
// 외주·프리 화면 두 개(프로젝트 목록 · 단가 분석)가 함께 쓰는 모양과 도구.
// 데이터: public/freelance.json — catch_capture/crawlers/crawl_freelance.py 가 누적하고,
// 등급·유형·분야·직무 분류와 단가 분석은 catch_capture/pipeline/freelance_rates.py 가 붙인다.

export interface Budget {
  type: 'monthly' | 'total'
  min: number | null
  max: number | null
}

export interface HistoryEntry {
  at: string
  budget: Budget | null
  status: 'active' | 'closed'
  duration: string
  applicants: number | null
}

export type Grade = '초급' | '중급' | '고급' | '특급'
export const GRADES: Grade[] = ['초급', '중급', '고급', '특급']

export interface Project {
  id: string
  site: string
  url: string
  title: string
  category: string
  kind: 'onsite' | 'remote' | ''
  location: string
  budget: Budget | null
  duration: string
  start: string
  skills: string[]
  career: string
  posted_date: string | null
  deadline: string | null
  applicants: number | null
  summary: string
  tags: string[]
  status: 'active' | 'closed'
  closed_reason?: string
  history?: HistoryEntry[]
  first_seen_at: string
  last_seen_at: string
  // freelance_rates.classify
  grade?: Grade | '혼합' | null
  grade_basis?: '표기' | '경력 추정' | null
  domain?: string
  work_type?: 'SI' | 'SM' | null
  role?: string | null
}

export interface Trend {
  weekly: { week: string; n: number; median: number | null; onsite: number | null; remote: number | null }[]
  by_skill: { skill: string; n: number; median: number; min: number; max: number }[]
  budget_moves: { id: string; title: string; from: number; to: number; pct: number; at: string }[]
}

export interface Stat {
  n: number
  p25: number
  median: number
  p75: number
  min: number
  max: number
}

export interface MatrixRow {
  key: string
  total: Stat
  grades: Partial<Record<Grade, Stat>>
}

export interface Analysis {
  meta: {
    monthly: number
    graded: number
    explicit: number
    inferred: number
    mixed: number
    ungraded: number
    sites: Record<string, number>
  }
  grades: Record<Grade, Stat | null>
  grades_explicit: Record<Grade, Stat | null>
  by_type: MatrixRow[]
  by_domain: MatrixRow[]
  by_role: MatrixRow[]
  by_mode: MatrixRow[]
  insights: string[]
  /** 현재 단가표 — 최근 N일 안에 본 자리. 칸마다 근거가 된 프로젝트 id 를 싣는다. */
  current?: {
    since: string
    until: string
    days: number
    cols: string[]
    table: Record<Grade, Record<string, (Stat & { ids: string[] }) | null>>
  }
  /** 월별 코호트 — 그 달에 올라온 자리의 '올라올 때 단가'. */
  monthly?: { month: string; n: number; grades: Partial<Record<Grade, Stat>> }[]
  /** 주별·월별 코호트를 등급별로, '분야|유형' 조합마다(전체 포함). */
  cohorts?: Record<'week' | 'month', Record<string, CohortRow[]>>
  domains?: string[]
}

export interface CohortRow {
  period: string
  n: number
  grades: Partial<Record<Grade, Stat>>
}

/** 그날의 현재 단가표(숫자만). 크롤러가 날짜별로 한 줄씩 쌓는다. */
export interface RateSnapshot {
  date: string
  cells: Partial<Record<Grade, Record<string, { n: number; p25: number; median: number; p75: number }>>>
}

/** 올라올 때의 월 단가(만원) — 분석 모듈(_first_monthly)과 같은 규칙. */
export function firstMonthly(p: Project): number | null {
  const v = monthlyMid(p.history?.[0]?.budget ?? p.budget)
  return v != null && v >= 150 && v <= 3000 ? v : null
}

export interface FreelanceData {
  updated_at: string
  started_at?: string
  sources: Record<string, { ok: boolean; fetched: number; error?: string }>
  trend?: Trend
  analysis?: Analysis
  rate_history?: RateSnapshot[]
  projects: Project[]
}

export const SITE_KO: Record<string, string> = {
  wanted_gigs: '원티드 긱스',
  freemoa: '프리모아',
  elancer: '이랜서',
  jobkorea: '잡코리아',
  saramin: '사람인',
  imjob: '아임잡',
  sism: 'SISM',
}

// 목록 앞쪽만 훑는 소스라 '이번에 안 보였다'가 곧 마감은 아니다. 그래도 2주째 안 보이면
// 내려갔을 가능성이 크니 모집중에서는 뺀다(데이터에서는 지우지 않는다). DB 의 project_state 와 같은 값.
export const STALE_DAYS = 14

export function todayKst(): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())
}

export function won(n: number): string {
  return n.toLocaleString()
}

export function budgetLabel(b: Budget | null): string {
  if (!b || (!b.min && !b.max)) return '단가 협의'
  const lo = b.min ?? b.max!
  const hi = b.max ?? b.min!
  const range = lo === hi ? `${won(lo)}만원` : `${won(lo)}~${won(hi)}만원`
  return b.type === 'monthly' ? `월 ${range}` : `총 ${range}`
}

/** 월 단가 가운데 값(만원). 월 단가가 아니면 null. */
export function monthlyMid(b: Budget | null): number | null {
  if (!b || b.type !== 'monthly') return null
  const lo = b.min ?? b.max
  const hi = b.max ?? b.min
  return lo != null && hi != null ? (lo + hi) / 2 : null
}

/** 올라온 뒤 단가가 바뀌었으면 첫 값→마지막 값. */
export function budgetMove(p: Project): { from: number; to: number; pct: number } | null {
  const vals = (p.history ?? []).map((h) => monthlyMid(h.budget)).filter((v): v is number => v != null)
  if (vals.length < 2 || vals[0] === vals[vals.length - 1]) return null
  const from = vals[0]
  const to = vals[vals.length - 1]
  return { from, to, pct: Math.round(((to - from) / from) * 1000) / 10 }
}
