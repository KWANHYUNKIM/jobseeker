import type { Job, Site } from '../types'
import { careerBucket } from './career'
import { classifyRoles } from './classify'

export interface FilterState {
  sites: Set<Site>
  careers: Set<string>
  stacks: Set<string>
  roles: Set<string>
  query: string
}

export function emptyFilter(): FilterState {
  return { sites: new Set(), careers: new Set(), stacks: new Set(), roles: new Set(), query: '' }
}

export function applyFilter(jobs: Job[], f: FilterState): Job[] {
  const q = f.query.trim().toLowerCase()
  return jobs.filter((j) => {
    if (f.sites.size && !f.sites.has(j.site)) return false
    if (f.careers.size && !f.careers.has(careerBucket(j.career))) return false
    if (f.roles.size) {
      // 직군은 제목+기술스택 기반으로 분류(국내·해외 동일 규칙). 하나라도 겹치면 통과.
      const roles = classifyRoles(j.title, j.tech_stack, j.qualifications || '')
      if (!roles.some((r) => f.roles.has(r))) return false
    }
    if (f.stacks.size) {
      const set = new Set(j.tech_stack.map((s) => s.toLowerCase()))
      for (const s of f.stacks) {
        if (!set.has(s.toLowerCase())) return false
      }
    }
    if (q) {
      const hay = (
        j.company +
        '\n' +
        j.title +
        '\n' +
        j.full_jd
      ).toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
}

export function roleCounts(jobs: Job[]): { name: string; count: number }[] {
  const c = new Map<string, number>()
  for (const j of jobs) {
    for (const r of classifyRoles(j.title, j.tech_stack, j.qualifications || '')) {
      c.set(r, (c.get(r) ?? 0) + 1)
    }
  }
  return [...c.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}

export function stackCounts(jobs: Job[]): { name: string; count: number }[] {
  const c = new Map<string, number>()
  for (const j of jobs) {
    const seen = new Set<string>()
    for (const t of j.tech_stack) {
      const key = t.trim()
      if (!key || seen.has(key)) continue
      seen.add(key)
      c.set(key, (c.get(key) ?? 0) + 1)
    }
  }
  return [...c.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}
