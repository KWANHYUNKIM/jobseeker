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

export function useJobs(): State {
  const [state, setState] = useState<State>({ jobs: [], loading: true, error: null })

  useEffect(() => {
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
        const jobs = meta
          ? data.map((j) => ({ ...j, company_size: bySize[j.company] }))
          : data
        setState({ jobs, loading: false, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ jobs: [], loading: false, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
