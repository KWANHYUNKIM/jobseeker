import { useEffect, useState } from 'react'
import type { RadarFile } from '../types'

interface State {
  data: RadarFile | null
  loading: boolean
  error: string | null
}

export function useRadar(): State {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    fetch('/company_tech_radar.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: RadarFile) => {
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
