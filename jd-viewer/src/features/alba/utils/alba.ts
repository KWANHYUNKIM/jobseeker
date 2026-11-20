// 당근알바 IT 공고 — public/alba.json 의 모양과 화면 규칙.
//
// 크롤러(catch_capture/crawlers/crawl_daangn_alba.py)가 약관 때문에 요약 칸만 싣는다 —
// 제목·급여·시/도·시/군/구·고용 형태·근무 시간·등록일·원문 주소. 본문·상호·연락처는 없다.
// 그래서 이 화면에는 상세가 없고, 자세히 보기와 지원은 언제나 원문에서 한다.

export type AlbaPay = { amount: number | null; unit: string; text: string }

export type AlbaPost = {
  id: string
  url: string
  title: string
  category: string
  pay: AlbaPay | null
  sido: string
  sigungu: string
  employment: string
  hours: string
  posted_at: string | null
  first_seen_at: string
  last_seen_at: string
  checked_at?: string
  status: 'open' | 'closed'
  closed_at?: string
  closed_reason?: string
}

export type AlbaData = {
  updated_at: string
  started_at?: string
  source?: { ok: boolean; sitemap?: number; new?: number; rechecked?: number; closed_now?: number }
  categories: string[]
  posts: AlbaPost[]
}

export type StatusFilter = 'open' | 'closed'

export type AlbaFilter = { status: StatusFilter; category: string | null; sido: string | null }

export const ALL_FILTER: AlbaFilter = { status: 'open', category: null, sido: null }

/** 걸러 낸 공고 — 상태 → 분류 → 시/도. 순서는 등록일 최신순(없으면 처음 본 날). */
export function filterPosts(posts: AlbaPost[], f: AlbaFilter): AlbaPost[] {
  return posts
    .filter((p) => p.status === f.status && (!f.category || p.category === f.category) && (!f.sido || p.sido === f.sido))
    .sort((a, b) => postedKey(b).localeCompare(postedKey(a)))
}

export const postedKey = (p: AlbaPost) => p.posted_at ?? p.first_seen_at

/** 분류별 건수 — 지금 고른 상태·지역 안에서 센다(칩 옆 숫자). */
export function countBy(posts: AlbaPost[], key: 'category' | 'sido', f: AlbaFilter): Map<string, number> {
  const m = new Map<string, number>()
  for (const p of posts) {
    if (p.status !== f.status) continue
    if (key === 'category' && f.sido && p.sido !== f.sido) continue
    if (key === 'sido' && f.category && p.category !== f.category) continue
    const k = p[key] || '지역 미상'
    m.set(k, (m.get(k) ?? 0) + 1)
  }
  return m
}

/** '건당 40,000원' — 원본 표기가 있으면 그것을, 없으면 단위 + 금액. */
export function payLabel(pay: AlbaPay | null): string {
  if (!pay || !pay.amount) return '급여 협의'
  if (pay.text) return pay.text
  return `${pay.unit} ${pay.amount.toLocaleString()}원`.trim()
}

/** '11.20' — 등록일(KST). */
export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const d = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date(t))
  return `${Number(d.slice(5, 7))}.${Number(d.slice(8, 10))}`
}
