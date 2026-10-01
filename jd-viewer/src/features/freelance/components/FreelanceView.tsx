import { useMemo, useState } from 'react'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import {
  SITE_KO,
  STALE_DAYS,
  budgetLabel,
  budgetMove,
  todayKst,
  type Project,
} from '../utils/freelance'
import { useFreelance } from '../hooks/useFreelance'
import { FreelanceNav } from './FreelanceNav'
import { EmptyState, ErrorState, Loader, Pagination, SearchInput, TechTag, hits } from '../../../components/ui'

// 외주·프리 — SI/SM 상주, 외주 도급, 부업으로 할 만한 프로젝트.
//
// 채용 공고와 따로 둔다. 여기서 보는 건 '회사'가 아니라 단가·기간·상주 여부이고,
// 올리는 쪽도 대개 에이전시라 회사 통계에 섞으면 둘 다 흐려진다.
// 데이터: public/freelance.json (catch_capture/crawlers/crawl_freelance.py 가 누적한다).

type KindFilter = 'all' | 'onsite' | 'remote' | 'side'
const KINDS: { key: KindFilter; label: string; hint: string }[] = [
  { key: 'all', label: '전체', hint: '' },
  { key: 'onsite', label: '상주 (SI/SM)', hint: '고객사에 출근하는 기간제' },
  { key: 'remote', label: '원격·도급', hint: '결과물로 계약하는 외주' },
  { key: 'side', label: '부업 가능', hint: '원격 + 짧은 기간 또는 파트타임 표기' },
]

type Sort = 'new' | 'pay'

function daysSince(iso: string): number {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 0 : (Date.now() - t) / 86_400_000
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

export function FreelanceView() {
  const { data, loading, error } = useFreelance()
  const [kind, setKind] = useState<KindFilter>('all')
  const [sites, setSites] = useState<Set<string>>(new Set())
  const [devOnly, setDevOnly] = useState(true)
  const [openOnly, setOpenOnly] = useState(true)
  const [sort, setSort] = useState<Sort>('new')
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

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
      <FreelanceNav current="list" />
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
        {shown.length === 0 ? (
          <EmptyState title="조건에 맞는 프로젝트가 없습니다" hint="필터를 풀거나 검색어를 바꿔 보세요." />
        ) : (
          <ul className="grid gap-3 p-4 grid-cols-1 xl:grid-cols-2">
            {slice.map(({ p, open, stale }) => {
              const isOpen = expanded === p.id
              const move = budgetMove(p)
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
                        {p.grade && p.grade !== '혼합' && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-700"
                            title={p.grade_basis === '경력 추정' ? `경력(${p.career})으로 추정한 등급` : '원본에 적힌 등급'}
                          >
                            {p.grade}
                            {p.grade_basis === '경력 추정' ? ' (추정)' : ''}
                          </span>
                        )}
                        {p.domain && p.domain !== '기타' && (
                          <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)">
                            {p.domain}
                          </span>
                        )}
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

                  {/* 이력 표는 두지 않는다 — 대부분 한 줄('처음 본 값')뿐이라 읽을 게 없었다.
                      단가가 실제로 바뀐 자리는 위의 배지가 말하고, 흐름은 단가 분석 페이지가 본다. */}
                  {p.summary && p.summary.length > 30 && (
                    <div className="text-xs text-(--color-muted)">
                      <p className={`whitespace-pre-line ${isOpen ? '' : 'line-clamp-2'}`}>{p.summary}</p>
                      {p.summary.length > 120 && (
                        <button
                          className="mt-0.5 text-(--color-accent) hover:underline"
                          onClick={() => setExpanded(isOpen ? null : p.id)}
                        >
                          {isOpen ? '접기' : '더 보기'}
                        </button>
                      )}
                    </div>
                  )}
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
