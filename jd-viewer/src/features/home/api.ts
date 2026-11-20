import { apiGet, getJson } from '../../api/client'
import type { Site } from '../../types'
import { ALWAYS_DDAY } from './utils'

/**
 * 메인 화면(`/`) — backend `/api/home`. 모집중인 IT 공고를 회사별로 묶은 것.
 * API 가 없으면 회차마다 구운 `/home.json`(catch_capture store/jobs/home_export.py)으로 물러선다 —
 * 그 파일 하나로 규모·정렬·더보기를 화면에서 흉내 낸다. 회사 패널은 `/home_companies.json`(같은 회차에 굽는다).
 */

export type HomeSize = '대기업' | '중견기업' | '중소기업' | '해외 기업'

export interface HomeCompany {
  name: string
  slug: string
  logo: string | null
  size: HomeSize
  industry: string
  active: number
  /** 마감일 있는 공고가 하나도 없다(상시만) — 메인 카드에서 빠지고 `/top/always` 로 간다. 옛 스냅숏엔 없다. */
  always?: boolean
  entry: number
  experienced: number
  career_from: string | null
  career_to: string | null
  new_7d: number
  latest_at: string
  soonest_dday: number | null
  roles: string[]
  titles: { title: string; site: string; pid: string; career_bucket: string; dday: number | null }[]
}

export interface HomeJob {
  site: Site
  pid: string
  url: string
  title: string
  company: string
  company_slug: string
  logo: string | null
  size: HomeSize | null
  industry: string
  career: string | null
  career_bucket: string
  region: string | null
  district: string | null
  dday: number | null
  deadline: string | null
  first_seen_at: string
  roles: string[]
  stacks: string[]
  /** 인기 점수와 내역(backend home.service.score_parts) — 순위 구역에만 있다 */
  score?: number | null
  score_parts?: ScoreParts | null
}

export interface ScoreParts {
  size: number
  fresh: number
  hiring: number
  soon: number
  agency: number
}

export interface HomeBoard {
  generated_at: string
  /** 첫 화면 로고 띠 — 필터와 무관하게 공고가 많은 큰 회사 */
  spotlight: { name: string; slug: string; logo: string | null; size: HomeSize; active: number }[]
  totals: { companies: number; jobs: number; entry: number; experienced: number }
  facets: { sizes: { name: HomeSize; n: number }[]; industries: { name: string; n: number }[] }
  companies: HomeCompany[]
  /** 아래로 내리며 보는 구역 — TOP 50 의 앞 10건. 나머지는 fetchSection */
  sections: HomeSection[]
}

export interface HomeSection {
  key: string
  /** 구역 이름(신입·경력·은행·금융…) */
  title: string
  /** 순위 제목 앞말 — '신입 인기' → '신입 인기 TOP 50' */
  lead: string
  total: number
  jobs: HomeJob[]
}

export interface HomeCompanyDetail {
  company: HomeCompany
  careers: { bucket: string; n: number }[]
  jobs: HomeJob[]
}

export type HomeSort = 'popular' | 'new' | 'count'

/** API 가 없을 때 읽는 스냅숏. 한 번 받으면 들고 있는다(회차마다 바뀌는 파일). */
let snapshot: Promise<HomeBoard> | null = null
const loadSnapshot = (init?: RequestInit) => (snapshot ??= getJson<HomeBoard>('/home.json', init).catch((e) => {
  snapshot = null
  throw e
}))

const SIZE_RANK: Record<string, number> = { 대기업: 0, 중견기업: 1, '해외 기업': 2, 중소기업: 3 }

/** 상시 공고만 있는 회사(backend `is_always` 와 같은 문턱 — 마감일 없음이거나 1년 넘게 남음). */
export const isAlwaysCompany = (c: HomeCompany): boolean =>
  c.always ?? (c.soonest_dday == null || c.soonest_dday > ALWAYS_DDAY)

/** exclude = 메인(상시만 있는 회사를 뺀다), only = 상시 채용만. */
export type HomeAlways = '' | 'exclude' | 'only'

/** 스냅숏으로 `/api/home` 을 흉내 낸다 — 규모로 거르고, 정렬하고, limit 만큼. */
function fromSnapshot(d: HomeBoard, q: { size: string; sort: HomeSort; limit: number; always?: HomeAlways }): HomeBoard {
  const cos = d.companies.filter(
    (c) => (!q.size || c.size === q.size) && (!q.always || (q.always === 'only') === isAlwaysCompany(c)),
  )
  const by = {
    popular: (a: HomeCompany, b: HomeCompany) =>
      (SIZE_RANK[a.size] ?? 9) - (SIZE_RANK[b.size] ?? 9) || b.active - a.active || b.new_7d - a.new_7d,
    new: (a: HomeCompany, b: HomeCompany) => (b.latest_at > a.latest_at ? 1 : -1),
    count: (a: HomeCompany, b: HomeCompany) => b.active - a.active,
  }[q.sort]
  return {
    ...d,
    totals: { ...d.totals, companies: cos.length },
    companies: [...cos].sort(by).slice(0, q.limit),
    sections: d.sections.map((x) => ({ ...x, jobs: x.jobs.slice(0, 10) })),
  }
}

export async function fetchHome(
  q: { size: string; industry: string; sort: HomeSort; limit: number; always?: HomeAlways },
  init?: RequestInit,
): Promise<HomeBoard> {
  const p = new URLSearchParams({ sort: q.sort, limit: String(q.limit) })
  if (q.size) p.set('size', q.size)
  if (q.always) p.set('always', q.always)
  if (q.industry) p.set('industry', q.industry)
  try {
    return await apiGet<HomeBoard>(`/api/home?${p}`, init)
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    return fromSnapshot(await loadSnapshot(init), q)
  }
}

/** 회사 패널 스냅숏 — `{ companies: {대표 슬러그: 패널}, aliases: {다른 슬러그: 대표} }`. 카드를 눌러야 받는다. */
interface PanelSnapshot {
  companies: Record<string, HomeCompanyDetail>
  aliases: Record<string, string>
}
let panels: Promise<PanelSnapshot> | null = null
const loadPanels = (init?: RequestInit) => (panels ??= getJson<PanelSnapshot>('/home_companies.json', init).catch((e) => {
  panels = null
  throw e
}))

export async function fetchHomeCompany(slug: string, init?: RequestInit): Promise<HomeCompanyDetail> {
  try {
    return await apiGet<HomeCompanyDetail>(`/api/home/company/${encodeURIComponent(slug)}`, init)
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    // API 가 없으면 같은 회차에 구운 패널 파일로 — 예전엔 여기서 '불러오지 못함'이었다.
    const snap = await loadPanels(init)
    const hit = snap.companies[slug] ?? snap.companies[snap.aliases[slug] ?? '']
    if (!hit) throw e
    return hit
  }
}

export async function fetchSection(key: string, init?: RequestInit): Promise<HomeSection> {
  try {
    return await apiGet<HomeSection>(`/api/home/section/${encodeURIComponent(key)}`, init)
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    const sec = (await loadSnapshot(init)).sections.find((x) => x.key === key)
    if (!sec) throw e
    return sec
  }
}
