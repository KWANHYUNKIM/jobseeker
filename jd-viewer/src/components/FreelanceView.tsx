import { useEffect, useMemo, useState } from 'react'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../lib/usePaged'
import { EmptyState, ErrorState, Loader, Pagination, SearchInput, TechTag, hits } from './ui'

// 외주·프리 — SI/SM 상주, 외주 도급, 부업으로 할 만한 프로젝트.
//
// 채용 공고와 따로 둔다. 여기서 보는 건 '회사'가 아니라 단가·기간·상주 여부이고,
// 올리는 쪽도 대개 에이전시라 회사 통계에 섞으면 둘 다 흐려진다.
// 데이터: public/freelance.json (catch_capture/crawlers/crawl_freelance.py 가 누적한다).

interface Budget {
  type: 'monthly' | 'total'
  min: number | null
  max: number | null
}

interface Project {
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
}

/** 월 단가 가운데 값(만원). 월 단가가 아니면 null. */
function monthlyMid(b: Budget | null): number | null {
  if (!b || b.type !== 'monthly') return null
  const lo = b.min ?? b.max
  const hi = b.max ?? b.min
  return lo != null && hi != null ? (lo + hi) / 2 : null
}

/** 올라온 뒤 단가가 바뀌었으면 첫 값→마지막 값. */
function budgetMove(p: Project): { from: number; to: number; pct: number } | null {
  const vals = (p.history ?? []).map((h) => monthlyMid(h.budget)).filter((v): v is number => v != null)
  if (vals.length < 2 || vals[0] === vals[vals.length - 1]) return null
  const from = vals[0]
  const to = vals[vals.length - 1]
  return { from, to, pct: Math.round(((to - from) / from) * 1000) / 10 }
}

