import { useEffect, useState } from 'react'

// public/role_insights.json — bin/build_role_insights.py 가 생성
export interface NameCount {
  name: string
  count: number
}
export interface KwCount {
  kw: string
  count: number
}
export interface RoleInsight {
  role: string
  count: number
  industries: NameCount[]
  career: NameCount[]
  years: NameCount[]
  education: NameCount[]
  tech: NameCount[]
  preferences: KwCount[]
  qualifications: KwCount[]
}
export interface RoleInsightsFile {
  generated_at: string
  total_jobs: number
  roles: RoleInsight[]
}

export function useRoleInsights() {
  const [data, setData] = useState<RoleInsightsFile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/role_insights.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - role_insights.json`)
        return r.json()
      })
      .then((d: RoleInsightsFile) => {
        if (!cancelled) {
          setData(d)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { data, loading, error }
}
