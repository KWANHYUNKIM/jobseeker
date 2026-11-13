import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useCompanies, useCompanyDetail } from '../../../hooks/useCompanies'
import { useLearning, type LearningVideo } from '../../../hooks/useLearning'
import { Loader, ErrorState, EmptyState, CompanyMark } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'
import { classifyRoles } from '../../../utils/classify'
import { navigate } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import type { CompanyStack, CompanyPosting, CareerGuide } from '../../../types'

const CAT_ORDER = [
  '언어', '백엔드', '프론트엔드', '모바일', '데이터베이스',
  '인프라/DevOps', '펌웨어/임베디드', 'AI/ML', '데이터', '협업/도구', '기타',
]
const SIZES = ['대기업', '중견기업', '중소기업', '해외 기업']
const SORTS = [
  ['count', '공고 많은 순'],
  ['name', '이름 순'],
] as const
type Sort = (typeof SORTS)[number][0]
const LIST_STEP = 12
const SOURCES = '사람인 · 잡코리아 · 인크루트 · 게임잡 · 원티드 · 점핏 · 각 사 채용 페이지'
const SITE_NAME: Record<string, string> = { ats: '자체 채용 (ATS)', boards: '기타 보드·공공', remote: '해외·원격', dev: '데보션' }

/**
 * 기업 기술스택(캐치형 03) — 위에 제목·검색·규모 칩·정렬, 아래 왼쪽은 회사 카드 목록(12곳씩 더보기),
 * 오른쪽은 고른 회사의 프로필 카드와 탭(기술스택·아키텍처·취업 가이드·공부 로드맵·채용 공고 — 누르면
 * 그 구역으로 내려간다). 회사 선택은 주소(/companies/<슬러그>)가 들고 있다.
 */
