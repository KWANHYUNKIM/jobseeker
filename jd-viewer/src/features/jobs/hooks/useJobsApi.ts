import { useEffect, useState } from 'react'
import type { Job } from '../../../types'
import { EMPTY_FACETS, fetchJob, fetchJobPage, probeJobsApi, toParams, type JobPage } from '../api'
import type { FilterState } from '../utils/filter'

/**
 * 공고 API 훅 — 요청 자체는 ../api.ts 에 있고, 여기는 화면 상태(디바운스·취소·로딩)만 둔다.
 */

export type ApiState = 'unknown' | 'yes' | 'no'

/** API 로 목록을 받을 수 있는지. 'no' 면 공고 전량 파일로 돈다(useJobs). */
export function useJobsApiAvailable(): ApiState {
  const [state, setState] = useState<ApiState>('unknown')
  useEffect(() => {
    let cancelled = false
    void probeJobsApi().then((ok) => !cancelled && setState(ok ? 'yes' : 'no'))
    return () => {
      cancelled = true
    }
  }, [])
  return state
}

interface PageState extends JobPage {
  loading: boolean
  error: string | null
}

const EMPTY_PAGE: JobPage = { items: [], total: 0, allTotal: 0, facets: EMPTY_FACETS, engines: null }

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
  const [done, setDone] = useState<{ qs: string; data: JobPage; error: string | null } | null>(null)

  useEffect(() => {
    if (!enabled) return
    const ac = new AbortController()
    const timer = setTimeout(() => {
      fetchJobPage(qs, ac.signal)
        .then((data) => setDone({ qs, data, error: null }))
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
    fetchJob(key, ac.signal)
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
