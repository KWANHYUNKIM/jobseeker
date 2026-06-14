import { useEffect, useState } from 'react'
import type { CalendarFile } from '../types'

interface State {
  data: CalendarFile | null
  loading: boolean
  error: string | null
}

export function useCalendar(): State {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    fetch('/job_calendar.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: CalendarFile) => {
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