export function CompanyView({
  selectedSlug,
  onSelectCompany,
  onStudyTech,
}: {
  /** 주소(/companies/coupang)에서 온 선택. 이 컴포넌트는 선택을 스스로 들고 있지 않는다. */
  selectedSlug?: string | null
  onSelectCompany: (slug: string) => void
  onStudyTech?: (tech: string) => void
}) {
  const { companies, meta, loading, error, slugOf, bySlug } = useCompanies()
  const [query, setQuery] = useState('')
  const [size, setSize] = useState('')
  const [sort, setSort] = useState<Sort>('count')
  const [shown, setShown] = useState(LIST_STEP)

  // 주소로 회사가 지정돼 들어오면 검색어를 비운다 — 걸러진 목록 때문에
  // 정작 지정된 회사가 왼쪽 목록에 안 보이는 상태를 막는다.
  const [prevSlug, setPrevSlug] = useState(selectedSlug)
  if (selectedSlug !== prevSlug) {
    setPrevSlug(selectedSlug)
    if (selectedSlug) setQuery('')
  }

  // 예전 주소(/companies/쿠팡)로 들어온 링크는 조용히 새 주소로 넘긴다.
  useEffect(() => {
    if (!selectedSlug || companies.length === 0) return
    if (bySlug(selectedSlug)) return
    const legacy = companies.find((c) => c.norm === selectedSlug)
    if (legacy) navigate(paths.company(slugOf(legacy.norm)), { replace: true })
  }, [selectedSlug, companies, bySlug, slugOf])

  const searched = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return companies
    return companies.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.domains.some((d) => d.name.toLowerCase().includes(q)) ||
        c.top_tech.some((t) => t.name.toLowerCase().includes(q)),
    )
  }, [companies, query])
  const sizeCount = (s: string) => searched.filter((c) => c.size === s).length
  const filtered = useMemo(() => {
    const out = size ? searched.filter((c) => c.size === size) : searched
    return sort === 'name' ? [...out].sort((a, b) => a.name.localeCompare(b.name, 'ko')) : out
  }, [searched, size, sort])

  const selected = useMemo(
    () => (selectedSlug ? bySlug(selectedSlug) : null) ?? filtered[0] ?? null,
    // bySlug 는 목록에서 만든 대응표를 읽을 뿐이라 목록이 그대로면 결과도 그대로다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [companies, selectedSlug, filtered],
  )

  // 목록 항목은 API 모드에서 요약뿐이다 — 프로필·제목에 쓸 전체 프로필은 따로 받는다.
  const { company: detail, loading: detailLoading } = useCompanyDetail(selected)

  // 주소로 회사가 지정된 화면의 제목·설명. 문구는 scripts/prerender.mjs 와 같은 규칙이어야 한다.
  const tech = (detail?.top_tech ?? []).slice(0, 15).map((t) => t.name)
  useSeo(
    selectedSlug && detail
      ? {
          title: `${detail.name} 기술스택·채용공고`,
          description: clip(`${detail.name}의 채용공고 ${detail.posting_count}건에서 뽑은 기술스택: ${tech.slice(0, 8).join(', ')}. ${detail.summary ?? ''}`),
          canonical: absUrl(paths.company(slugOf(detail.norm))),
          jsonLd: {
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: detail.name,
            ...(detail.homepage ? { url: detail.homepage } : {}),
            description: clip(detail.summary, 300),
            knowsAbout: tech,
          },
        }
      : null,
  )

  if (loading) return <Loader label="회사 분석 데이터 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="회사 프로필을 불러오지 못했습니다"
        detail={error}
        hint={<>뷰어 API(/api/companies) 또는 company_stacks.json — 생성: <code className="text-(--color-text)">python3 jd-viewer/bin/build_company_stacks.py</code></>}
      />
    )

  const pick = (f: () => void) => {
    f()
    setShown(LIST_STEP)
  }

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">기업 기술스택</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          채용공고에서 뽑은 회사별 기술·직군·아키텍처를 한눈에 비교해 보세요.{' '}
          <b className="font-bold text-(--color-accent)">{companies.length.toLocaleString()}개 회사</b> · 공고 {meta?.min_posting ?? 2}건 이상
        </p>

        <form role="search" onSubmit={(e) => e.preventDefault()} className="mt-[23px] flex gap-2.5">
          <label className="flex-1 min-w-0 flex items-center gap-2.5 h-[52px] rounded-[26px] border border-[#c4c4c4] pl-[23px] pr-5 focus-within:border-[#272727]">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2" aria-hidden className="shrink-0">
              <circle cx="8.5" cy="8.5" r="5.5" />
              <path d="M12.5 12.5 16 16" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              value={query}
              onChange={(e) => pick(() => setQuery(e.target.value))}
              placeholder="회사·기술스택을 검색해 보세요"
              aria-label="회사 검색"
              className="flex-1 min-w-0 bg-transparent text-[15px] tracking-[-0.16px] text-[#272727] placeholder:text-[#999] outline-none"
            />
          </label>
          <button
            type="submit"
            className="shrink-0 w-[110px] h-[52px] rounded-[26px] border-2 border-(--color-accent) text-base font-bold text-(--color-accent) hover:bg-(--color-accent-weak)"
          >
            검색
          </button>
        </form>

        <div className="mt-[18px] flex flex-wrap items-center gap-2">
          <Chip on={!size} count={searched.length} onClick={() => pick(() => setSize(''))}>
            전체
          </Chip>
          {SIZES.map((s) => (
            <Chip key={s} on={size === s} count={sizeCount(s)} onClick={() => pick(() => setSize(size === s ? '' : s))}>
              {s}
            </Chip>
          ))}
          <label className="ml-auto relative inline-flex items-center h-9 rounded-[18px] border border-(--color-accent) bg-white">
            <select
              aria-label="정렬"
              value={sort}
              onChange={(e) => pick(() => setSort(e.target.value as Sort))}
              className="appearance-none h-full bg-transparent pl-[17px] pr-[34px] text-sm font-medium tracking-[-0.3px] text-(--color-accent) outline-none cursor-pointer"
            >
              {SORTS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <svg className="pointer-events-none absolute right-[17px]" width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#f45757" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
              <path d="M1.5 2.5 5 6l3.5-3.5" />
            </svg>
          </label>
        </div>

        <div className="mt-[30px] flex flex-col lg:flex-row gap-6 items-start">
          {/* 왼쪽: 회사 카드 목록 */}
          <nav aria-label="회사 목록" className="w-full lg:w-[360px] shrink-0 flex flex-col gap-2">
            {filtered.length === 0 && <p className="py-10 text-center text-sm text-[#999]">조건에 맞는 회사가 없어요.</p>}
            {filtered.slice(0, shown).map((c) => {
              const active = selected?.norm === c.norm
              const to = paths.company(slugOf(c.norm))
              return (
                <a
                  key={c.norm}
                  href={to}
                  onClick={(e) => {
                    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
                    e.preventDefault()
                    onSelectCompany(slugOf(c.norm))
                  }}
                  aria-current={active ? 'true' : undefined}
                  className={
                    'flex items-center gap-3 h-[81px] rounded-[18px] px-[17px] transition ' +
                    (active ? 'bg-[#fff9f9] border-2 border-(--color-accent)' : 'bg-white border border-[#e2e8ec] hover:border-[#999]')
                  }
                >
                  <span className="grid place-items-center w-11 h-11 rounded-[11px] overflow-hidden shrink-0">
                    <CompanyMark name={c.name} size={44} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-base font-bold leading-6 tracking-[-0.16px] text-[#272727] truncate">{c.name}</span>
                    <span className="block text-[13px] leading-[19px] tracking-[-0.16px] text-[#777] truncate">
                      {c.domains[0]?.name ?? '도메인 미상'}
                      {c.top_tech.length > 0 ? ` · ${c.top_tech.slice(0, 3).map((t) => t.name).join(', ')}` : ''}
                    </span>
                  </span>
                  <span className="shrink-0 flex flex-col items-end gap-1">
                    <SizeTag size={c.size} />
                    <span className="text-[15px] font-bold leading-[21px] text-[#272727] tabular-nums">{c.posting_count}건</span>
                  </span>
                </a>
              )
            })}
            {shown < filtered.length && (
              <button
                type="button"
                onClick={() => setShown((n) => n + LIST_STEP)}
                className="mt-[22px] inline-flex items-center justify-center gap-2 h-11 rounded-[30px] bg-[#272727] text-base font-medium tracking-[-0.16px] text-white hover:bg-black"
              >
                회사 더보기 {Math.min(shown, filtered.length)} / {filtered.length.toLocaleString()}
                <svg width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                  <path d="M1.5 2.5 5 6l3.5-3.5" />
                </svg>
              </button>
            )}
          </nav>

          {/* 오른쪽: 회사 프로필 */}
          <main className="flex-1 min-w-0 w-full">
            {detail ? (
              <CompanyProfile key={detail.norm} c={detail} onStudyTech={onStudyTech} />
            ) : detailLoading ? (
              <Loader label="회사 프로필 불러오는 중…" />
            ) : (
              <EmptyState title="회사를 선택하세요" hint="왼쪽 목록에서 회사를 고르면 기술스택·취업 가이드가 표시됩니다." />
            )}
          </main>
        </div>
      </div>
      <SiteFooter jobs={meta?.total_jobs} companies={companies.length} updated={meta?.generated_at} sources={SOURCES} />
    </div>
  )
}

