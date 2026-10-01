/**
 * 공고 기능의 요청 — 뷰어 API(backend `features/jobs`·`features/search`)와 파일 대체 경로.
 *
 * API 는 목록·칩 건수·상세를 정본 DB 에서 읽는 순간의 상태로 준다. API 가 없는 배포
 * (정적 호스팅, DB 가 내려간 동안)에서는 예전처럼 공고 전량 파일(184MB)을 받아 화면이
 * 거른다 — `probeJobsApi` 가 false 면 hooks/useJobs 가 그 길로 간다.
 */
import { apiGet, getJson, HttpError } from '../../api/client'
import type { CompanySize, Job } from '../../types'
import type { Facets, FilterState } from './utils/filter'

/** 목록 한 쪽에 싣는 건수. JobList 의 PAGE_SIZE_DENSE 와 같아야 쪽 번호가 맞는다. */
export const API_PAGE_SIZE = 20

interface FacetsWire {
  siteCount: Record<string, number>
  careerCount: Record<string, number>
  regions: Facets['regions']
  districts: Facets['districts']
  sizes: Facets['sizes']
  roles: Facets['roles']
  stacks: Facets['stacks']
}

interface JobsResponse {
  total: number
  all_total: number
  page: number
  limit: number
  items: Job[]
  engines: { fts: number; vector: number } | null
  facets: FacetsWire
}

export interface JobPage {
  items: Job[]
  total: number
  allTotal: number
  facets: Facets
  engines: { fts: number; vector: number } | null
}

export const EMPTY_FACETS: Facets = {
  siteCount: new Map(),
  careerCount: new Map(),
  regions: [],
  districts: [],
  sizes: [],
  roles: [],
  stacks: [],
}

/**
 * API 로 목록을 받을 수 있는지. `items` 배열까지 확인한다 — SPA 폴백(index.html)이나
 * 503(DB 다운)이면 false.
 */
export async function probeJobsApi(): Promise<boolean> {
  try {
    const body = await apiGet<{ items?: unknown }>('/api/jobs?limit=1')
    return Array.isArray(body.items)
  } catch {
    return false
  }
}

/** 필터 → /api/jobs 질의. 파라미터 이름은 backend 와 맞아야 한다(양쪽 테스트가 확인한다). */
export function toParams(f: FilterState, semantic: boolean, page: number): URLSearchParams {
  const p = new URLSearchParams()
  const add = (key: string, values: Iterable<string>) => {
    for (const v of [...values].sort()) p.append(key, v)
  }
  add('site', f.sites)
  add('career', f.careers)
  add('stack', f.stacks)
  add('role', f.roles)
  add('region', f.regions)
  add('district', f.districts)
  add('size', f.sizes)
  if (f.query.trim()) p.set('q', f.query)
  if (semantic && f.query.trim()) p.set('semantic', '1')
  p.set('closed', f.closed)
  p.set('unverified', f.unverified)
  p.set('page', String(page + 1))
  p.set('limit', String(API_PAGE_SIZE))
  return p
}

export async function fetchJobPage(qs: string, signal?: AbortSignal): Promise<JobPage> {
  const d = await apiGet<JobsResponse>(`/api/jobs?${qs}`, { signal })
  return {
    items: d.items,
    total: d.total,
    allTotal: d.all_total,
    engines: d.engines,
    facets: {
      ...d.facets,
      siteCount: new Map(Object.entries(d.facets.siteCount)),
      careerCount: new Map(Object.entries(d.facets.careerCount)),
    },
  }
}

/** 공고 한 건(본문 포함). 404 는 오류가 아니라 "없는 공고" — null. */
export async function fetchJob(key: string, signal?: AbortSignal): Promise<Job | null> {
  try {
    return await apiGet<Job>(`/api/jobs/${encodeURIComponent(key)}`, { signal })
  } catch (e) {
    if (e instanceof HttpError && e.status === 404) return null
    throw e
  }
}

/** 추천 목록은 url 만 들고 있다 — 그 공고의 주소 키. 없으면 null. */
export async function lookupJobKey(url: string): Promise<string | null> {
  try {
    const body = await apiGet<{ key?: string }>(`/api/jobs/lookup?url=${encodeURIComponent(url)}`)
    return body.key ?? null
  } catch {
    return null
  }
}

// ── 하이브리드 검색(파일 모드에서만 — API 모드에서는 /api/jobs?semantic=1 이 한다) ──

/** /api/search 응답의 한 건. */
export interface SearchHit {
  id: string
  url: string
  site: string
  company: string
  title: string
  career: string
  location: string
  tech_stack: string[]
  score: number
  rank_fts: number | null
  rank_vec: number | null
}

export interface SearchResponse {
  query: string
  total: number
  engines: { fts: number; vector: number }
  results: SearchHit[]
}

/** 검색 API 가 떠 있는지 — 서버가 자기 소개한 {ok:true} 까지 본다. */
export async function probeSearchApi(): Promise<boolean> {
  try {
    return (await apiGet<{ ok?: boolean }>('/api/health')).ok === true
  } catch {
    return false
  }
}

export function searchJobs(params: URLSearchParams, signal?: AbortSignal): Promise<SearchResponse> {
  return apiGet<SearchResponse>(`/api/search?${params}`, { signal })
}

// ── 파일 대체 경로 ────────────────────────────────────────────────────

/** build_company_meta.py 산출물. 키는 공고에 적힌 회사 이름 원문. */
interface CompanyMeta {
  generated_at: string
  company_count: number
  sizes: Record<string, CompanySize>
}

/**
 * 공고 전량과 회사 규모 색인. 규모는 얇은 색인(company_meta.json)에 따로 있다 — 공고
 * 파일에 넣으면 규모 하나 바뀔 때마다 큰 파일을 다시 받게 된다. 색인이 없는 배포도
 * 돌아가야 하므로(규모 필터만 사라진다) 그쪽 실패는 삼킨다.
 */
export async function fetchAllJobsFile(): Promise<Job[]> {
  const [data, meta] = await Promise.all([
    getJson<Job[]>('/all_jobs_enriched.json'),
    getJson<CompanyMeta>('/company_meta.json').catch(() => null),
  ])
  if (!meta) return data
  return data.map((j) => ({ ...j, company_size: meta.sizes[j.company] }))
}
