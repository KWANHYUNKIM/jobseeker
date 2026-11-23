import { useEffect, useState } from 'react'
import { docFetch } from '../../../api/client'

// 직무 역설계(공고 한 줄씩 읽기) — engine/roles 가 쓰는 public/roles/{index.json, items/<id>.json}.
// index 의 jobs 가 공고 키(site-pid) → 풀이 id 다. 같은 자리가 여러 사이트에 올라와도 풀이는 하나.

export type RoleSection = 'task' | 'qualification' | 'preference'

export interface RoleLine {
  section: RoleSection
  quote: string
  short: string
  why: string
  actually?: { intro?: string; items: string[] }
  level?: { basic: string; work: string; team: string }
  flows?: { caption: string; steps: string[]; mine_from?: number }[]
  examples?: { title: string; body: string; lang?: string; code?: string }[]
  how_far?: string
  refs?: number[]
  study?: string[]
}

export interface RoleResource {
  id: string
  title: string
  by?: string
  kind: 'book' | 'course' | 'doc' | 'video' | 'internal'
  url: string
  lang: 'ko' | 'en'
  free?: boolean
  level: '입문' | '실무' | '심화'
  why: string
}

export interface RoleStudyStep {
  title: string
  time?: string
  goal: string
  task: string
  resources: string[]
}

export interface RoleSource {
  n: number
  title: string
  url: string
  kind: 'company' | 'posting' | 'news' | 'reference' | 'community'
  date?: string
  note?: string
}

export interface RoleReading {
  id: string
  company: string
  role: string
  team?: string
  jobs: string[]
  researched_at: string
  tldr: { what: string; env: string; oneline: string }
  lines: RoleLine[]
  fit?: { good: string[]; hard: string[] }
  interview?: { q: string; a: string }[]
  sources: RoleSource[]
  resources?: RoleResource[]
  study_path?: RoleStudyStep[]
  pay?: RolePay
  benefits?: { items: { name: string; detail: string }[]; note?: string }
  location?: RoleLocation
  caveat?: string
}

export interface RolePay {
  summary: string
  /** amount — 만원 단위 숫자(막대 길이). peer — 다른 회사 비교 줄(회색 막대). */
  rows: { label: string; value: string; amount?: number; peer?: boolean; basis: string; note?: string }[]
  how?: string
}

export interface RoleLocation {
  name: string
  address: string
  postal?: string
  map_url?: string
  near?: string
  note?: string
}

interface RoleIndex {
  jobs: Record<string, string>
}

let indexPromise: Promise<RoleIndex> | null = null
const itemCache = new Map<string, Promise<RoleReading | null>>()

function loadIndex(): Promise<RoleIndex> {
  if (!indexPromise) {
    indexPromise = docFetch('/roles/index.json')
      .then((r) => (r.ok ? (r.json() as Promise<RoleIndex>) : { jobs: {} }))
      .catch(() => ({ jobs: {} }))
  }
  return indexPromise
}

function loadItem(id: string): Promise<RoleReading | null> {
  let p = itemCache.get(id)
  if (!p) {
    p = docFetch(`/roles/items/${id}.json`)
      .then((r) => (r.ok ? (r.json() as Promise<RoleReading>) : null))
      .catch(() => null)
    itemCache.set(id, p)
  }
  return p
}

/** 공고 키(site-pid)의 풀이. 없으면 null — 화면은 풀이 없이 원래대로 그린다. */
export function useRoleReading(jobKey: string | null): RoleReading | null {
  const [state, setState] = useState<{ key: string | null; data: RoleReading | null }>({ key: null, data: null })
  useEffect(() => {
    if (!jobKey) return
    let alive = true
    loadIndex()
      .then((ix) => (ix.jobs[jobKey] ? loadItem(ix.jobs[jobKey]) : null))
      .then((data) => {
        if (alive) setState({ key: jobKey, data })
      })
    return () => {
      alive = false
    }
  }, [jobKey])
  return state.key === jobKey ? state.data : null
}