function Chip({ on, count, onClick, children }: { on: boolean; count: number; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'inline-flex items-center gap-1.5 h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {children}
      <span className={'text-xs font-normal tabular-nums ' + (on ? 'text-[#ffd9d9]' : 'text-[#999]')}>{count.toLocaleString()}</span>
    </button>
  )
}

function SizeTag({ size }: { size: string }) {
  return (
    <span
      className={
        'rounded px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] ' +
        (size === '대기업' ? 'bg-(--color-accent-weak) text-(--color-accent)' : 'bg-[#f4f4f4] text-[#474747]')
      }
    >
      {size}
    </span>
  )
}

/** 요약 문장에서 직군·주력 기술·아키텍처 대목을 굵게 — '주로 X 직군', '채용하며 Y 기반', '아키텍처는 Z로'. */
function SummaryText({ text }: { text: string }) {
  const parts: ReactNode[] = []
  const re = /(주로 )(.+?)( 직군)|(채용하며 )(.+?)( 기반)|(아키텍처는 )(.+?)(로 추정)/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text))) {
    parts.push(text.slice(last, m.index))
    const [pre, bold, post] = m[1] ? [m[1], m[2], m[3]] : m[4] ? [m[4], m[5], m[6]] : [m[7], m[8], m[9]]
    parts.push(pre, <b key={k++} className="font-bold text-[#272727]">{bold}</b>, post)
    last = m.index + m[0].length
  }
  parts.push(text.slice(last))
  return <>{parts}</>
}

const TABS = [
  ['stack', '기술스택'],
  ['arch', '아키텍처'],
  ['guide', '취업 가이드'],
  ['roadmap', '공부 로드맵'],
  ['jobs', '채용 공고'],
] as const

