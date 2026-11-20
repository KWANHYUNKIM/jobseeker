import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import { GRADES, SITE_KO, budgetLabel, monthlyMid, projectState, todayKst, type Project, type Stat } from '../utils/freelance'
import { useFreelance } from '../hooks/useFreelance'
import { EmptyState, ErrorState, Loader } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { SiteFooter } from '../../../components/SiteFooter'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'

// 외주·프리 — SI/SM 상주, 외주 도급, 부업으로 할 만한 프로젝트(캐치형 08).
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
type Sort = 'pay' | 'new'

/** 등급 카드 막대의 눈금(만원) — 네 등급이 같은 자로 재여야 서로 비교가 된다. */
const SCALE_MIN = 200
const SCALE_MAX = 1000
const pos = (v: number) => Math.max(0, Math.min(1, (v - SCALE_MIN) / (SCALE_MAX - SCALE_MIN))) * 100

/** 부업으로 할 만한가 — 원격이면서 3개월 이하이거나, 원본이 파트타임·주말을 적었거나. */
function isSide(p: Project): boolean {
  if (p.tags.includes('부업 가능')) return true
  if (p.kind !== 'remote') return false
  const m = p.duration.match(/(\d+)\s*(일|개월)/)
  if (!m) return false
  const days = Number(m[1]) * (m[2] === '개월' ? 30 : 1)
  return days <= 90
}

/** 정렬용 월 단가 — 가운데 값. 3천만원을 넘는 월 단가는 원본의 자리채움(9,999 등)이라 단가 없음으로 본다. */
const payOf = (p: Project) => {
  const v = monthlyMid(p.budget)
  return v != null && v <= 3000 ? v : -1
}

/**
 * 외주·프리 목록 — 숫자 칸 넷, 등급별 월 단가 카드(상주, 중간 50% 막대), 프로젝트 목록(유형 칩·정렬·쪽 번호),
 * 오른쪽에 직군별 월 단가 중앙값과 수집 사이트. 단가를 더 깊게 보는 화면은 `/freelance/rates`.
 */
