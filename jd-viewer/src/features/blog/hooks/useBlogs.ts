import { useEffect, useState } from 'react'
import type { BlogFile } from '../../../types'
import { fetchBlogs } from '../api'

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
    fetchBlogs()
      .then((data) => {
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
