import { apiGet } from '../../api/client'
import type { Site } from '../../types'

/** 메인 화면(`/`) — backend `/api/home`. 모집중인 국내 IT 공고를 회사별로 묶은 것. */

export type HomeSize = '대기업' | '중견기업' | '중소기업' | '해외 기업'

export interface HomeCompany {
  name: string
  slug: string
  logo: string | null
  size: HomeSize
  industry: string
  active: number
  entry: number
  experienced: number
  career_from: string | null
  career_to: string | null
  new_7d: number
  latest_at: string
  soonest_dday: number | null
  roles: string[]
  titles: { title: string; site: string; pid: string; career_bucket: string; dday: number | null }[]
}

export interface HomeJob {
  site: Site
  pid: string
  url: string
  title: string
  company: string
  company_slug: string
  logo: string | null
  size: HomeSize | null
  industry: string
  career: string | null
  career_bucket: string
  region: string | null
  district: string | null
  dday: number | null
  deadline: string | null
  first_seen_at: string
  roles: string[]
  stacks: string[]
}

export interface HomeBoard {
  generated_at: string
  /** 첫 화면 로고 띠 — 필터와 무관하게 공고가 많은 큰 회사 */
  spotlight: { name: string; slug: string; logo: string | null; size: HomeSize; active: number }[]
  totals: { companies: number; jobs: number; entry: number; experienced: number }
  facets: { sizes: { name: HomeSize; n: number }[]; industries: { name: string; n: number }[] }
  companies: HomeCompany[]
  /** 아래로 내리며 보는 구역 — TOP 50 의 앞 10건. 나머지는 fetchSection */
  sections: HomeSection[]
}

export interface HomeSection {
  key: string
  /** 구역 이름(신입·경력·은행·금융…) */
  title: string
  /** 순위 제목 앞말 — '신입 인기' → '신입 인기 TOP 50' */
  lead: string
  total: number
  jobs: HomeJob[]
}

export interface HomeCompanyDetail {
  company: HomeCompany
  careers: { bucket: string; n: number }[]
  jobs: HomeJob[]
}

export type HomeSort = 'popular' | 'new' | 'count'

export function fetchHome(
  q: { size: string; industry: string; sort: HomeSort; limit: number },
  init?: RequestInit,
): Promise<HomeBoard> {
  const p = new URLSearchParams({ sort: q.sort, limit: String(q.limit) })
  if (q.size) p.set('size', q.size)
  if (q.industry) p.set('industry', q.industry)
  return apiGet<HomeBoard>(`/api/home?${p}`, init)
}

export function fetchHomeCompany(slug: string, init?: RequestInit): Promise<HomeCompanyDetail> {
  return apiGet<HomeCompanyDetail>(`/api/home/company/${encodeURIComponent(slug)}`, init)
}

export function fetchSection(key: string, init?: RequestInit): Promise<HomeSection> {
  return apiGet<HomeSection>(`/api/home/section/${encodeURIComponent(key)}`, init)
}