export function FreelanceView() {
  const { data, loading, error } = useFreelance()
  const [kind, setKind] = useState<KindFilter>('all')
  const [sort, setSort] = useState<Sort>('pay')

  // 마감일이 지났거나 2주 넘게 안 보인 프로젝트는 모집중에서 뺀다(projectState — 상세·단가표와 같은 규칙).
  const open = useMemo(() => {
    if (!data) return []
    const today = todayKst()
    return data.projects.filter((p) => projectState(p, today).open)
  }, [data])

  const shown = useMemo(() => {
    const rows = open.filter((p) =>
      kind === 'onsite' ? p.kind === 'onsite' : kind === 'remote' ? p.kind === 'remote' : kind === 'side' ? isSide(p) : true,
    )
    if (sort === 'pay') return [...rows].sort((a, b) => payOf(b) - payOf(a))
    const key = (p: Project) => p.posted_date ?? p.first_seen_at.slice(0, 10)
    return [...rows].sort((a, b) => (key(a) < key(b) ? 1 : key(a) > key(b) ? -1 : 0))
  }, [open, kind, sort])

  const paged = usePaged(shown, PAGE_SIZE)
  const stars = useStars()

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

  const a = data.analysis
  const onsiteRow = a?.by_mode.find((r) => r.key === '상주')
  const grades = onsiteRow?.grades ?? a?.grades ?? {}
  const onsiteN = open.filter((p) => p.kind === 'onsite').length
  const roles = (a?.by_role ?? []).filter((r) => r.total.n > 0).slice(0, 6)

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">외주·프리</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          SI/SM 상주부터 원격 도급까지, 프리랜서 프로젝트 <b className="font-bold text-(--color-accent)">{open.length.toLocaleString()}건</b>을 모으고 월
          단가를 분석해요.
        </p>

        <div className="mt-[29px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
          <Stat label="모집중" value={`${open.length.toLocaleString()}건`} />
          <Stat label="상주 (SI/SM)" value={`${onsiteN.toLocaleString()}건`} />
          <Stat label="원격·도급" value={`${(open.length - onsiteN).toLocaleString()}건`} />
          <Stat label="상주 월 단가 중앙값" value={onsiteRow ? `${onsiteRow.total.median.toLocaleString()}만원` : '-'} accent />
        </div>

        {/* 등급별 월 단가 */}
        <div className="mt-[49px] flex flex-wrap items-baseline gap-x-[15px] gap-y-1">
          <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
            등급별 <span className="font-black text-(--color-accent)">월 단가</span>
          </h2>
          <span className="text-sm text-[#999]">상주 · 단위 만원 · 공고 {(a?.meta.graded ?? 0).toLocaleString()}건 기준</span>
          <a href={paths.freelanceRates()} onClick={onLinkClick(paths.freelanceRates())} className="ml-auto text-sm text-[#777] hover:text-[#272727]">
            단가 분석 자세히 ›
          </a>
        </div>
        <div className="mt-[22px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
          {GRADES.map((g) => (
            <GradeCard key={g} grade={g} s={grades[g] ?? null} />
          ))}
        </div>

        <div className="mt-[53px] flex flex-col lg:flex-row gap-7 items-start">
          {/* 프로젝트 목록 */}
          <section data-fl-top className="flex-1 min-w-0 w-full scroll-mt-4">
            <div className="flex items-center justify-between">
              <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">프로젝트</h2>
              <span className="text-[15px] text-[#666] tabular-nums">모집중 {open.length.toLocaleString()}건</span>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {KINDS.map((k) => (
                <button
                  key={k.key}
                  type="button"
                  title={k.hint}
                  aria-pressed={kind === k.key}
                  onClick={() => {
                    setKind(k.key)
                    paged.setPage(0)
                  }}
                  className={
                    'h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
                    (kind === k.key ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
                  }
                >
                  {k.label}
                </button>
              ))}
              <label className="ml-auto relative inline-flex items-center h-9 rounded-[18px] border border-(--color-accent) bg-white">
                <select
                  aria-label="정렬"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as Sort)}
                  className="appearance-none h-full bg-transparent pl-[17px] pr-[34px] text-sm font-medium tracking-[-0.3px] text-(--color-accent) outline-none cursor-pointer"
                >
                  <option value="pay">월 단가 높은순</option>
                  <option value="new">최신순</option>
                </select>
                <svg className="pointer-events-none absolute right-[17px]" width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#f45757" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                  <path d="M1.5 2.5 5 6l3.5-3.5" />
                </svg>
              </label>
            </div>
            {shown.length === 0 ? (
              <EmptyState title="조건에 맞는 프로젝트가 없습니다" hint="다른 유형을 골라 보세요." />
            ) : (
              <ul className="mt-[23px]">
                {paged.slice.map((p) => (
                  <ProjectRow key={p.id} p={p} starred={stars.has(p.id)} onStar={() => stars.toggle(p.id)} />
                ))}
              </ul>
            )}
            <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} scrollTo="[data-fl-top]" />
          </section>

          {/* 오른쪽 칸 */}
          <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4">
            <Box>
              <h3 className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">
                직군별 월 단가 <span className="font-black text-(--color-accent)">중앙값</span>
              </h3>
              <ul className="mt-[21px] flex flex-col gap-[13px]">
                {roles.map((r) => (
                  <li key={r.key} className="flex items-center">
                    <span className="w-24 shrink-0 text-sm text-[#474747] truncate">{r.key}</span>
                    <span className="flex-1 h-2.5 rounded-[5px] bg-[#f1f3f5] overflow-hidden">
                      <span className="block h-full rounded-[5px] bg-[#f67979]" style={{ width: `${Math.min(100, (r.total.median / SCALE_MAX) * 100)}%` }} />
                    </span>
                    <span className="w-[44px] shrink-0 text-right text-sm font-bold text-[#272727] tabular-nums">{r.total.median}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-[21px] text-xs text-[#999]">단위 만원 · 상주 기준</p>
            </Box>
            <Box>
              <h3 className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">수집 사이트</h3>
              <ul className="mt-[18px]">
                {Object.entries(data.sources).map(([s, r]) => (
                  <li key={s} className="flex items-center justify-between h-[34px] border-b border-[#f1f3f5] text-[15px]">
                    <span className="text-[#272727]">{SITE_KO[s] ?? s}</span>
                    <b className="font-bold text-[#272727] tabular-nums">{r.ok ? `${r.fetched}건` : '실패'}</b>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-[#999]">수집 {data.updated_at.slice(0, 16).replace('T', ' ')}</p>
            </Box>
          </aside>
        </div>
      </div>
      <SiteFooter updated={data.updated_at} sources="원티드 긱스 · 프리모아 · 이랜서 · 잡코리아 · 사람인 · 아임잡 · SISM" />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={'h-28 rounded-[20px] border px-[25px] pt-[22px] ' + (accent ? 'bg-(--color-accent-weak) border-[#ffd5d5]' : 'border-[#e2e8ec]')}>
      <div className="text-sm tracking-[-0.16px] text-[#777]">{label}</div>
      <div className={'mt-1 text-[28px] font-bold leading-10 tracking-[-0.5px] tabular-nums ' + (accent ? 'text-(--color-accent)' : 'text-[#272727]')}>{value}</div>
    </div>
  )
}

function GradeCard({ grade, s }: { grade: string; s: Stat | null }) {
  return (
    <div className="h-[183px] rounded-[22px] bg-[#f7f9fa] px-6 pt-6">
      <div className="flex items-baseline gap-1.5">
        <span className="text-[17px] font-bold text-[#272727]">{grade}</span>
        <span className="text-[13px] text-[#999] tabular-nums">{s ? `${s.n}건` : '표본 없음'}</span>
      </div>
      {s ? (
        <>
          <div className="mt-[5px]">
            <span className="text-[36px] font-bold leading-[52px] tracking-[-0.8px] text-[#272727] tabular-nums">{s.median}</span>
            <span className="ml-0.5 text-[15px] text-[#474747]">만원</span>
          </div>
          {/* 회색 자 = 200~1000만원, 붉은 칸 = 중간 50%, 검은 눈금 = 중앙값 */}
          <div className="relative mt-3 h-2 rounded bg-[#e3e7ea]" aria-hidden>
            <span className="absolute inset-y-0 rounded bg-[#f67979]" style={{ left: `${pos(s.p25)}%`, width: `${Math.max(1, pos(s.p75) - pos(s.p25))}%` }} />
            <span className="absolute -top-1 w-1 h-4 rounded-sm bg-[#272727]" style={{ left: `calc(${pos(s.median)}% - 2px)` }} />
          </div>
          <div className="mt-[10px] text-sm text-[#474747] tabular-nums">
            {s.p25} ~ {s.p75} <span className="text-[11.5px] text-[#999]">(중간 50%)</span>
          </div>
        </>
      ) : (
        <p className="mt-6 text-sm text-[#999]">이 등급으로 단가가 적힌 공고가 아직 없어요.</p>
      )}
    </div>
  )
}

const STAR_KEY = 'jd-freelance-stars'

/** 관심 프로젝트(별) — 이 브라우저에만 남는 편의 기능이다. 저장소가 막혀 있으면 이번 방문 동안만 기억한다. */
function useStars() {
  const [set, setSet] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(STAR_KEY) || '[]') as string[])
    } catch {
      return new Set()
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(STAR_KEY, JSON.stringify([...set]))
    } catch {
      /* 저장소가 막힌 브라우저 — 기억만 못 할 뿐 동작은 같다 */
    }
  }, [set])
  return {
    has: (k: string) => set.has(k),
    toggle: (k: string) =>
      setSet((s) => {
        const n = new Set(s)
        if (n.has(k)) n.delete(k)
        else n.add(k)
        return n
      }),
  }
}

function Box({ children }: { children: ReactNode }) {
  return <div className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] pt-[23px] pb-[22px]">{children}</div>
}

