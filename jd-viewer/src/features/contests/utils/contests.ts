// IT·디자인 공모전 — public/contests.json 의 모양과 화면 규칙.
//
// 크롤러(catch_capture/crawlers/crawl_contests.py)가 씽굿·위비티·콘테스트코리아에서 컴퓨터로 하는
// 공모전만 골라 요약 칸만 싣는다 — 제목·주최·우리 분류·상금(짧게)·접수 기간·참가 대상·원문 주소.
// 요강 본문·포스터·연락처는 없다(씽굿 약관 제24조). 자세한 요강과 접수는 언제나 원문에서 한다.

export type ContestStatus = 'open' | 'closed'

export type Contest = {
  id: string
  source: string
  url: string
  title: string
  host: string
  category: string
  prize: string
  target: string
  period_start: string | null
  period_end: string | null
  status: ContestStatus
  closed_at?: string
  closed_reason?: string
  /** 다른 출처에 같은 공모전이 먼저 올라와 있으면 그쪽 id(둘 다 싣고, 목록에는 대표만 보인다). */
  dup_of?: string
  first_seen_at: string
  last_seen_at: string
}

export type ContestsData = {
  updated_at: string
  started_at?: string
  sources: Record<string, string>
  categories: string[]
  contests: Contest[]
}

/** 'all' 이 기본이다 — 마감한 공모전도 목록에 남기고 빨간 '마감'만 붙인다(사용자 결정 2026-11-21). */
export type StatusFilter = 'all' | 'open' | 'closed'

export type ContestFilter = { status: StatusFilter; category: string | null; source: string | null }

export const ALL_FILTER: ContestFilter = { status: 'all', category: null, source: null }

/** 오늘(KST) 'YYYY-MM-DD'. */
export function todayKst(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(now)
}

/**
 * 화면에서 보는 상태 — 받은 status 가 open 이어도 마감일이 지났으면 닫는다.
 * 수집이 멈춰 파일이 낡아도 날짜 지난 공모전이 '모집중'에 남지 않게(useJobs 와 같은 규칙).
 */
export function statusOf(c: Contest, today: string): ContestStatus {
  if (c.status === 'closed') return 'closed'
  return c.period_end && c.period_end < today ? 'closed' : 'open'
}

/** 대표 id → 같은 공모전의 다른 출처들. */
export function dupsByRep(rows: Contest[]): Map<string, Contest[]> {
  const ids = new Set(rows.map((c) => c.id))
  const m = new Map<string, Contest[]>()
  for (const c of rows) {
    if (!c.dup_of || !ids.has(c.dup_of)) continue
    m.set(c.dup_of, [...(m.get(c.dup_of) ?? []), c])
  }
  return m
}

/** 목록에 한 줄로 설 것 — 출처를 고르지 않았으면 사본(대표가 데이터에 있는 dup_of)은 뺀다. */
function visible(c: Contest, ids: Set<string>, f: ContestFilter): boolean {
  if (f.source) return c.source === f.source
  return !(c.dup_of && ids.has(c.dup_of))
}

const statusOk = (c: Contest, s: StatusFilter, today: string) => s === 'all' || statusOf(c, today) === s

/**
 * 걸러 낸 공모전 — 상태 → 분류 → 출처. 모집중이 먼저(마감 가까운 순, 마감일 모름은 뒤),
 * 마감은 그 뒤(최근에 마감한 것부터).
 */
export function filterContests(rows: Contest[], f: ContestFilter, today: string): Contest[] {
  const ids = new Set(rows.map((c) => c.id))
  return rows
    .filter((c) => visible(c, ids, f) && statusOk(c, f.status, today) && (!f.category || c.category === f.category))
    .sort((a, b) => {
      const sa = statusOf(a, today)
      const sb = statusOf(b, today)
      if (sa !== sb) return sa === 'open' ? -1 : 1
      const ea = a.period_end ?? (sa === 'open' ? '9999-12-31' : '0000-01-01')
      const eb = b.period_end ?? (sb === 'open' ? '9999-12-31' : '0000-01-01')
      return (sa === 'open' ? ea.localeCompare(eb) : eb.localeCompare(ea)) || a.id.localeCompare(b.id)
    })
}

/** 칩 옆 숫자 — 지금 고른 상태와 다른 축 안에서 센다. */
export function countBy(rows: Contest[], key: 'category' | 'source', f: ContestFilter, today: string): Map<string, number> {
  const ids = new Set(rows.map((c) => c.id))
  const m = new Map<string, number>()
  for (const c of rows) {
    if (!statusOk(c, f.status, today)) continue
    if (key === 'category' && !visible(c, ids, f)) continue
    if (key === 'category' && f.source && c.source !== f.source) continue
    if (key === 'source' && f.category && c.category !== f.category) continue
    const k = c[key]
    m.set(k, (m.get(k) ?? 0) + 1)
  }
  return m
}

/** 'D-7' · 'D-day'. 마감일을 모르거나 지났으면 ''. */
export function ddayLabel(end: string | null, today: string): string {
  if (!end) return ''
  const days = Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000)
  if (Number.isNaN(days) || days < 0) return ''
  return days === 0 ? 'D-day' : `D-${days}`
}

/** '11.20' */
export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  return m ? `${Number(m[2])}.${Number(m[3])}` : ''
}

/** '10.19 ~ 11.22' — 해가 바뀌면 연도를 붙인다. */
export function periodLabel(c: Pick<Contest, 'period_start' | 'period_end'>, today: string): string {
  const y = today.slice(0, 4)
  const one = (d: string | null) => (d ? (d.slice(0, 4) === y ? dayLabel(d) : `${d.slice(2, 4)}.${dayLabel(d)}`) : '')
  const s = one(c.period_start)
  const e = one(c.period_end)
  return s && e ? `${s} ~ ${e}` : e ? `~ ${e}` : s ? `${s} ~` : ''
}
