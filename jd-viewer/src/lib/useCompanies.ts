import { useEffect, useMemo, useState } from 'react'
import type { CompanyStack, CompanyStacksFile } from '../types'
import { buildCompanySlugs } from './companySlug'

interface State {
  companies: CompanyStack[]
  meta: Omit<CompanyStacksFile, 'companies'> | null
  loading: boolean
  error: string | null
}

interface Result extends State {
  /** 회사 이름(norm) → 주소 슬러그. 목록·링크가 쓴다. */
  slugOf: (norm: string) => string
  /** 주소 슬러그 → 회사. 라우팅이 쓴다. */
  bySlug: (slug: string) => CompanyStack | null
}

export function useCompanies(): Result {
  const [state, setState] = useState<State>({
    companies: [],
    meta: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    fetch('/company_stacks.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: CompanyStacksFile) => {
        if (cancelled) return
        const { companies, ...meta } = data
        setState({ companies, meta, loading: false, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ companies: [], meta: null, loading: false, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  // 슬러그는 목록 전체를 봐야 정해진다(같은 이름이 겹치면 뒤에 번호가 붙는다).
  // 회사가 1,990곳이라 매 렌더마다 다시 만들면 안 된다.
  const maps = useMemo(() => {
    const { byNorm, bySlug } = buildCompanySlugs(state.companies.map((c) => c.norm))
    const byNormKey = new Map(state.companies.map((c) => [c.norm, c]))
    return { byNorm, bySlug, byNormKey }
  }, [state.companies])

  return {
    ...state,
    slugOf: (norm) => maps.byNorm.get(norm) ?? norm,
    bySlug: (slug) => {
      const norm = maps.bySlug.get(slug)
      return norm ? (maps.byNormKey.get(norm) ?? null) : null
    },
  }
}