function ProjectRow({ p, starred, onStar }: { p: Project; starred: boolean; onStar: () => void }) {
  const priced = !!p.budget && !!(p.budget.min || p.budget.max)
  // 원본 사이트로 내보내지 않는다 — 우리 상세 화면에서 본문을 읽고, 지원만 원문에서 한다.
  const to = paths.freelanceProject(p.site, p.pid ?? p.id.slice(p.id.indexOf(':') + 1))
  return (
    <li className="flex flex-col md:flex-row md:items-center gap-3 border-b border-[#e2e2e2] py-[22px] md:py-0 md:min-h-[126px]">
      <div className="md:w-[480px] md:shrink-0 min-w-0 px-[14px]">
        <div className="flex flex-wrap gap-1">
          <span className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]">{p.kind === 'onsite' ? '상주' : '원격·도급'}</span>
          {p.grade && p.grade !== '혼합' && (
            <span
              className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] text-[#5b4fd6]"
              title={p.grade_basis === '경력 추정' ? `경력(${p.career})으로 추정한 등급` : '원본에 적힌 등급'}
            >
              {p.grade}
            </span>
          )}
        </div>
        <a href={to} onClick={onLinkClick(to)} className="mt-2 block truncate text-[17px] font-medium leading-[25px] tracking-[-0.16px] text-[#272727] hover:underline underline-offset-2">
          {p.title}
        </a>
        <div className="mt-2 flex flex-wrap gap-x-[14px] text-[13px] leading-[19px] text-[#666]">
          {p.location && (
            <span className="inline-flex items-center gap-[5px]">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#666" strokeWidth="1.3" aria-hidden>
                <path d="M7 12.5s4-3.6 4-6.6a4 4 0 0 0-8 0c0 3 4 6.6 4 6.6Z" />
                <circle cx="7" cy="5.8" r="1.5" />
              </svg>
              {p.location}
            </span>
          )}
          {(p.career || p.duration) && (
            <span className="inline-flex items-center gap-[5px]">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#666" strokeWidth="1.3" aria-hidden>
                <rect x="1.5" y="4" width="11" height="8" rx="1.5" />
                <path d="M5 4V2.5h4V4" />
              </svg>
              {p.career || `기간 ${p.duration}`}
            </span>
          )}
        </div>
      </div>
      <div className="md:w-[190px] md:shrink-0 flex flex-wrap gap-1 px-[14px] md:px-0">
        {p.skills.slice(0, 3).map((s) => (
          <span key={s} className="rounded-md border border-[#e2e2e2] px-2 text-xs leading-[22px] text-[#474747]">
            {s}
          </span>
        ))}
      </div>
      <div className="md:w-[170px] md:shrink-0 px-[14px] md:px-0 md:pr-[14px] md:text-right">
        <div className={'text-base font-bold leading-6 ' + (priced ? 'text-(--color-accent)' : 'text-[#999] font-medium')}>{budgetLabel(p.budget)}</div>
        <div className="mt-1 text-[13px] text-[#999]">{SITE_KO[p.site] ?? p.site}</div>
      </div>
      <div className="hidden md:grid md:w-10 md:shrink-0 place-items-center">
        <button type="button" onClick={onStar} aria-pressed={starred} aria-label={starred ? '관심 프로젝트에서 빼기' : '관심 프로젝트로 담기'} className="w-6 h-6 grid place-items-center">
          <svg width="24" height="24" viewBox="0 0 24 24" fill={starred ? '#f45757' : 'none'} stroke={starred ? '#f45757' : '#c4c4c4'} strokeWidth="1.5" strokeLinejoin="round" aria-hidden>
            <path d="M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8Z" />
          </svg>
        </button>
      </div>
    </li>
  )
}
