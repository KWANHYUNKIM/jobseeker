import { useEffect, useState } from 'react'
import type { TrendsFile } from '../../../types'
import { docFetch } from '../../../api/client'

interface State {
  data: TrendsFile | null
  loading: boolean
  error: string | null
}

export function useTrends(): State {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    docFetch('/trends.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: TrendsFile) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ data: null, loading: false, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
