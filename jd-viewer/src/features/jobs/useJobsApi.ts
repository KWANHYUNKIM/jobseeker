import { useEffect, useState } from 'react'
import type { Job } from '../../types'
import type { Facets, FilterState } from './filter'
import { API_BASE } from './useHybridSearch'

/**
 * 공고 API(`catch_capture/store/api/main.py`) — 목록·칩 건수·상세를 DB 에서 받는다.
 *
 * 지금까지는 공고 전량(all_jobs_enriched.json, 184MB)을 첫 화면에서 받아 필터·칩 건수를
 * 브라우저에서 셌다. 그 파일은 크롤 사이클마다 구워졌으므로 DB 에서 닫힌 공고가 다음
 * 굽기까지 화면에 모집중으로 남았다. API 는 읽는 순간의 상태를 준다.
 *
 * API 가 없는 배포(옛 검색 서버만 떠 있거나 /api/ 프록시가 없는 곳)에서는 예전처럼
 * 파일로 돈다 — `useJobsApiAvailable` 이 'no' 를 돌려주면 App 이 useJobs 로 되돌아간다.
 */

export type ApiState = 'unknown' | 'yes' | 'no'

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
 * API 로 목록을 받을 수 있는지. 상태 코드만 보면 안 된다 — /api/ 프록시가 없는
 * 배포에서는 SPA 폴백이 index.html 을 200 으로 돌려준다(useSearchAvailable 과 같은
 * 이유). 응답을 JSON 으로 읽어 `items` 배열이 있는지까지 본다.
 */
export function useJobsApiAvailable(): ApiState {
  const [state, setState] = useState<ApiState>('unknown')
  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/api/jobs?limit=1`)
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => !cancelled && setState(Array.isArray(body?.items) ? 'yes' : 'no'))
      .catch(() => !cancelled && setState('no'))
    return () => {
      cancelled = true
    }
  }, [])
  return state
}

/** 필터 → /api/jobs 질의. 파라미터 이름은 store/api/main.py 와 맞아야 한다(테스트가 양쪽에서 확인한다). */
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

interface PageData {
  items: Job[]
  total: number
  allTotal: number
  facets: Facets
  engines: { fts: number; vector: number } | null
}

interface PageState extends PageData {
  loading: boolean
  error: string | null
}

const EMPTY_PAGE: PageData = { items: [], total: 0, allTotal: 0, facets: EMPTY_FACETS, engines: null }

const DEBOUNCE_MS = 200

/**
 * 필터·쪽 번호 → 목록 한 쪽과 칩 건수. 빠르게 치는 동안의 중간 값은 버린다
 * (디바운스 + 앞선 요청 취소). 새 응답이 오기 전까지는 앞 화면을 그대로 둔다 —
 * 칩과 목록이 한 박자씩 빈 화면으로 깜박이지 않게.
 *
 * "지금 로딩 중인가" 는 상태로 따로 두지 않고, 마지막 응답이 **어느 질의의 답인가**
 * 로 계산한다. effect 안에서 곧바로 loading 을 켜면 렌더가 한 번 더 돈다.
 */
export function useJobPage(filter: FilterState, semantic: boolean, page: number, enabled: boolean): PageState {
  const qs = toParams(filter, semantic, page).toString()
  const [done, setDone] = useState<{ qs: string; data: PageData; error: string | null } | null>(null)

  useEffect(() => {
    if (!enabled) return
    const ac = new AbortController()
    const timer = setTimeout(() => {
      fetch(`${API_BASE}/api/jobs?${qs}`, { signal: ac.signal })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`)
          return r.json() as Promise<JobsResponse>
        })
        .then((d) =>
          setDone({
            qs,
            error: null,
            data: {
              items: d.items,
              total: d.total,
              allTotal: d.all_total,
              engines: d.engines,
              facets: {
                ...d.facets,
                siteCount: new Map(Object.entries(d.facets.siteCount)),
                careerCount: new Map(Object.entries(d.facets.careerCount)),
              },
            },
          }),
        )
        .catch((e) => {
          if (e.name === 'AbortError') return // 뒤 요청이 이어받는다
          setDone((prev) => ({ qs, data: prev?.data ?? EMPTY_PAGE, error: String(e) }))
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      ac.abort()
    }
  }, [qs, enabled])

  return {
    ...(done?.data ?? EMPTY_PAGE),
    loading: enabled && done?.qs !== qs,
    error: done?.qs === qs ? done.error : null,
  }
}

interface JobState {
  job: Job | null
  loading: boolean
  error: string | null
}

/** 공고 한 건(본문 포함). key 는 주소의 `/jobs/<사이트>-<번호>` 부분. */
export function useJob(key: string | null, enabled: boolean): JobState {
  const [done, setDone] = useState<{ key: string; job: Job | null; error: string | null } | null>(null)
  const active = enabled && !!key

  useEffect(() => {
    if (!active || !key) return
    const ac = new AbortController()
    fetch(`${API_BASE}/api/jobs/${encodeURIComponent(key)}`, { signal: ac.signal })
      .then((r) => {
        // 404 는 오류가 아니라 "없는 공고" 다 — 화면이 따로 안내한다.
        if (r.status === 404) return null
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Job>
      })
      .then((job) => setDone({ key, job, error: null }))
      .catch((e) => {
        if (e.name === 'AbortError') return
        setDone({ key, job: null, error: String(e) })
      })
    return () => ac.abort()
  }, [key, active])

  if (!active) return { job: null, loading: false, error: null }
  const fresh = done?.key === key
  return { job: fresh ? done.job : null, loading: !fresh, error: fresh ? done.error : null }
}

/** 추천 목록은 url 만 들고 있다 — 그 공고의 주소 키. 없으면 null. */
export async function lookupJobKey(url: string): Promise<string | null> {
  try {
    const r = await fetch(`${API_BASE}/api/jobs/lookup?url=${encodeURIComponent(url)}`)
    if (!r.ok) return null
    const body = (await r.json()) as { key?: string }
    return body.key ?? null
  } catch {
    return null
  }
}
