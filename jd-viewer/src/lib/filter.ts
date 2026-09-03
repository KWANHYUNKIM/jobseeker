import type { CompanySize, Job, Site } from '../types'
import { careerBucket } from './career'
import { classifyRoles } from './classify'
import { COMPANY_SIZES } from '../types'
import { REGION_OPTIONS, districtCounts, placeOf, type Place } from './region'

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

// placeOf / classifyRoles 는 정규식과 문자열 분해라 싸지 않은데, 칩 건수를 축마다
// 세면서 같은 공고를 수십 번 다시 보게 됐다. 공고 객체는 한 번 로드된 뒤 바뀌지
// 않으므로 객체 자체를 키로 캐시한다.
const placeCache = new WeakMap<object, Place>()
const rolesCache = new WeakMap<object, string[]>()

function place(j: Job): Place {
  let p = placeCache.get(j)
  if (!p) {
    p = placeOf(j)
    placeCache.set(j, p)
  }
  return p
}

function rolesOf(j: Job): string[] {
  let r = rolesCache.get(j)
  if (!r) {
    r = classifyRoles(j.title, j.tech_stack, j.qualifications || '')
    rolesCache.set(j, r)
  }
  return r
}

/** 고를 수 있는 필터 축. 칩 건수를 "자기 축만 빼고" 세기 위해 축별로 분리해 둔다. */
export type FacetKey = 'sites' | 'regions' | 'districts' | 'sizes' | 'careers' | 'roles' | 'stacks'

const DIMENSIONS: Record<FacetKey, (j: Job, f: FilterState) => boolean> = {
  sites: (j, f) => !f.sites.size || f.sites.has(j.site),
  regions: (j, f) => !f.regions.size || f.regions.has(place(j).region),
  districts: (j, f) => {
    if (!f.districts.size) return true
    const d = place(j).district
    return !!d && f.districts.has(d)
  },
  sizes: (j, f) => !f.sizes.size || !!(j.company_size && f.sizes.has(j.company_size)),
  careers: (j, f) => !f.careers.size || f.careers.has(careerBucket(j.career)),
  roles: (j, f) => !f.roles.size || rolesOf(j).some((r) => f.roles.has(r)),
  stacks: (j, f) => {
    if (!f.stacks.size) return true
    const set = new Set(j.tech_stack.map((s) => s.toLowerCase()))
    for (const s of f.stacks) {
      if (!set.has(s.toLowerCase())) return false
    }
    return true
  },
}

const FACET_KEYS = Object.keys(DIMENSIONS) as FacetKey[]

/** 모집 상태와 검색어. 어떤 축의 건수를 세든 **언제나** 적용된다. */
function matchesBase(j: Job, f: FilterState, q: string): boolean {
  const isClosed = j.status === 'closed'
  if (f.closed === 'hide' && isClosed) return false
  if (f.closed === 'only' && !isClosed) return false
  if (q) {
    const hay = (j.company + '\n' + j.title + '\n' + j.full_jd).toLowerCase()
    if (!hay.includes(q)) return false
  }
  return true
}

export function applyFilter(jobs: Job[], f: FilterState): Job[] {
  const q = f.query.trim().toLowerCase()
  return jobs.filter(
    (j) => matchesBase(j, f, q) && FACET_KEYS.every((k) => DIMENSIONS[k](j, f)),
  )
}

export interface Facets {
  /** 고정 목록으로 그리는 축은 이름→건수 맵으로 준다(칩 순서는 화면이 정한다). */
  siteCount: Map<string, number>
  careerCount: Map<string, number>
  regions: { name: string; count: number }[]
  districts: { name: string; count: number }[]
  sizes: { name: CompanySize; count: number }[]
  roles: { name: string; count: number }[]
  stacks: { name: string; count: number }[]
}

/**
 * 필터 칩에 붙는 건수.
 *
 * 각 축은 **자기 자신을 뺀 나머지 필터**를 적용한 결과로 센다. 그래야 숫자가
 * "이걸 누르면 몇 건이 되는지"를 뜻한다. 자기 축까지 적용하면 고르지 않은 칩이
 * 전부 0 이 되어 쓸모가 없고, 아무 축도 적용하지 않으면(예전 동작) 목록은 모집중
 * 3,000건인데 칩은 마감까지 합친 10,000건을 말하는 상태가 된다.
 *
 * 모집 상태와 검색어는 어느 축에서도 빼지 않는다 — 그 둘은 고르는 축이 아니라
 * "지금 보고 있는 모집단" 자체를 정하는 조건이다.
 */
export function computeFacets(jobs: Job[], f: FilterState): Facets {
  const q = f.query.trim().toLowerCase()
  const base = jobs.filter((j) => matchesBase(j, f, q))
  const except = (skip: FacetKey, also?: FacetKey) =>
    base.filter((j) =>
      FACET_KEYS.every((k) => k === skip || k === also || DIMENSIONS[k](j, f)),
    )

  const countBy = <T extends string>(rows: Job[], pick: (j: Job) => T | null | undefined) => {
    const c = new Map<string, number>()
    for (const j of rows) {
      const v = pick(j)
      if (v) c.set(v, (c.get(v) ?? 0) + 1)
    }
    return c
  }

  // 지역 건수를 셀 때는 시군구도 같이 뺀다 — 시군구는 지역에 딸린 축이라,
  // '서울 강남구'를 고른 채로 다른 시도를 세면 전부 0 이 된다.
  const regionCount = countBy(except('regions', 'districts'), (j) => place(j).region)
  const sizeCount = countBy(except('sizes'), (j) => j.company_size)

  // 지역·규모 칩은 0건이어도 목록에서 빼지 않는다. 데이터에 존재하는 축은 그대로
  // 두고 숫자만 0 으로 보여야, 모집 상태를 바꿀 때 칩이 나타났다 사라지며 자리가
  // 흔들리지 않는다. '경기는 지금 마감뿐' 이라는 사실 자체도 정보다.
  const presentRegions = new Set(jobs.map((j) => place(j).region))
  const presentSizes = new Set(jobs.map((j) => j.company_size).filter(Boolean))

  return {
    siteCount: countBy(except('sites'), (j) => j.site),
    careerCount: countBy(except('careers'), (j) => careerBucket(j.career)),
    regions: REGION_OPTIONS.filter((name) => presentRegions.has(name)).map((name) => ({
      name,
      count: regionCount.get(name) ?? 0,
    })),
    // 시군구는 지역을 딱 하나 골랐을 때만 뜻이 있다(Sidebar 와 같은 규칙).
    districts:
      f.regions.size === 1
        ? districtCounts(except('districts'), [...f.regions][0])
        : [],
    sizes: COMPANY_SIZES.filter((name) => presentSizes.has(name)).map((name) => ({
      name,
      count: sizeCount.get(name) ?? 0,
    })),
    roles: roleCounts(except('roles')),
    stacks: stackCounts(except('stacks')),
  }
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
