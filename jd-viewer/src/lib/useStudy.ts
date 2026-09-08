import { useEffect, useState } from 'react'

// public/study/index.json + public/study/articles/<slug>.json
//   — study-engine/PROMPT.md 가 매 사이클 갱신, study-engine/schema.json 이 형식의 단일 소스.
//
// 목록(index)과 문서를 나눠 받는 이유는 역설계 쪽과 같다: 문서가 늘어나도 목록은 파일
// 하나면 되고, 본문은 열어 본 문서만 내려받는다. 문서 하나가 30KB 를 넘는다.

export type Confidence = 'confirmed' | 'inferred' | 'unknown'
export type Category =
  | 'language' | 'framework' | 'runtime' | 'infra' | 'data' | 'ai'
  | 'firmware' | 'hardware' | 'term' | 'domain' | 'practice'
export type Level = 'basic' | 'core' | 'deep'

export interface Source {
  title: string
  url: string
  publisher?: string
  date?: string
  kind?: string
  summary?: string
}

interface Claim {
  confidence?: Confidence
  sources?: Source[]
}

/** 채용 데이터에 못 박은 수요. tech_relations.json 에서 그대로 옮긴 값이고, 없는 낱말도 많다 */
export interface Market {
  tech: string
  layer?: string
  postings: number
  pct_jobs: number
  with?: { name: string; pct: number; why?: string }[]
  as_of: string
}

export interface Section extends Claim {
  id: string
  heading: string
  /** what → why → how → limits 의 네 자리. why 가 없는 문서는 공식 문서 요약본이다 */
  kind: 'what' | 'why' | 'how' | 'limits' | 'extra'
  body: string
}

/** 산문으로 쓰면 안 읽히는 것 — 핀맵·레지스터 비트·저항 색띠·선택지 비교 */
export interface Table extends Claim {
  id: string
  kind: 'pinmap' | 'register' | 'spec' | 'compare' | 'glossary'
  caption: string
  /** 읽는 법과 전제. 핀맵이면 패키지가 여기 적혀 있다(패키지가 다르면 핀 번호가 다르다) */
  note?: string
  columns: string[]
  rows: string[][]
}

export interface WhenToUse extends Claim {
  situation: string
  pick: string
  /** 무엇 대신인가. 이게 없으면 '이럴 땐 이걸'은 고르는 데 도움이 안 된다 */
  over: string
  why: string
  tradeoff: string
}

export interface Pitfall {
  trap: string
  why: string
  /** fix 없는 항목은 경고가 아니라 겁주기다 */
  fix: string
  sources?: Source[]
}

export interface Term {
  term: string
  en?: string
  what: string
}

export interface Drill {
  task: string
  done_when: string
  why: string
  needs?: string
  /** 장비가 없을 때의 대안. 하드웨어가 필요한 실습이면 채워져 있다 */
  no_hardware?: string
  hours?: number
}

/** 이 낱말이 실제로 박힌 문장 — 이 백과사전이 남의 것과 갈리는 자리 */
export interface Evidence {
  quote: string
  from: 'posting' | 'blog' | 'docs' | 'standard'
  url: string
  where?: string
  what_it_shows: string
}

export interface Related {
  slug: string
  how: string
}

export interface Article {
  slug: string
  title: string
  title_en?: string
  aliases: string[]
  category: Category
  level: Level
  status: 'in_progress' | 'done'
  updated_at: string
  one_liner: string
  summary: string
  market?: Market | null
  sections?: Section[]
  tables?: Table[]
  when_to_use?: WhenToUse[]
  pitfalls?: Pitfall[]
  terms?: Term[]
  drills?: Drill[]
  checks?: string[]
  evidence?: Evidence[]
  related?: Related[]
  open_questions?: string[]
  sources?: Source[]
}

export interface IndexEntry {
  slug: string
  title: string
  category: Category
  level: Level
  status: 'in_progress' | 'done'
  one_liner: string
  /** tech_relations.json 의 name 과 글자 그대로 같은 값이 들어 있다 — 관계 화면이 이걸로 잇는다 */
  aliases: string[]
  sections: number
  drills: number
  updated_at: string
}

export interface StudyIndex {
  updated_at: string
  articles: IndexEntry[]
  categories: Record<string, string>
}

export const LEVEL_LABEL: Record<Level, string> = {
  basic: '기초',
  core: '중급',
  deep: '심화',
}

// 받아 온 결과에 **그 결과가 어느 주소의 것인지**를 함께 담는다. loading·초기화를
// 따로 setState 하지 않고 `state.path === path` 로 계산해서 얻는 방식이다.
// (useReveng.ts 의 같은 훅은 효과 안에서 setState 를 세 번 부르는데, 그러면 주소가
//  바뀐 첫 프레임에 **앞 문서의 본문이 새 제목 밑에 잠깐 보인다.** 문서를 옮겨 다니는
//  화면에서는 그게 눈에 걸린다.)
function useJson<T>(path: string | null) {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string | null }>({
    path: null,
    data: null,
    error: null,
  })

  useEffect(() => {
    if (path === null) return
    let cancelled = false
    fetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - ${path}`)
        return r.json()
      })
      .then((d: T) => {
        if (!cancelled) setState({ path, data: d, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ path, data: null, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [path])

  const fresh = state.path === path
  return {
    data: fresh ? state.data : null,
    loading: path !== null && !fresh,
    error: fresh ? state.error : null,
  }
}

export const useStudyIndex = () => useJson<StudyIndex>('/study/index.json')
export const useArticle = (slug: string | null) =>
  useJson<Article>(slug ? `/study/articles/${slug}.json` : null)

/**
 * 기술 이름 → 문서 slug. 기술 관계 화면에서 백과사전으로 들어오는 유일한 길이다.
 * 대소문자만 접는다 — 그 이상 손대면 `C++`·`C/C++` 처럼 기호가 뜻인 이름이 뭉개진다.
 */
export function articleByTech(index: StudyIndex | null, tech: string | null | undefined): IndexEntry | null {
  if (!index || !tech) return null
  const key = tech.toLowerCase()
  return index.articles.find((a) => a.aliases.some((x) => x.toLowerCase() === key)) ?? null
}