function CompanyProfile({ c, onStudyTech }: { c: CompanyStack; onStudyTech?: (tech: string) => void }) {
  const learning = useLearning()
  const [tab, setTab] = useState<string>('stack')
  const [liked, setLiked] = useState(false)
  const roles = Object.entries(c.roles).sort((a, b) => b[1] - a[1])
  const maxRole = Math.max(1, ...roles.map(([, n]) => n))
  const topRole = roles[0]
  const refs = useRef<Record<string, HTMLElement | null>>({})
  const go = (key: string) => {
    setTab(key)
    refs.current[key]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const tags = [
    `# 채용공고 ${c.posting_count}건`,
    topRole ? `# ${topRole[0]} ${topRole[1]}명 채용 중` : null,
    c.architecture[0] ? `# ${c.architecture[0].label}` : null,
  ].filter(Boolean) as string[]

  return (
    <div>
      {/* 프로필 카드 */}
      <section className="relative rounded-[30px] border border-[#e2e8ec] px-[37px] pt-[37px] pb-[31px]">
        <button
          type="button"
          onClick={() => setLiked((v) => !v)}
          aria-pressed={liked}
          aria-label="관심 기업"
          className="absolute right-[31px] top-[31px]"
        >
          <svg width="22" height="22" viewBox="0 0 22 22" fill={liked ? '#f45757' : 'none'} stroke={liked ? '#f45757' : '#b7b7b7'} strokeWidth="1.6" aria-hidden>
            <path d="M11 18s-6.5-4-6.5-8.5A3.5 3.5 0 0 1 11 7.2a3.5 3.5 0 0 1 6.5 2.3C17.5 14 11 18 11 18Z" />
          </svg>
        </button>
        <div className="flex flex-col sm:flex-row gap-[26px]">
          <span className="grid place-items-center w-24 h-24 shrink-0 rounded-3xl bg-white shadow-[0_6px_18px_rgba(0,0,0,0.08)] overflow-hidden">
            <CompanyMark name={c.name} size={96} />
          </span>
          <div className="min-w-0 flex-1 pr-6">
            <div className="flex flex-wrap items-center gap-x-[13px] gap-y-1">
              <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">{c.name}</h1>
              <span className="flex flex-wrap gap-1.5">
                <SizeTag size={c.size} />
                {c.domains.slice(0, 2).map((d) => (
                  <span key={d.name} className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]" title={d.evidence.join(', ')}>
                    {d.name}
                  </span>
                ))}
              </span>
            </div>
            <p className="mt-3 max-w-[650px] text-base leading-[26px] tracking-[-0.16px] text-[#474747]">
              <SummaryText text={c.summary} />
            </p>
            <div className="mt-[13px] flex flex-wrap gap-2">
              {tags.map((t) => (
                <span key={t} className="h-8 px-[15px] rounded-2xl border border-[#e2e2e2] bg-white text-[13px] leading-[30px] tracking-[-0.16px] text-[#474747]">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-[26px] grid grid-cols-2 md:grid-cols-4 gap-[10px]">
          <Stat label="채용중인 공고" value={String(c.posting_count)} unit="건" />
          <Stat label="가장 많이 뽑는 직군" value={topRole?.[0] ?? '-'} unit={topRole ? `${topRole[1]}건` : ''} />
          <Stat label="핵심 기술" value={c.top_tech.slice(0, 3).map((t) => t.name).join(' · ') || '-'} />
          <Stat label="공고 출처" value={c.sites.map((s) => SITE_NAME[s] ?? s).join(', ')} />
        </div>
      </section>

      {/* 탭 — 누르면 그 구역으로 내려간다 */}
      <div role="tablist" className="mt-[43px] flex overflow-x-auto no-scrollbar border-b border-[#e2e2e2]">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => go(key)}
            className={
              'relative shrink-0 min-w-[106px] px-[22px] pb-[13px] text-left text-[17px] leading-[25px] tracking-[-0.16px] ' +
              (tab === key ? 'font-bold text-[#272727] after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-[#272727]' : 'font-medium text-[#777] hover:text-[#272727]')
            }
          >
            {label}
          </button>
        ))}
      </div>

      {/* 기술스택 */}
      <Section refKey="stack" refs={refs} title="기술스택" note="채용공고 기반 · 숫자는 언급된 공고 수">
        <div className="mt-[22px]">
          {CAT_ORDER.filter((cat) => c.tech_categories[cat]?.length).map((cat) => (
            <div key={cat} className="flex gap-4 py-[14px] border-b border-[#eef1f3] last:border-b">
              <span className="w-[116px] shrink-0 pl-1 pt-[7px] text-[15px] font-bold leading-[21px] tracking-[-0.16px] text-[#272727]">{cat}</span>
              <div className="flex flex-wrap gap-2">
                {c.tech_categories[cat].map((t) => {
                  const hasCurr = !!learning.curricula[t.name]
                  const hasVids = (learning.resources[t.name]?.length ?? 0) > 0
                  const studiable = !!onStudyTech && (hasCurr || hasVids)
                  return (
                    <button
                      key={t.name}
                      type="button"
                      disabled={!studiable}
                      onClick={() => studiable && onStudyTech?.(t.name)}
                      title={studiable ? `${t.name} 학습 ${hasCurr ? '커리큘럼' : '영상'} 보기` : `${t.name} (공고 ${t.count}건)`}
                      className={
                        'inline-flex items-center gap-1.5 h-9 px-[17px] rounded-[18px] border border-[#d8d8d8] bg-white text-sm font-medium tracking-[-0.3px] text-[#272727] ' +
                        (studiable ? 'hover:border-[#272727] cursor-pointer' : 'cursor-default')
                      }
                    >
                      {t.name}
                      <span className="text-xs font-normal text-[#999] tabular-nums">{t.count}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 직군 분포 */}
      <Section title="채용 직군 분포">
        <div className="mt-[18px] flex flex-col gap-3">
          {roles.map(([role, n]) => (
            <div key={role} className="flex items-center">
              <span className="w-36 shrink-0 text-[15px] leading-[21px] tracking-[-0.16px] text-[#474747] truncate">{role}</span>
              <span className="flex-1 h-4 rounded-lg bg-[#f1f3f5] overflow-hidden">
                <span className="block h-full rounded-lg bg-[#f67979]" style={{ width: `${(n / maxRole) * 100}%` }} />
              </span>
              <span className="w-[58px] shrink-0 text-right text-[15px] font-medium leading-[21px] text-[#272727] tabular-nums">{n}건</span>
            </div>
          ))}
        </div>
      </Section>

      {/* 추정 아키텍처 */}
      <Section refKey="arch" refs={refs} title="추정 아키텍처">
        {c.architecture.length ? <ArchGrid items={c.architecture} /> : <p className="mt-4 text-sm text-[#999]">추론된 아키텍처 없음</p>}
      </Section>

      {/* 취업 가이드 + 공부 로드맵 */}
      {c.career_guide && (
        <CareerGuideBlock g={c.career_guide} refs={refs} videos={learning.resources} searchUrl={learning.searchUrl} />
      )}

      {/* 채용 공고 */}
      <Section refKey="jobs" refs={refs} title="채용중인 공고" note={`${c.name} ${c.posting_count}건 중 ${Math.min(8, c.postings.length)}건`}>
        <PostingList c={c} />
      </Section>
    </div>
  )
}

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="min-h-[111px] rounded-2xl border border-[#e2e8ec] bg-white px-[19px] pt-[17px] pb-3">
      <div className="text-[13px] leading-[19px] tracking-[-0.16px] text-[#777]">{label}</div>
      <div className="mt-1.5 text-lg font-bold leading-[26px] tracking-[-0.16px] text-[#272727] break-keep">
        {value}
        {unit && <span className="ml-0.5 text-sm font-normal text-[#474747]">{unit}</span>}
      </div>
    </div>
  )
}

function ArchGrid({ items }: { items: CompanyStack['architecture'] }) {
  const [all, setAll] = useState(false)
  const shown = all ? items : items.slice(0, 4)
  return (
    <>
      <div className="mt-[18px] grid sm:grid-cols-2 gap-3">
        {shown.map((a) => (
          <div key={a.label} className="min-h-[94px] rounded-[18px] border border-[#e2e8ec] px-[23px] pt-[21px] pb-4">
            <div className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">{a.label}</div>
            <div className="mt-1.5 text-sm leading-[21px] tracking-[-0.16px] text-[#666]">{a.why}</div>
          </div>
        ))}
      </div>
      {items.length > 4 && (
        <button type="button" onClick={() => setAll((v) => !v)} className="mt-3 text-[13px] text-[#777] hover:text-[#272727]">
          {all ? '접기' : `아키텍처 ${items.length - 4}개 더 보기`}
        </button>
      )}
    </>
  )
}

const POST_STEP = 8

function PostingList({ c }: { c: CompanyStack }) {
  const [shown, setShown] = useState(POST_STEP)
  const list: CompanyPosting[] = c.postings.slice(0, shown)
  return (
    <div className="mt-[22px]">
      <ul>
        {list.map((p, i) => {
          const roles = classifyRoles(p.title, [], '')
          return (
            <li key={`${p.url}-${i}`} className="border-b border-[#eef1f3]">
              <a href={p.url} target="_blank" rel="noreferrer" className="group flex items-center gap-[14px] min-h-[79px] px-1">
                <span className="grid place-items-center w-9 h-9 rounded-[9px] overflow-hidden shrink-0">
                  <CompanyMark name={c.name} size={36} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm leading-[21px] tracking-[-0.16px] text-[#666]">{c.name}</span>
                  <span className="block text-base font-medium leading-6 tracking-[-0.16px] text-[#272727] truncate group-hover:underline underline-offset-2">
                    {p.title || p.url}
                  </span>
                </span>
                {roles.length > 0 && (
                  <span className="hidden sm:inline shrink-0 rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] text-[#474747]">
                    {roles.join(' · ')}
                  </span>
                )}
                <span className="shrink-0 w-[60px] text-right text-sm text-[#999]">{p.site}</span>
              </a>
            </li>
          )
        })}
      </ul>
      {c.postings.length > POST_STEP && (
        <button
          type="button"
          onClick={() => setShown((n) => (n >= c.postings.length ? POST_STEP : n + 20))}
          className="mt-5 w-full inline-flex items-center justify-center gap-2 h-11 rounded-[30px] bg-[#272727] text-base font-medium tracking-[-0.16px] text-white hover:bg-black"
        >
          {shown >= c.postings.length ? '접기' : `${c.name} 공고 전체 보기`}
          <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
            <path d="M2.5 1.5 6 5l-3.5 3.5" />
          </svg>
        </button>
      )}
    </div>
  )
}

function CareerGuideBlock({
  g,
  refs,
  videos,
  searchUrl,
}: {
  g: CareerGuide
  refs: React.MutableRefObject<Record<string, HTMLElement | null>>
  videos: Record<string, LearningVideo[]>
  searchUrl: string
}) {
  const [openStage, setOpenStage] = useState<number | null>(null)
  const [extra, setExtra] = useState(false)
  // "{tech}+강의" 검색 URL — 큐레이션 영상이 없을 때의 폴백
  const ytSearch = (tech: string) =>
    searchUrl
      ? searchUrl.replace('{tech}', encodeURIComponent(tech))
      : `https://www.youtube.com/results?search_query=${encodeURIComponent(tech + ' 강의')}`
  // 한 단계의 기술들에서 큐레이션 영상(기술당 1개) 모으기 — 중복 제거
  const stageVideos = (techs: string[]): LearningVideo[] => {
    const out: LearningVideo[] = []
    const seen = new Set<string>()
    for (const t of techs) {
      const v = videos[t]?.[0]
      if (v && !seen.has(v.url)) {
        seen.add(v.url)
        out.push(v)
      }
    }
    return out
  }

  return (
    <>
      <Section refKey="guide" refs={refs} title="이런 사람을 원합니다" note="채용 데이터 기반 추론">
        {g.wants.length > 0 && (
          <ul className="mt-[22px] rounded-[20px] bg-[#f7f9fa] px-[26px] py-2">
            {g.wants.map((w, i) => (
              <li key={i} className="flex gap-[11px] py-3 border-b border-[#e8ecef] last:border-b-0 text-base leading-6 tracking-[-0.16px] text-[#272727]">
                <span className="shrink-0 font-bold text-(--color-accent)">✓</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        )}
        {(g.tasks.length > 0 || g.study_blogs.length > 0) && (
          <div className="mt-3">
            <button type="button" onClick={() => setExtra((v) => !v)} aria-expanded={extra} className="text-[13px] text-[#777] hover:text-[#272727]">
              {extra ? '입사 후 업무·추천 블로그 접기' : '입사 후 업무·추천 블로그 더 보기'}
            </button>
            {extra && (
              <div className="mt-3 grid gap-4 text-sm leading-relaxed">
                {g.tasks.length > 0 && (
                  <ul className="space-y-1">
                    {g.tasks.map((t, i) => (
                      <li key={i} className="flex gap-2 text-[#272727]">
                        <span className="text-(--color-accent)">▸</span>
                        {t}
                      </li>
                    ))}
                  </ul>
                )}
                {g.study_blogs.length > 0 && (
                  <ul className="space-y-1.5">
                    {g.study_blogs.map((b, i) => (
                      <li key={i}>
                        <a href={b.url} target="_blank" rel="noreferrer" className="text-[#272727] underline-offset-2 hover:underline">
                          {b.title}
                        </a>
                        <span className="ml-1.5 text-xs text-[#999]">
                          · {b.company}
                          {b.country ? ` (${b.country})` : ''}
                          {b.why ? ` · ${b.why}` : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </Section>

      {g.roadmap.length > 0 && (
        <Section refKey="roadmap" refs={refs} title="공부 로드맵" note="이 회사 스택 기준 · 순서대로">
          <ol className="mt-[22px] flex flex-col gap-[10px]">
            {g.roadmap.map((s, i) => {
              const vids = stageVideos(s.techs)
              const open = openStage === i
              return (
                <li key={i} className="rounded-[20px] border border-[#e2e8ec] px-[25px] py-[21px]">
                  <div className="flex items-center gap-[18px]">
                    <span className="grid place-items-center w-10 h-10 shrink-0 rounded-full bg-[#272727] text-[17px] font-bold text-white">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start gap-3">
                        <span className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">{s.stage.replace(/^\d+\.\s*/, '')}</span>
                        <button
                          type="button"
                          onClick={() => setOpenStage(open ? null : i)}
                          aria-expanded={open}
                          className="ml-auto shrink-0 inline-flex items-center gap-1.5 text-[13px] tracking-[-0.16px] text-(--color-accent)"
                        >
                          {open ? '접기' : vids.length > 0 ? `추천 강의 ${vids.length}개` : '공부 팁 보기'}
                          <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden className={open ? 'rotate-90' : ''}>
                            <path d="M2.5 1.5 6 5l-3.5 3.5" />
                          </svg>
                        </button>
                      </div>
                      <div className="mt-[3px] text-sm leading-[21px] tracking-[-0.16px] text-[#666]">{s.goal}</div>
                      <div className="mt-[9px] flex flex-wrap gap-1.5">
                        {s.techs.map((t) => (
                          <a
                            key={t}
                            href={ytSearch(t)}
                            target="_blank"
                            rel="noreferrer"
                            title={`유튜브에서 '${t} 강의' 검색`}
                            className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] text-[#5b4fd6] hover:underline"
                          >
                            {t}
                          </a>
                        ))}
                      </div>
                    </div>
                  </div>
                  {open && (
                    <div className="mt-4 pl-[58px]">
                      {vids.length > 0 && (
                        <div className="grid sm:grid-cols-2 gap-2">
                          {vids.map((v) => (
                            <a key={v.url} href={v.url} target="_blank" rel="noreferrer" className="flex gap-2 rounded-xl border border-[#e2e8ec] p-1.5 hover:border-[#999]">
                              <img src={v.thumbnail} alt="" loading="lazy" className="w-20 h-12 object-cover rounded shrink-0" />
                              <div className="min-w-0">
                                <div className="text-[12px] leading-snug text-[#272727] line-clamp-2">{v.title}</div>
                                <div className="mt-0.5 text-[10px] text-[#999] truncate">
                                  {v.channel} · {v.length}
                                </div>
                              </div>
                            </a>
                          ))}
                        </div>
                      )}
                      {s.tips.length > 0 && (
                        <ul className="mt-2 space-y-0.5">
                          {s.tips.map((t, j) => (
                            <li key={j} className="text-[13px] leading-relaxed text-[#666]">
                              · {t}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
        </Section>
      )}
    </>
  )
}

function Section({
  title,
  note,
  refKey,
  refs,
  children,
}: {
  title: string
  note?: string
  refKey?: string
  refs?: React.MutableRefObject<Record<string, HTMLElement | null>>
  children: ReactNode
}) {
  return (
    <section
      ref={(el) => {
        if (refKey && refs) refs.current[refKey] = el
      }}
      className="scroll-mt-4 mt-[43px]"
    >
      <h2 className="flex flex-wrap items-baseline gap-x-[13px]">
        <span className="text-xl font-bold leading-[29px] tracking-[-0.2px] text-[#272727]">{title}</span>
        {note && <span className="text-sm tracking-[-0.2px] text-[#999]">{note}</span>}
      </h2>
      {children}
    </section>
  )
}
