import { useEffect, useState } from 'react'
import type { TechRelationsFile } from '../types'

interface State {
  data: TechRelationsFile | null
  loading: boolean
  error: string | null
}

export function useTechRelations(): State {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    fetch('/tech_relations.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: TechRelationsFile) => {
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
