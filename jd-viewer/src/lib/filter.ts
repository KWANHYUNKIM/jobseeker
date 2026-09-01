import type { CompanySize, Job, Site } from '../types'
import { careerBucket } from './career'
import { classifyRoles } from './classify'
import { placeOf } from './region'

export interface FilterState {
  sites: Set<Site>
  careers: Set<string>
  stacks: Set<string>
  roles: Set<string>
  // 근무 지역(시도) 과 그 아래 시군구. 시군구는 지역을 하나만 골랐을 때만 뜬다 —
  // 서울 강남과 서울 금천은 같은 '서울'이어도 통근이 전혀 다른 자리다.
  regions: Set<string>
  districts: Set<string>
  // 회사 규모(대기업/중견기업/중소기업). useJobs 가 붙여 준 company_size 를 본다.
  sizes: Set<CompanySize>
  query: string
  // 마감 공고 취급. 기본은 'hide' — 목록에 섞여 있으면 지원할 수 없는 자리를 계속
  // 클릭하게 된다. 'only' 는 지난 공고만, 'show' 는 함께 보되 배지로 구분한다.
  // 어느 쪽이든 데이터에서 지우지는 않는다(검색·색인은 그대로).
  closed: 'hide' | 'show' | 'only'
}

export function emptyFilter(): FilterState {
  return {
    sites: new Set(), careers: new Set(), stacks: new Set(), roles: new Set(),
    regions: new Set(), districts: new Set(), sizes: new Set(),
    query: '', closed: 'hide',
  }
}

export function applyFilter(jobs: Job[], f: FilterState): Job[] {
  const q = f.query.trim().toLowerCase()
  return jobs.filter((j) => {
    const isClosed = j.status === 'closed'
    if (f.closed === 'hide' && isClosed) return false
    if (f.closed === 'only' && !isClosed) return false
    if (f.sites.size && !f.sites.has(j.site)) return false
    if (f.regions.size || f.districts.size) {
      const p = placeOf(j)
      if (f.regions.size && !f.regions.has(p.region)) return false
      if (f.districts.size && (!p.district || !f.districts.has(p.district))) return false
    }
    if (f.sizes.size && !(j.company_size && f.sizes.has(j.company_size))) return false
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


/**
 * 검색 API 결과에 덧씌우는 후처리 필터.
 *
 * 의미 검색이 켜지면 목록은 API 가 매긴 순서를 그대로 쓰므로 applyFilter 를 타지
 * 않는다. 그런데 API 는 지역·규모 축을 모른다 — 그대로 두면 지역을 골라도 검색
 * 중에는 무시되는 것처럼 보인다. API 가 이미 거른 축(사이트·경력·스택)은 다시
 * 건드리지 않고, 화면에서만 아는 두 축만 여기서 건다.
 */
export function applyLocalFacets(jobs: Job[], f: FilterState): Job[] {
  if (!f.regions.size && !f.districts.size && !f.sizes.size) return jobs
  return jobs.filter((j) => {
    if (f.sizes.size && !(j.company_size && f.sizes.has(j.company_size))) return false
    if (!f.regions.size && !f.districts.size) return true
    const p = placeOf(j)
    if (f.regions.size && !f.regions.has(p.region)) return false
    if (f.districts.size && (!p.district || !f.districts.has(p.district))) return false
    return true
  })
}
