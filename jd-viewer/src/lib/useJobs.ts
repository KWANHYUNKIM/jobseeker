import { useEffect, useState } from 'react'
import type { CompanySize, Job } from '../types'

interface State {
  jobs: Job[]
  loading: boolean
  error: string | null
}

/** build_company_meta.py 산출물. 키는 공고에 적힌 회사 이름 원문. */
interface CompanyMeta {
  generated_at: string
  company_count: number
  sizes: Record<string, CompanySize>
}

/** 오늘 날짜(한국). deadline_date 와 같은 YYYY-MM-DD 로. */
function todayKst(): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())
}

/**
 * 마감일이 지난 공고를 화면에서 닫는다.
 *
 * status 는 데이터를 만든 날 기준이다. 파이프라인이 멈추면(맥이 꺼지면) 그 날짜에
 * 굳은 채로 계속 서빙돼, 마감일이 지난 공고가 모집중 목록에 며칠이고 남았다.
 * 연도까지 확정된 deadline_date 가 있는 공고는 여기서 오늘과 다시 비교한다.
 * 수동 보정(override)은 사람이 정한 답이라 건드리지 않는다.
 */
function expirePassed(jobs: Job[]): Job[] {
  const today = todayKst()
  return jobs.map((j) =>
    j.status !== 'closed' && j.status_source !== 'override' && j.deadline_date && j.deadline_date < today
      ? { ...j, status: 'closed', closed_reason: `마감일 경과(${j.deadline_date})` }
      : j,
  )
}

/**
 * 공고 전량을 파일로 받는다. `enabled` 가 false 면 아무것도 받지 않는다 — 공고 API 가
 * 있는 배포에서는 184MB 를 받을 이유가 없다(App 이 API 가 없을 때만 켠다).
 */
export function useJobs(enabled = true): State {
  const [state, setState] = useState<State>({ jobs: [], loading: true, error: null })

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    // 회사 규모는 얇은 색인(company_meta.json)에 따로 있다. 공고 파일에 넣으면
    // 62MB 짜리를 규모 하나 바뀔 때마다 다시 내려받게 된다. 이 색인이 없는 배포도
    // 그대로 돌아가야 하므로(규모 필터만 사라진다) 실패를 통째로 삼킨다.
    const sizes = fetch('/company_meta.json')
      .then((r) => (r.ok ? (r.json() as Promise<CompanyMeta>) : null))
      .catch(() => null)

    Promise.all([
      fetch('/all_jobs_enriched.json').then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Job[]>
      }),
      sizes,
    ])
      .then(([data, meta]) => {
        if (cancelled) return
        const bySize = meta?.sizes ?? {}
        const withSize = meta
          ? data.map((j) => ({ ...j, company_size: bySize[j.company] }))
          : data
        setState({ jobs: expirePassed(withSize), loading: false, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ jobs: [], loading: false, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [enabled])

  return state
}
