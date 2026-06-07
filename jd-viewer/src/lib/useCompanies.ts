import { useEffect, useState } from 'react'
import type { CompanyStack, CompanyStacksFile } from '../types'

interface State {
  companies: CompanyStack[]
  meta: Omit<CompanyStacksFile, 'companies'> | null
  loading: boolean
  error: string | null
}

export function useCompanies(): State {
  const [state, setState] = useState<State>({
    companies: [],
    meta: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    fetch('/company_stacks.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: CompanyStacksFile) => {
        if (cancelled) return
        const { companies, ...meta } = data
        setState({ companies, meta, loading: false, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ companies: [], meta: null, loading: false, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
