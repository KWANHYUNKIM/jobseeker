import { useEffect, useState } from 'react'

// public/reveng/index.json + public/reveng/companies/<slug>.json
//   — engine/PROMPT.md 가 매 사이클 갱신, engine/schema.json 이 형식의 단일 소스.
//
// 목록(index)과 상세(company)를 나눠 받는 이유: 회사가 늘어나도 메인 그리드는
// 파일 하나만 읽으면 되고, 상세는 열어 본 회사만 내려받는다.

export type Confidence = 'confirmed' | 'inferred' | 'unknown'

export interface Source {
  title: string
  url: string
  publisher?: string
  date?: string
  summary?: string
}

interface Claim {
  confidence?: Confidence
  sources?: Source[]
}

export interface RevenueStream extends Claim {
  name: string
  how: string
  /** 전체 매출에서 이 수익원이 차지하는 비중(%). 공개 실적에 숫자가 있을 때만 채운다 */
  share?: number
  /** 표시용 금액 문자열 — 단위가 회사마다 달라(조·억·$B) 계산하지 않고 그대로 적는다 */
  amount?: string
}

export interface DomainTech extends Claim {
  tech: string
  solves: string
  limits: string
}

export interface Domain {
  name: string
  why: string
  tech?: DomainTech[]
  features?: string[]
}

// 그림은 여러 장이다 — 정상 흐름과 실패 경로는 같은 그림에 그리면 둘 다 안 읽힌다.
export interface Diagram {
  title: string
  question?: string
  kind?: 'flow' | 'sequence' | 'state' | 'failure'
  code: string
}

// 결정이 '무엇을 골랐나'라면 이건 '고르기 전에 무엇이 걸렸나'다.
export interface Thought {
  at: string
  thought: string
  confidence?: Confidence
}

export interface Metric extends Claim {
  label: string
  value: string
}

export interface Decision extends Claim {
  question: string
  chosen: string
  alternatives?: string[]
  tradeoff: string
}

export interface StackItem extends Claim {
  tech: string
  role: string
}

export interface Connection {
  to: string
  via: string
  contract?: string
  confidence?: Confidence
}

// 회사 밖의 근거 — engine/STYLE.md 7번.
// 회사 자료만 읽으면 '이 회사는 이렇게 했다'에서 끝나고, 왜 그것 말고 다른 수가
// 없었는지가 안 보인다. 그 답은 대개 논문과 난제 쪽에 있다.
export interface Paper {
  title: string
  authors?: string
  year?: string
  venue?: string
  url: string
  takeaway: string
  confidence?: Confidence
}

// open_questions 와 다르다 — 저건 '내가 못 찾은 것', 이건 '업계가 아직 못 푼 것'.
export interface HardProblem extends Claim {
  problem: string
  why_hard: string
  current_best?: string
}

export interface Research {
  papers?: Paper[]
  hard_problems?: HardProblem[]
}

// ── 화면 도해 (UiSketch) ─────────────────────────────────────
// 이 탭의 글은 "무엇을 어떻게 만들었나"인데, 읽는 사람에게는 그게 앱의 어느 부분
// 이야기인지 붙들 데가 없다. 그래서 사용자가 보는 화면을 먼저 놓고, 그 위의 번호에
// 설명을 건다.
//
// ⚠️ 실제 화면 캡처가 아니다. 남의 앱 화면을 공개 사이트에 올리는 문제를 피하고,
// 앱 로그인이 필요해 애초에 찍을 수 없는 회사(토스·당근 등)까지 같은 형식으로
// 다루려고 **공개 자료에 적힌 것만으로 다시 그린 도해**를 쓴다. 그래서 element 는
// 자유 HTML 이 아니라 아래의 정해진 종류만 받는다 — 형식이 열려 있으면 회사마다
// 제각각이 되고, 그 순간 이 도해는 '그 회사 화면'이 아니라 '그린 사람의 취향'이 된다.
export type UiElementType =
  | 'appbar'
  | 'label'
  | 'text'
  | 'input'
  | 'chips'
  | 'amount'
  | 'button'
  | 'rows'
  | 'tabs'
  | 'card'
  | 'divider'
  | 'spacer'

export interface UiElement {
  type: UiElementType
  /** appbar·label·text·input·amount·button·card 의 본문 */
  text?: string
  /** input 의 회색 자리표시자 */
  hint?: string
  /** chips·tabs 의 항목, card 의 줄 */
  items?: string[]
  /** rows 의 줄 */
  rows?: { title: string; sub?: string; right?: string }[]
  /** button 의 강조 여부 */
  variant?: 'primary' | 'ghost'
  /** 이 요소에 걸린 설명 번호. pins[].n 과 맞는다 */
  pin?: number
}

