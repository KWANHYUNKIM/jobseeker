import { useEffect, useState } from 'react'
import type { BlogFile } from '../types'

interface State {
  data: BlogFile | null
  loading: boolean
  error: string | null
}

const EMPTY: BlogFile = {
  generated_at: '',
  total: 0,
  sources: [],
  categories: [],
  tag_categories: {},
  posts: [],
}

export function useBlogs(): State {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    fetch('/tech_blogs.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: BlogFile) => {
        if (!cancelled) setState({ data: data ?? EMPTY, loading: false, error: null })
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