// ── 단가 추이 — 주별 상주 월 단가 중앙값(막대) + 기술별 단가 표 + 단가를 바꾼 프로젝트 ──
function TrendPanel({ trend }: { trend: Trend }) {
  const [hover, setHover] = useState<number | null>(null)
  const weeks = trend.weekly.filter((w) => w.onsite != null)
  const max = Math.max(1, ...weeks.map((w) => w.onsite ?? 0))
  const W = 560
  const H = 150
  const pad = { l: 36, r: 8, t: 10, b: 22 }
  const bw = weeks.length ? (W - pad.l - pad.r) / weeks.length : 0
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max)
  const ticks = [0, Math.round(max / 2), Math.round(max)]
  const hv = hover != null ? weeks[hover] : null

  return (
    <div className="grid gap-4 p-4 border-b border-(--color-border) bg-(--color-panel)/40 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <section>
        <h3 className="text-sm font-semibold text-(--color-text)">상주 프로젝트 월 단가 중앙값 (주별, 만원)</h3>
        <p className="text-[11px] text-(--color-muted) mb-1">
          그 주에 새로 올라온 자리의 <b>올라올 때 단가</b>로 셉니다. 나중에 내린 값은 오른쪽 목록에서 따로 봅니다.
        </p>
        {weeks.length === 0 ? (
          <p className="text-xs text-(--color-muted)">아직 주별로 셀 만큼 쌓이지 않았습니다. 사이클이 돌수록 채워집니다.</p>
        ) : (
          <div className="relative">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="주별 상주 월 단가 중앙값">
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--color-border)" strokeWidth={1} />
                  <text x={pad.l - 4} y={y(t) + 3} textAnchor="end" fontSize={9} fill="var(--color-muted)">
                    {t}
                  </text>
                </g>
              ))}
              {weeks.map((w, i) => {
                const v = w.onsite ?? 0
                const x = pad.l + i * bw + 1
                const top = y(v)
                const h = H - pad.b - top
                const r = Math.min(4, (bw - 2) / 2, h)
                return (
                  <g key={w.week} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                    {/* 막대보다 넓은 히트 영역 */}
                    <rect x={pad.l + i * bw} y={pad.t} width={bw} height={H - pad.t - pad.b} fill="transparent" />
                    <path
                      d={`M${x},${H - pad.b} V${top + r} Q${x},${top} ${x + r},${top} H${x + bw - 2 - r} Q${x + bw - 2},${top} ${x + bw - 2},${top + r} V${H - pad.b} Z`}
                      fill="var(--color-accent)"
                      opacity={hover == null || hover === i ? 1 : 0.45}
                    />
                    {(i === 0 || i === weeks.length - 1 || i % 4 === 0) && (
                      <text x={x + (bw - 2) / 2} y={H - 8} textAnchor="middle" fontSize={9} fill="var(--color-muted)">
                        {w.week.slice(5)}
                      </text>
                    )}
                  </g>
                )
              })}
            </svg>
            {hv && (
              <div className="absolute top-0 right-0 text-[11px] rounded border border-(--color-border) bg-(--color-panel) px-2 py-1 shadow-sm">
                <b className="text-(--color-text)">{hv.week} 주</b>
                <div className="text-(--color-muted)">
                  상주 {hv.onsite?.toLocaleString()}만원 · 전체 {hv.median?.toLocaleString()}만원 · {hv.n}건
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 min-w-0">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-(--color-text) mb-1">기술별 월 단가 (모집중)</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-(--color-muted)">
                <th className="text-left font-normal">기술</th>
                <th className="text-right font-normal">중앙값</th>
                <th className="text-right font-normal">범위</th>
                <th className="text-right font-normal">건</th>
              </tr>
            </thead>
            <tbody>
              {trend.by_skill.slice(0, 10).map((s) => (
                <tr key={s.skill} className="border-t border-(--color-border)">
                  <td className="py-0.5 text-(--color-text)">{s.skill}</td>
                  <td className="text-right tabular-nums text-(--color-text)">{Math.round(s.median).toLocaleString()}</td>
                  <td className="text-right tabular-nums text-(--color-muted)">
                    {Math.round(s.min)}~{Math.round(s.max)}
                  </td>
                  <td className="text-right tabular-nums text-(--color-muted)">{s.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-(--color-text) mb-1">올라온 뒤 단가를 바꾼 프로젝트</h3>
          {trend.budget_moves.length === 0 ? (
            <p className="text-xs text-(--color-muted)">
              아직 없습니다. 같은 프로젝트의 단가가 사이클 사이에 바뀌면 여기에 쌓입니다.
            </p>
          ) : (
            <ul className="text-xs flex flex-col gap-1">
              {trend.budget_moves.slice(0, 8).map((m) => (
                <li key={m.id} className="flex gap-2">
                  <span className="truncate flex-1 text-(--color-text)">{m.title}</span>
                  <span className="tabular-nums text-(--color-muted) shrink-0">
                    {m.from}→{m.to}
                  </span>
                  <span className={`tabular-nums shrink-0 ${m.pct < 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {m.pct > 0 ? '+' : ''}
                    {m.pct}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

interface HistoryEntry {
  at: string
  budget: Budget | null
  status: 'active' | 'closed'
  duration: string
  applicants: number | null
}

interface Trend {
  weekly: { week: string; n: number; median: number | null; onsite: number | null; remote: number | null }[]
  by_skill: { skill: string; n: number; median: number; min: number; max: number }[]
  budget_moves: { id: string; title: string; from: number; to: number; pct: number; at: string }[]
}

interface FreelanceData {
  updated_at: string
  sources: Record<string, { ok: boolean; fetched: number; error?: string }>
  trend?: Trend
  projects: Project[]
}

const SITE_KO: Record<string, string> = {
  wanted_gigs: '원티드 긱스',
  freemoa: '프리모아',
  elancer: '이랜서',
  jobkorea: '잡코리아',
  saramin: '사람인',
  imjob: '아임잡',
  sism: 'SISM',
}

// 목록 앞쪽만 훑는 소스라 '이번에 안 보였다'가 곧 마감은 아니다. 그래도 2주째 안 보이면
// 내려갔을 가능성이 크니 모집중에서는 뺀다(데이터에서는 지우지 않는다).
const STALE_DAYS = 14

type KindFilter = 'all' | 'onsite' | 'remote' | 'side'
const KINDS: { key: KindFilter; label: string; hint: string }[] = [
  { key: 'all', label: '전체', hint: '' },
  { key: 'onsite', label: '상주 (SI/SM)', hint: '고객사에 출근하는 기간제' },
  { key: 'remote', label: '원격·도급', hint: '결과물로 계약하는 외주' },
  { key: 'side', label: '부업 가능', hint: '원격 + 짧은 기간 또는 파트타임 표기' },
]

type Sort = 'new' | 'pay'

function todayKst(): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())
}

function daysSince(iso: string): number {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 0 : (Date.now() - t) / 86_400_000
}

function won(n: number): string {
  return n.toLocaleString()
}

function budgetLabel(b: Budget | null): string {
  if (!b || (!b.min && !b.max)) return '단가 협의'
  const lo = b.min ?? b.max!
  const hi = b.max ?? b.min!
  const range = lo === hi ? `${won(lo)}만원` : `${won(lo)}~${won(hi)}만원`
  return b.type === 'monthly' ? `월 ${range}` : `총 ${range}`
}

/** 개발 프로젝트인가. 프리모아는 분야를 "개발,디자인,기획" 처럼 여럿 단다. */
function isDev(p: Project): boolean {
  return !p.category || p.category.split(',').some((c) => c.trim() === '개발')
}

/** 부업으로 할 만한가 — 원격이면서 3개월 이하이거나, 원본이 파트타임·주말을 적었거나. */
function isSide(p: Project): boolean {
  if (p.tags.includes('부업 가능')) return true
  if (p.kind !== 'remote') return false
  const m = p.duration.match(/(\d+)\s*(일|개월)/)
  if (!m) return false
  const days = Number(m[1]) * (m[2] === '개월' ? 30 : 1)
  return days <= 90
}

function useFreelance() {
  const [state, setState] = useState<{ data: FreelanceData | null; loading: boolean; error: string | null }>({
    data: null,
    loading: true,
    error: null,
  })
  useEffect(() => {
    let cancelled = false
    fetch('/freelance.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<FreelanceData>
      })
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((e) => !cancelled && setState({ data: null, loading: false, error: String(e) }))
    return () => {
      cancelled = true
    }
  }, [])
  return state
}

export function FreelanceView() {
  const { data, loading, error } = useFreelance()
  const [kind, setKind] = useState<KindFilter>('all')
  const [sites, setSites] = useState<Set<string>>(new Set())
  const [devOnly, setDevOnly] = useState(true)
  const [openOnly, setOpenOnly] = useState(true)
  const [sort, setSort] = useState<Sort>('new')
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [showTrend, setShowTrend] = useState(false)

  // 마감일이 지났는데 원본 재확인 전이면 여기서 닫는다(뷰어의 useJobs 와 같은 규칙).
  const projects = useMemo(() => {
    if (!data) return []
    const today = todayKst()
    return data.projects.map((p) => {
      const passed = p.status === 'active' && !!p.deadline && p.deadline < today
      const stale = daysSince(p.last_seen_at) > STALE_DAYS
      return { p, open: p.status === 'active' && !passed && !stale, stale }
    })
  }, [data])

  const shown = useMemo(() => {
    const rows = projects.filter(({ p, open }) => {
      if (openOnly && !open) return false
      if (devOnly && !isDev(p)) return false
      if (sites.size && !sites.has(p.site)) return false
      if (kind === 'onsite' && p.kind !== 'onsite') return false
      if (kind === 'remote' && p.kind !== 'remote') return false
      if (kind === 'side' && !isSide(p)) return false
      return hits(query, p.title, p.location, p.summary, p.career, ...p.skills, ...p.tags)
    })
    if (sort === 'pay') {
      // 월 단가끼리만 비교가 된다. 총액(도급)은 기간이 제각각이라 뒤로 보낸다.
      const pay = (p: Project) => (p.budget?.type === 'monthly' ? (p.budget.max ?? p.budget.min ?? 0) : -1)
      return [...rows].sort((a, b) => pay(b.p) - pay(a.p))
    }
    const key = (p: Project) => p.posted_date ?? p.first_seen_at.slice(0, 10)
    return [...rows].sort((a, b) => (key(a.p) < key(b.p) ? 1 : key(a.p) > key(b.p) ? -1 : 0))
  }, [projects, openOnly, devOnly, sites, kind, query, sort])

  const counts = useMemo(() => {
    const open = projects.filter((x) => x.open && (!devOnly || isDev(x.p)))
    return {
      open: open.length,
      onsite: open.filter((x) => x.p.kind === 'onsite').length,
      remote: open.filter((x) => x.p.kind === 'remote').length,
      side: open.filter((x) => isSide(x.p)).length,
      bySite: open.reduce<Record<string, number>>((m, x) => ((m[x.p.site] = (m[x.p.site] ?? 0) + 1), m), {}),
    }
  }, [projects, devOnly])

  const { page, setPage, totalPages, slice } = usePaged(shown, PAGE_SIZE)

  if (loading) return <Loader label="외주·프리 프로젝트 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="freelance.json 로드 실패"
        detail={error}
        hint={
          <>
            생성: <code className="text-(--color-text)">python -m crawlers.crawl_freelance</code>
          </>
        }
      />
    )
  if (!data) return null

  const toggleSite = (s: string) =>
    setSites((prev) => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })
  const kindCount: Record<KindFilter, number> = {
    all: counts.open,
    onsite: counts.onsite,
    remote: counts.remote,
    side: counts.side,
  }
  const chip = (on: boolean) =>
    `px-2.5 py-1 rounded-full text-xs border transition ${
      on
        ? 'bg-(--color-accent) border-(--color-accent) text-white'
        : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text)'
    }`

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      <div className="px-4 py-3 border-b border-(--color-border) bg-(--color-panel)/60 flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="text-sm text-(--color-text)">
            모집중 <b>{counts.open.toLocaleString()}</b>건
          </span>
          <span className="text-xs text-(--color-muted)">
            상주 {counts.onsite} · 원격·도급 {counts.remote} · 부업 가능 {counts.side}
          </span>
          <span className="text-xs text-(--color-muted) ml-auto">
            수집 {data.updated_at.slice(0, 16).replace('T', ' ')} ·{' '}
            {Object.entries(data.sources)
              .map(([s, r]) => `${SITE_KO[s] ?? s} ${r.ok ? r.fetched : '실패'}`)
              .join(' · ')}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {KINDS.map((k) => (
            <button key={k.key} title={k.hint} className={chip(kind === k.key)} onClick={() => setKind(k.key)}>
              {k.label} <span className="opacity-70">{kindCount[k.key]}</span>
            </button>
          ))}
          <span className="w-px h-4 bg-(--color-border) mx-1" />
          {Object.keys(SITE_KO).map((s) => (
            <button key={s} className={chip(sites.has(s))} onClick={() => toggleSite(s)}>
              {SITE_KO[s]} <span className="opacity-70">{counts.bySite[s] ?? 0}</span>
            </button>
          ))}
          <span className="w-px h-4 bg-(--color-border) mx-1" />
          <button className={chip(devOnly)} onClick={() => setDevOnly((v) => !v)} title="디자인·기획·마케팅 프로젝트 빼기">
            개발만
          </button>
          <button className={chip(openOnly)} onClick={() => setOpenOnly((v) => !v)} title="마감·오래 안 보인 프로젝트 빼기">
            모집중만
          </button>
          <div className="ml-auto flex items-center gap-2">
            {data.trend && (
              <button className={chip(showTrend)} onClick={() => setShowTrend((v) => !v)}>
                단가 추이
              </button>
            )}
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
              className="text-xs rounded border border-(--color-border) bg-(--color-bg) text-(--color-text) px-2 py-1.5"
            >
              <option value="new">최신순</option>
              <option value="pay">월 단가 높은순</option>
            </select>
            <SearchInput value={query} onChange={setQuery} placeholder="제목·기술·지역 검색" className="w-56" />
          </div>
        </div>
      </div>

      <main data-scroll className="flex-1 min-h-0 overflow-auto jd-panel">
        {showTrend && data.trend && <TrendPanel trend={data.trend} />}
        {shown.length === 0 ? (
          <EmptyState title="조건에 맞는 프로젝트가 없습니다" hint="필터를 풀거나 검색어를 바꿔 보세요." />
        ) : (
          <ul className="grid gap-3 p-4 grid-cols-1 xl:grid-cols-2">
            {slice.map(({ p, open, stale }) => {
              const isOpen = expanded === p.id
              const move = budgetMove(p)
              const changes = (p.history ?? []).length
              const dday =
                p.deadline && open
                  ? Math.ceil((Date.parse(p.deadline) - Date.parse(todayKst())) / 86_400_000)
                  : null
              return (
                <li
                  key={p.id}
                  className={`rounded-lg border border-(--color-border) bg-(--color-panel) p-3 flex flex-col gap-2 ${open ? '' : 'opacity-60'}`}
                >
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5 text-[11px] mb-1">
                        <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)">
                          {SITE_KO[p.site] ?? p.site}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded ${p.kind === 'onsite' ? 'bg-(--color-accent)/15 text-(--color-accent)' : 'bg-emerald-500/15 text-emerald-600'}`}
                        >
                          {p.kind === 'onsite' ? '상주' : '원격·도급'}
                        </span>
                        {p.tags.map((t) => (
                          <span key={t} className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700">
                            {t}
                          </span>
                        ))}
                        {!open && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-(--color-bg) text-(--color-muted)"
                            title={p.closed_reason}
                          >
                            {stale ? `${STALE_DAYS}일 넘게 안 보임` : '마감'}
                          </span>
                        )}
                        {move && (
                          <span
                            className={`px-1.5 py-0.5 rounded ${move.pct < 0 ? 'bg-rose-500/15 text-rose-600' : 'bg-emerald-500/15 text-emerald-600'}`}
                            title="올라온 뒤 월 단가가 바뀌었습니다"
                          >
                            단가 {move.from}→{move.to} ({move.pct > 0 ? '+' : ''}
                            {move.pct}%)
                          </span>
                        )}
                        {dday !== null && dday <= 7 && (
                          <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-600">
                            {dday <= 0 ? '오늘 마감' : `D-${dday}`}
                          </span>
                        )}
                      </div>
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-semibold text-(--color-text) hover:text-(--color-accent) line-clamp-2"
                      >
                        {p.title}
                      </a>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-bold text-(--color-text) tabular-nums">{budgetLabel(p.budget)}</div>
                      {p.applicants != null && (
                        <div className="text-[11px] text-(--color-muted)">지원 {p.applicants}명</div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-(--color-muted)">
                    {p.location && <span>📍 {p.location}</span>}
                    {p.duration && <span>기간 {p.duration}</span>}
                    {p.start && <span>시작 {p.start}</span>}
                    {p.career && <span>{p.career}</span>}
                    {p.deadline && <span>마감 {p.deadline}</span>}
                    <span>등록 {p.posted_date ?? `${p.first_seen_at.slice(0, 10)} (수집일)`}</span>
                  </div>

                  {p.skills.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {p.skills.slice(0, 8).map((s) => (
                        <TechTag key={s} tech={s} />
                      ))}
                    </div>
                  )}

                  {p.summary && p.summary.length > 30 && (
                    <p className={`text-xs text-(--color-muted) whitespace-pre-line ${isOpen ? '' : 'line-clamp-2'}`}>
                      {p.summary}
                    </p>
                  )}

                  {isOpen && (
                    <div className="text-xs border-t border-(--color-border) pt-2">
                      <div className="text-(--color-muted) mb-1">
                        처음 본 날 {p.first_seen_at.slice(0, 10)} · 마지막으로 본 날 {p.last_seen_at.slice(0, 10)}
                        {p.closed_reason && ` · ${p.closed_reason}`}
                      </div>
                      <table className="w-full">
                        <thead>
                          <tr className="text-(--color-muted)">
                            <th className="text-left font-normal">시각</th>
                            <th className="text-left font-normal">단가</th>
                            <th className="text-left font-normal">기간</th>
                            <th className="text-left font-normal">상태</th>
                            <th className="text-right font-normal">지원</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(p.history ?? []).map((h) => (
                            <tr key={h.at} className="border-t border-(--color-border)">
                              <td className="py-0.5 tabular-nums">{h.at.slice(0, 16).replace('T', ' ')}</td>
                              <td>{budgetLabel(h.budget)}</td>
                              <td>{h.duration || '—'}</td>
                              <td>{h.status === 'closed' ? '마감' : '모집중'}</td>
                              <td className="text-right tabular-nums">{h.applicants ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {changes <= 1 && (
                        <p className="mt-1 text-(--color-muted)">아직 바뀐 적이 없습니다 — 단가·상태·기간이 바뀌면 한 줄씩 쌓입니다.</p>
                      )}
                    </div>
                  )}

                  <button
                    className="self-start text-xs text-(--color-accent) hover:underline"
                    onClick={() => setExpanded(isOpen ? null : p.id)}
                  >
                    {isOpen ? '접기' : `세부 내역${changes > 1 ? ` · 변경 ${changes - 1}회` : ''}`}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        <Pagination page={page} totalPages={totalPages} total={shown.length} pageSize={PAGE_SIZE} onChange={setPage} />
      </main>
    </div>
  )
}
