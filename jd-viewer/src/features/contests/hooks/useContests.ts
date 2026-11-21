import { useEffect, useState } from 'react'
import { fetchContests } from '../api'
import type { ContestsData } from '../utils/contests'

export function useContests() {
  const [state, setState] = useState<{ data: ContestsData | null; loading: boolean; error: string | null }>({
    data: null,
    loading: true,
    error: null,
  })
  useEffect(() => {
    const ctl = new AbortController()
    fetchContests({ signal: ctl.signal })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e: Error) => e.name !== 'AbortError' && setState({ data: null, loading: false, error: String(e) }))
    return () => ctl.abort()
  }, [])
  return state
}
