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

export interface Feature {
  key: string
  name: string
  domain: string
  updated_at?: string
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
  products: string[]
  one_liner: string
  /** 로고를 가져올 회사 도메인. 없으면 글자 마크로 대체한다. */
  domain?: string
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
