/**
 * 취업(커리어 후기) — 뷰어 API `/api/careers`(backend features/careers)가 정본 DB(019)를 센 값.
 *
 * 정적 파일 사본이 없다 — 원문이 남의 글이라 public 에 굽지 않는다. API 가 없으면 화면은 오류를 말한다.
 * 원문 본문은 열쇠(X-Careers-Key)를 아는 요청에만 온다. 열쇠는 이 브라우저에만 둔다(localStorage).
 */
import { apiGet } from '../../api/client'

/** [이름, 건수] 또는 표본이 충분하면 [이름, 건수, 비율%] */
export type Count = [string, number] | [string, number, number]

export interface Spec {
  n: number
  with_spec: number
  levels: Count[]
  education: Count[]
  gpa: { n: number; median: number | null; bands: Count[] }
  certs: Count[]
  language: Count[]
  activities: Count[]
  awards: Count[]
  internships: Count[]
  algorithm: Count[]
  age: { n: number; median: number | null }
  years_before: { n: number; median: number | null }
  stack: Count[]
  programs: Count[]
}

export interface StoryBrief {
  id: string
  title: string | null
  source: string | null
  year: number | null
  kind: string | null
  company: string | null
  company_type: string | null
  role: string | null
  level: string | null
  years_before: number | null
  origin: string | null
  education: string | null
  summary: string | null
  steps: string[]
}

export interface Voice {
  t: string
  id: string
  company: string | null
  year: number | null
}

export interface Overview {
  updated_at: string | null
  total: { posts: number; stories: number; counted: number }
  n: number
  filters: Partial<Record<FilterKey, string>>
  facets: { years: [number, number][]; types: Count[]; levels: Count[]; kinds: Count[]; roles: Count[]; origins: Count[] }
  companies: { key: string; name: string; type: string | null; n: number }[]
  programs: { key: string; name: string; n: number }[]
  spec: Spec
  by_year: (Spec & { year: number; kinds: Count[]; types: Count[] })[]
  by_type: (Spec & { type: string; companies: Count[] })[]
  moves: {
    n: number
    origins: Count[]
    matrix: { origin: string; type: string; n: number }[]
    years: { band: string; n: number; types: Count[] }[]
    destinations: { company: string; type: string | null; n: number }[]
    transitions: Count[]
    examples: StoryBrief[]
  }
  paths: {
    tags: Count[]
    prep: Count[]
    prep_months: { n: number; median: number | null }
    interviews: Count[]
    coding_test: Count[]
  }
  applied: { company: string; pass: number; fail: number; stages: Count[] }[]
  docs: Record<'resume_points' | 'portfolio_points' | 'portfolio_projects' | 'cover_letter_points' | 'cover_letter_questions', Count[]>
  voices: { factors: Voice[]; advice: Voice[]; questions: Voice[] }
}

export interface StoryList {
  n: number
  offset: number
  items: StoryBrief[]
}

export interface StoryDetail extends Omit<StoryBrief, 'steps' | 'summary'> {
  url: string | null
  posted_on: string | null
  period: string | null
  program: string | null
  company_size: string | null
  transition: string | null
  transition_cat: string | null
  age: number | null
  tags: string[]
  summary?: string | null
  path?: { step: string; months?: number | null }[]
  spec?: Record<string, unknown>
  selection?: Record<string, unknown>
  stack?: string[]
  prep_months?: number | null
  prep_methods?: string[]
  key_factors?: string[]
  advice?: string[]
  market_note?: string | null
  background?: Record<string, unknown>
  application?: Record<string, unknown>
  other_companies?: { company?: string | null; result?: string | null; stage?: string | null }[]
  path_tags?: string[]
  year_from?: string | null
  company_from?: string | null
  company_desc?: string | null
  body: string | null
  body_locked: boolean
  body_chars: number
}

export interface Roster {
  posts: number
  people: number
  years: [number, number][]
  orgs: { org: string; n: number; type: string | null; schools: Count[]; majors: Count[]; cs: number; years: [number, number][] }[]
  schools: Count[]
}

export const FILTER_KEYS = ['year', 'type', 'level', 'kind', 'role', 'origin', 'company', 'q'] as const
export type FilterKey = (typeof FILTER_KEYS)[number]
export type Filters = Partial<Record<FilterKey, string>>

function qs(f: Filters, extra: Record<string, string | number> = {}): string {
  const p = new URLSearchParams()
  for (const k of FILTER_KEYS) if (f[k]) p.set(k, f[k] as string)
  for (const [k, v] of Object.entries(extra)) p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const fetchOverview = (f: Filters, signal?: AbortSignal) => apiGet<Overview>(`/api/careers${qs(f)}`, { signal })

export const fetchStories = (f: Filters, offset: number, signal?: AbortSignal) =>
  apiGet<StoryList>(`/api/careers/stories${qs(f, { offset, limit: 40 })}`, { signal })

export const fetchRoster = (signal?: AbortSignal) => apiGet<Roster>('/api/careers/roster', { signal })

const KEY = 'careersKey'

export function careersKey(): string {
  try {
    return localStorage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}

export function setCareersKey(v: string): void {
  try {
    if (v) localStorage.setItem(KEY, v)
    else localStorage.removeItem(KEY)
  } catch {
    /* 저장이 막힌 브라우저 — 이번 화면에서만 쓴다 */
  }
}

export function fetchStory(id: string, key: string, signal?: AbortSignal) {
  return apiGet<StoryDetail>(`/api/careers/stories/${encodeURIComponent(id)}`, {
    signal,
    headers: key ? { 'X-Careers-Key': key } : undefined,
  })
}
