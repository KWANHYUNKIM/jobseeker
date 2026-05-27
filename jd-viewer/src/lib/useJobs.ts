import { useEffect, useState } from 'react'
import type { Job } from '../types'

interface State {
  jobs: Job[]
  loading: boolean
  error: string | null
}

export function useJobs(): State {
  const [state, setState] = useState<State>({ jobs: [], loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    fetch('/all_jobs_enriched.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: Job[]) => {
        if (!cancelled) setState({ jobs: data, loading: false, error: null })
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
