// 컴퓨터 알바 모음 — public/alba.json 의 모양과 화면 규칙.
//
// 크롤러(catch_capture/crawlers/crawl_alba.py, 출처별 crawlers/alba/*)가 당근알바·알바천국·알바몬·사람인·잡코리아에서
// 컴퓨터로 하는 일만 골라 요약 칸만 싣는다 — 제목·급여·시/도·시/군/구·고용 형태·근무 시간·등록일·마감일·원문 주소.
// 본문·상호·연락처는 없다. 그래서 이 화면에는 상세가 없고, 자세히 보기와 지원은 언제나 원문에서 한다.

export type AlbaPay = { amount: number | null; unit: string; text: string }

/** 출처 — 크롤러의 SOURCE_ORDER 와 같은 순서(화면 칩 순서). */
export type AlbaSource = 'daangn' | 'albacheonguk' | 'albamon' | 'saramin' | 'jobkorea'

export const SOURCE_ORDER: AlbaSource[] = ['daangn', 'albacheonguk', 'albamon', 'saramin', 'jobkorea']

/** 데이터에 source_labels 가 없을 때(옛 파일) 쓰는 이름. */
export const SOURCE_LABELS: Record<AlbaSource, string> = {
  daangn: '당근',
  albacheonguk: '알바천국',
  albamon: '알바몬',
  saramin: '사람인',
  jobkorea: '잡코리아',
}

export type AlbaPost = {
  /** `<출처>-<원본 번호>` — 출처 사이에서 겹치지 않는다. */
  id: string
  /** 옛 파일(당근만 있던 때)에는 없다 — 그러면 당근이다. */
  source?: AlbaSource
  url: string
  title: string
  category: string
  pay: AlbaPay | null
  sido: string
  sigungu: string
  employment: string
  hours: string
  posted_at: string | null
  /** 원본이 준 접수 마감일(YYYY-MM-DD). 당근은 없다. */
  deadline?: string | null
  /** 제목+지역이 같은 공고의 대표 id — 둘 다 목록에 남기고 '같은 공고' 표시만 한다. */
  dup_of?: string
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
  source?: { ok: boolean; sitemap?: number; new?: number; rechecked?: number; closed_now?: number; failed?: string[] }
  /** 출처별 마지막 회차 결과. */
  sources?: Record<string, { ok: boolean; at?: string; label?: string; total?: number; open?: number }>
  source_labels?: Partial<Record<AlbaSource, string>>
  categories: string[]
  posts: AlbaPost[]
}

/** 'all' 이 기본이다 — 마감된 공고도 목록에 남기고 옆에 '마감'만 붙인다(사용자 요청 2026-11-21). */
export type StatusFilter = 'all' | 'open' | 'closed'

export type AlbaFilter = { status: StatusFilter; category: string | null; sido: string | null; source: AlbaSource | null }

export const ALL_FILTER: AlbaFilter = { status: 'all', category: null, sido: null, source: null }

const statusOk = (p: AlbaPost, s: StatusFilter) => s === 'all' || p.status === s

export const sourceOf = (p: AlbaPost): AlbaSource => p.source ?? 'daangn'

export function sourceLabel(src: AlbaSource, labels?: AlbaData['source_labels']): string {
  return labels?.[src] ?? SOURCE_LABELS[src] ?? src
}

type Axis = 'category' | 'sido' | 'source'

/** 축 하나를 뺀 나머지 선택에 맞는가 — 칩 옆 숫자는 '그 칩을 누르면 몇 건'이다. */
function matches(p: AlbaPost, f: AlbaFilter, skip?: Axis): boolean {
  return (
    statusOk(p, f.status) &&
    (skip === 'category' || !f.category || p.category === f.category) &&
    (skip === 'sido' || !f.sido || p.sido === f.sido) &&
    (skip === 'source' || !f.source || sourceOf(p) === f.source)
  )
}

/** 걸러 낸 공고 — 상태 → 출처 → 분류 → 시/도. 모집중이 먼저, 그 안에서 등록일 최신순(없으면 처음 본 날). */
export function filterPosts(posts: AlbaPost[], f: AlbaFilter): AlbaPost[] {
  return posts
    .filter((p) => matches(p, f))
    .sort(
      (a, b) =>
        Number(a.status === 'closed') - Number(b.status === 'closed') || postedKey(b).localeCompare(postedKey(a)),
    )
}

export const postedKey = (p: AlbaPost) => p.posted_at ?? p.first_seen_at

/** 축별 건수 — 다른 축의 선택(상태 포함) 안에서 센다(칩 옆 숫자). */
export function countBy(posts: AlbaPost[], key: Axis, f: AlbaFilter): Map<string, number> {
  const m = new Map<string, number>()
  for (const p of posts) {
    if (!matches(p, f, key)) continue
    const k = key === 'source' ? sourceOf(p) : p[key] || '지역 미상'
    m.set(k, (m.get(k) ?? 0) + 1)
  }
  return m
}

/** '건당 40,000원' — 원본 표기가 있으면 그것을, 없으면 단위 + 금액.
 *  사람인 목록은 급여를 주지 않는다 — 그때는 '협의'가 아니라 원문을 보라고 한다. */
export function payLabel(pay: AlbaPay | null, source?: AlbaSource): string {
  if (!pay || !pay.amount) return source === 'saramin' ? '급여 원문 확인' : '급여 협의'
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

/** '~12.3 마감' — 모집중 공고에만 쓴다(마감한 것은 '마감' 표시가 따로 있다). */
export function deadlineLabel(p: AlbaPost): string {
  if (p.status !== 'open' || !p.deadline) return ''
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(p.deadline)
  return m ? `~${Number(m[1])}.${Number(m[2])} 마감` : ''
}