export interface UiPin extends Claim {
  n: number
  title: string
  what: string
  /** 회사 화면 도해에서만 — 이 자리가 어느 도메인인가 */
  domain?: string
}

export interface UiSketchData {
  title: string
  /** 이 도해가 답하는 질문. 없으면 빼는 것이 낫다 — STYLE.md 1번 */
  question?: string
  kind?: 'phone' | 'web'
  /** 재구성이라는 사실을 화면에 남기는 자리. 비어 있으면 기본 문구가 붙는다 */
  note?: string
  screen: UiElement[]
  pins: UiPin[]
}

export interface Feature {
  key: string
  name: string
  domain: string
  updated_at?: string
  /** 이 기능이 사용자에게 보이는 자리 */
  ui?: UiSketchData
  business: { why: string; metrics?: Metric[] }
  thinking?: Thought[]
  domain_model?: {
    // 스키마는 {name, what} 객체지만, 초기 사이클들이 "이름 — 설명" 한 문자열로 적은
    // 데이터가 6개 회사 14개 기능에 남아 있다. 화면은 둘 다 읽는다 — 객체만 읽으면
    // 그 14개는 빈 줄로 나온다. 엔진 쪽은 validate.py 가 경고로 몰아간다.
    entities?: ({ name: string; what: string } | string)[]
    invariants?: string[]
  }
  implementation?: {
    flow?: { step: string; why?: string }[]
    decisions?: Decision[]
    stack?: StackItem[]
  }
  connections?: Connection[]
  research?: Research
  diagrams?: Diagram[]
  diagram?: string
  sources?: Source[]
}

export interface Company {
  slug: string
  name: string
  name_en: string
  country: string
  category: string
  status: 'in_progress' | 'done'
  updated_at: string
  business_model: string
  /** 표시용 총매출 한 줄. 예: '2025년 연결 매출 12조 350억' */
  revenue_total?: string
  products: string[]
  one_liner: string
  /** 로고를 가져올 회사 도메인. 없으면 글자 마크로 대체한다. */
  domain?: string
  /** 앱 첫 화면 도해 — 어느 자리가 어느 도메인인지. 있으면 도메인 지도(mermaid)는 접힌다 */
  ui_map?: UiSketchData
  domain_map?: Diagram
  revenue_streams?: RevenueStream[]
  domains?: Domain[]
  features?: Feature[]
  open_questions?: string[]
  sources?: Source[]
}

export interface IndexEntry {
  slug: string
  name: string
  name_en: string
  country: string
  category: string
  status: 'in_progress' | 'done'
  features_done: number
  one_liner: string
  updated_at: string
  /** 로고를 가져올 회사 도메인. 없으면 글자 마크로 대체한다. */
  domain?: string
}

export interface RevengIndex {
  updated_at: string
  companies: IndexEntry[]
  domains: string[]
  countries: Record<string, string>
}

function useJson<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(path !== null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (path === null) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - ${path}`)
        return r.json()
      })
      .then((d: T) => {
        if (!cancelled) {
          setData(d)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [path])

  return { data, loading, error }
}

// 도메인 비교 문서 — 여러 회사가 같은 문제를 어떻게 다르게 풀었는지.
// 회사 페이지가 '한 회사를 세로로' 읽는 것이라면 이쪽은 '한 문제를 가로로' 읽는다.
export interface DomainDoc {
  slug: string
  title: string
  question?: string
  companies: string[]
  features: string[]
  file: string
}

export interface DomainIndex {
  updated_at: string
  docs: DomainDoc[]
}

export const useRevengIndex = () => useJson<RevengIndex>('/reveng/index.json')
export const useDomainDocs = () => useJson<DomainIndex>('/reveng/domains/index.json')
export const useCompany = (slug: string | null) =>
  useJson<Company>(slug ? `/reveng/companies/${slug}.json` : null)

// 마크다운은 JSON 이 아니라 텍스트로 받는다.
export function useMarkdown(path: string | null) {
  const [text, setText] = useState<string | null>(null)
  const [loading, setLoading] = useState(path !== null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (path === null) {
      setText(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - ${path}`)
        return r.text()
      })
      .then((t) => {
        if (!cancelled) {
          setText(t)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [path])

  return { text, loading, error }
}
