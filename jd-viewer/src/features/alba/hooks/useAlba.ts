import { useEffect, useState } from 'react'
import { fetchAlba } from '../api'
import type { AlbaData } from '../utils/alba'

export function useAlba() {
  const [state, setState] = useState<{ data: AlbaData | null; loading: boolean; error: string | null }>({
    data: null,
    loading: true,
    error: null,
  })
  useEffect(() => {
    const ctl = new AbortController()
    fetchAlba({ signal: ctl.signal })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e: Error) => e.name !== 'AbortError' && setState({ data: null, loading: false, error: String(e) }))
    return () => ctl.abort()
  }, [])
  return state
}
