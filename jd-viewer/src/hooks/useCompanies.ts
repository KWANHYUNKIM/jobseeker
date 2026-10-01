import { useEffect, useMemo, useState } from 'react'
import { apiGet, apiOrFile, type Source } from '../api/client'
import type { CompanyStack, CompanyStacksFile } from '../types'
import { buildCompanySlugs } from '../utils/companySlug'

/**
 * 회사 프로필. 회사 탭과 개발 트렌드(확장 지도)가 같이 쓴다.
 *
 * 뷰어 API(`/api/companies`)는 목록에 **요약 필드만** 싣는다 — company_stacks.json(15MB)의
 * 대부분은 회사 하나를 열 때만 쓰는 필드(career_guide·postings …)다. 고른 회사의 전체
 * 프로필은 `useCompanyDetail` 이 따로 받는다. API 가 없으면 파일 전체를 받고, 그때는
 * 목록의 항목이 이미 전체 프로필이다.
 */

/** 목록에서 빠질 수 있는 필드(API 가 detail_fields 로 알려 준다). */
type DetailField = 'career_guide' | 'postings' | 'architecture' | 'summary' | 'titles'
export type CompanyListItem = Omit<CompanyStack, DetailField> & Partial<Pick<CompanyStack, DetailField>>

type IndexFile = Omit<CompanyStacksFile, 'companies'> & { companies: CompanyListItem[]; detail_fields?: string[] }

interface State {
  companies: CompanyListItem[]
  meta: Omit<CompanyStacksFile, 'companies'> | null
  source: Source | null
  loading: boolean
  error: string | null
}

interface Result extends State {
  /** 회사 이름(norm) → 주소 슬러그. 목록·링크가 쓴다. */
  slugOf: (norm: string) => string
  /** 주소 슬러그 → 회사. 라우팅이 쓴다. */
  bySlug: (slug: string) => CompanyListItem | null
}

let indexCache: Promise<{ data: IndexFile; source: Source }> | null = null

export function useCompanies(): Result {
  const [state, setState] = useState<State>({
    companies: [],
    meta: null,
    source: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    indexCache ??= apiOrFile<IndexFile>('/api/companies', '/company_stacks.json')
    indexCache
      .then(({ data, source }) => {
        if (cancelled) return
        const { companies, detail_fields: _drop, ...meta } = data
        void _drop
        setState({ companies, meta, source, loading: false, error: null })
      })
      .catch((e) => {
        indexCache = null
        if (!cancelled) setState({ companies: [], meta: null, source: null, loading: false, error: String(e) })
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

const detailCache = new Map<string, Promise<CompanyStack | null>>()

function isFull(c: CompanyListItem): c is CompanyStack {
  return Array.isArray(c.postings) && c.titles !== undefined
}

/** 고른 회사의 전체 프로필. 파일 모드에서는 목록 항목이 이미 전체다. */
export function useCompanyDetail(item: CompanyListItem | null): { company: CompanyStack | null; loading: boolean } {
  const full = item && isFull(item) ? item : null
  const norm = item && !full ? item.norm : null
  const [done, setDone] = useState<{ norm: string; company: CompanyStack | null } | null>(null)

  useEffect(() => {
    if (!norm) return
    let cancelled = false
    let p = detailCache.get(norm)
    if (!p) {
      p = apiGet<CompanyStack>(`/api/companies/${encodeURIComponent(norm)}`).catch(() => null)
      detailCache.set(norm, p)
    }
    void p.then((company) => !cancelled && setDone({ norm, company }))
    return () => {
      cancelled = true
    }
  }, [norm])

  if (full) return { company: full, loading: false }
  if (!norm) return { company: null, loading: false }
  const fresh = done?.norm === norm
  return { company: fresh ? done.company : null, loading: !fresh }
}
