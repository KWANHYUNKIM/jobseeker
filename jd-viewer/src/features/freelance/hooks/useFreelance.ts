import { useEffect, useState } from 'react'
import { fetchFreelance } from '../api'
import type { FreelanceData } from '../utils/freelance'

export function useFreelance() {
  const [state, setState] = useState<{ data: FreelanceData | null; loading: boolean; error: string | null }>({
    data: null,
    loading: true,
    error: null,
  })
  useEffect(() => {
    let cancelled = false
    fetchFreelance()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((e) => !cancelled && setState({ data: null, loading: false, error: String(e) }))
    return () => {
      cancelled = true
    }
  }, [])
  return state
}
