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

export interface Domain {
  name: string
  why: string
  features?: string[]
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

export interface Feature {
  key: string
  name: string
  domain: string
  updated_at?: string
  business: { why: string; metrics?: Metric[] }
  domain_model?: {
    entities?: { name: string; what: string }[]
    invariants?: string[]
  }
  implementation?: {
    flow?: { step: string; why?: string }[]
    decisions?: Decision[]
    stack?: StackItem[]
  }
  connections?: Connection[]
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

export const useRevengIndex = () => useJson<RevengIndex>('/reveng/index.json')
export const useCompany = (slug: string | null) =>
  useJson<Company>(slug ? `/reveng/companies/${slug}.json` : null)
