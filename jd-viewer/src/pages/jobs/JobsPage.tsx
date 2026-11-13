import { useEffect, useMemo, useState } from 'react'
import { SiteFooter } from '../../components/SiteFooter'
import { ErrorState, Loader } from '../../components/ui'
import { JobDetail } from '../../features/jobs/components/JobDetail'
import { JobList } from '../../features/jobs/components/JobList'
import { fetchHome, type HomeBoard } from '../../features/home/api'
import { CategoryPanel } from '../../features/jobs/components/CategoryPanel'
import { HotJobs } from '../../features/jobs/components/HotJobs'
import { useJobBoardContext } from '../../features/jobs/hooks/useJobBoard'
import { onLinkClick, useRoute } from '../../utils/navigation'
import { absUrl, SITE_NAME, useSeo } from '../../utils/seo'
import { breadcrumbJsonLd, jobDescription, jobJsonLd, jobTitle, paths, TAB_SEO } from '../../utils/urls'

/** `/jobs` · `/jobs/<사이트>-<번호>` — 잡 리스트와 공고 상세. 상태는 app/providers 의 JobBoard. */
export function JobsPage() {
  const b = useJobBoardContext()
  const route = useRoute()

  // 공고 상세는 공고별 제목·설명·JobPosting 구조화 데이터를 쓴다. 검색어가 걸린 목록은
  // 색인하지 않는다(같은 목록의 무한 변형이라 색인해봐야 중복 페이지만 는다).
  const seo = useMemo(() => {
    const selected = b.selected
    if (selected) {
      const url = absUrl(paths.job(selected))
      return {
        title: jobTitle(selected),
        description: jobDescription(selected),
        canonical: url,
        jsonLd: {
          '@context': 'https://schema.org',
          '@graph': [
            jobJsonLd(selected, url),
            breadcrumbJsonLd([
              { name: SITE_NAME, url: absUrl('/') },
              { name: selected.company, url },
            ]),
          ],
        },
      }
    }
    return {
      title: TAB_SEO.jobs.title,
      description: TAB_SEO.jobs.desc,
      canonical: absUrl(route.path),
      robots: b.filter.query && b.isJobList ? 'noindex, follow' : undefined,
    }
  }, [b.selected, b.filter.query, b.isJobList, route.path])
  useSeo(seo)

  if (b.loading) return <Loader label="채용 데이터 불러오는 중…" />
  if (b.error) {
    return (
      <ErrorState
        title="데이터를 불러오지 못했습니다"
        detail={b.error}
        hint={
          b.apiMode ? (
            <>뷰어 API(/api/jobs)와 정본 DB 가 떠 있는지 확인하세요.</>
          ) : (
            <>public/all_jobs_enriched.json 이 있는지 확인하세요.</>
          )
        }
      />
    )
  }
  if (b.selectedLoading) return <Loader label="공고 불러오는 중…" />
  if (b.selected) {
    // 공고를 고르면 목록을 통째로 갈아끼운다. 모달로 띄우면 오른쪽 취업 가이드가
    // 들어갈 폭이 안 나오고, 좁은 칸에 겹쳐 둔 JD 와 가이드는 둘 다 안 읽힌다.
    return (
      <div key="jobdetail" className="flex flex-1 min-h-0 jd-fade-in">
        <JobDetail key={b.selected.url} job={b.selected} onOpenUrl={b.openJobByUrl} />
      </div>
    )
  }
  if (b.detail) {
    // 주소에는 공고 id 가 있는데 데이터에 없다 — 마감돼 걷힌 공고이거나 오래된 링크.
    return (
      <ErrorState
        title="없는 공고입니다"
        detail={`공고 ${b.detail} 을(를) 찾지 못했습니다.`}
        hint={
          <a href="/jobs" onClick={onLinkClick('/jobs')} className="text-(--color-accent) underline">
            전체 공고 목록으로
          </a>
        }
      />
    )
  }
  return <JobListView />
}

const SOURCES = '사람인 · 잡코리아 · 인크루트 · 게임잡 · 원티드 · 점핏 · 각 사 채용 페이지'

/**
 * 잡 리스트(캐치형 02) — 지금 주목받는 공고 → 큰 검색칸 → 전체 카테고리(탭 필터) → 전체 공고 목록 → 바닥 띠.
 * 왼쪽 사이드바는 없앴다. 필터 축은 전체 카테고리로, 모집 상태·마감 확인·시군구는 목록 위 줄로 옮겼다.
 */
function JobListView() {
  const b = useJobBoardContext()
  const { filter, setFilter } = b
  const [more, setMore] = useState(false)
  const [home, setHome] = useState<HomeBoard | null>(null)
  const onlyRegion = filter.regions.size === 1 ? [...filter.regions][0] : null

  // 주목받는 공고 칸과 바닥 띠의 갱신 시각·회사 수 — 메인과 같은 /api/home(없으면 스냅숏).
  useEffect(() => {
    const ctl = new AbortController()
    fetchHome({ size: '', industry: '', sort: 'popular', limit: 48 }, { signal: ctl.signal })
      .then(setHome)
      .catch(() => {})
    return () => ctl.abort()
  }, [])

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white jd-fade-in">
      <div className="jd-container pt-[43px]">
        <HotJobs companies={home?.companies ?? null} />

        <form role="search" onSubmit={(e) => e.preventDefault()} className="mt-9 flex gap-2.5">
          <label className="flex-1 min-w-0 flex items-center gap-2.5 h-[52px] rounded-[26px] border border-[#c4c4c4] pl-[23px] pr-5 focus-within:border-[#272727]">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2" aria-hidden className="shrink-0">
              <circle cx="8.5" cy="8.5" r="5.5" />
              <path d="M12.5 12.5 16 16" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              value={filter.query}
              onChange={(e) => setFilter({ ...filter, query: e.target.value })}
              placeholder={b.semantic && b.searchAvailable ? '예: 재택 되는 백엔드 자리' : '기업명/키워드/기술스택을 입력해주세요'}
              aria-label="공고 검색"
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

        <div className="mt-[30px]">
          <CategoryPanel filter={filter} setFilter={setFilter} facets={b.facets} />
        </div>

        <section data-jobs-top aria-label="전체 공고" className="scroll-mt-4 mt-[55px]">
          <div className="flex flex-wrap items-center justify-between gap-2 pl-[10px]">
            <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">전체 공고</h2>
            <p className="pr-[11px] text-[15px] tracking-[-0.16px] text-[#666] tabular-nums">
              전체 <b className="font-bold text-[#272727]">{b.filteredCount.toLocaleString()}</b>건 / {b.totalCount.toLocaleString()}건
            </p>
          </div>
          <div className="mt-[18px] flex flex-wrap items-center gap-2.5">
            {/* 정렬은 지금 한 가지(최신순)뿐이다 — 목록 API 가 정한 순서를 그대로 쓴다. */}
            <Select label="정렬" value="new" onChange={() => {}} options={[['new', '최신순']]} />
            <Select
              label="모집 상태"
              value={filter.closed}
              onChange={(v) => setFilter({ ...filter, closed: v as typeof filter.closed })}
              options={[
                ['hide', '모집중만'],
                ['show', '마감 포함'],
                ['only', '마감만'],
              ]}
            />
            <button
              type="button"
              onClick={() => setMore((v) => !v)}
              aria-expanded={more}
              className="ml-2 inline-flex items-center gap-1.5 text-[17px] font-bold tracking-[-0.16px] text-[#494949]"
            >
              상세조건
              <Caret up={more} color="#494949" />
            </button>
            {b.searchAvailable && (
              <span className="ml-auto flex items-center gap-2 pr-[1px]">
                {b.semantic && b.searchState.loading && <span className="text-xs text-[#999]">찾는 중…</span>}
                {b.semantic && !b.searchState.loading && b.searchState.engines && (
                  <span className="text-xs text-[#999] tabular-nums">
                    키워드 {b.searchState.engines.fts} · 의미 {b.searchState.engines.vector}
                  </span>
                )}
                <button
                  type="button"
                  role="switch"
                  aria-checked={b.semantic}
                  onClick={() => b.setSemantic(!b.semantic)}
                  title="키워드와 의미를 함께 보는 검색 (문장으로 물어도 됩니다)"
                  className={'text-base font-medium tracking-[-0.16px] ' + (b.semantic ? 'text-(--color-accent)' : 'text-[#999]')}
                >
                  의미 검색
                </button>
              </span>
            )}
          </div>
          {more && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-[#f8f8f8] px-4 py-3 text-[13px]">
              {filter.closed !== 'only' && (
                <>
                  <span className="mr-1 font-bold text-[#272727]">마감 확인</span>
                  {(
                    [
                      ['show', '전체'],
                      ['hide', '확인된 공고만'],
                    ] as const
                  ).map(([v, label]) => (
                    <Pill key={v} on={filter.unverified === v} onClick={() => setFilter({ ...filter, unverified: v })}>
                      {label}
                    </Pill>
                  ))}
                </>
              )}
              {onlyRegion && b.facets.districts.length > 0 && (
                <>
                  <span className="ml-4 mr-1 font-bold text-[#272727]">{onlyRegion} 시·군·구</span>
                  {b.facets.districts.map((d) => (
                    <Pill
                      key={d.name}
                      on={filter.districts.has(d.name)}
                      onClick={() => {
                        const next = new Set(filter.districts)
                        if (next.has(d.name)) next.delete(d.name)
                        else next.add(d.name)
                        setFilter({ ...filter, districts: next })
                      }}
                    >
                      {d.name} <span className="text-[#999]">{d.count}</span>
                    </Pill>
                  ))}
                </>
              )}
            </div>
          )}
          <div className="mt-[17px] border-t border-[#e2e2e2]">
            <JobList jobs={b.filtered} server={b.page} noData={b.noData} />
          </div>
        </section>
      </div>
      <SiteFooter updated={home?.generated_at} jobs={b.totalCount} companies={home?.totals.companies} sources={SOURCES} />
    </div>
  )
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: [string, string][]
}) {
  return (
    <label className="relative inline-flex items-center h-10 rounded-md border border-[#d8d8d8] bg-white">
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none h-full bg-transparent pl-[17px] pr-[36px] text-sm font-medium tracking-[-0.16px] text-[#272727] outline-none cursor-pointer"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-[17px]">
        <Caret color="#272727" />
      </span>
    </label>
  )
}

function Caret({ up, color }: { up?: boolean; color: string }) {
  return (
    <svg width="10" height="8" viewBox="0 0 10 8" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" aria-hidden>
      <path d={up ? 'M1.5 5.5 5 2l3.5 3.5' : 'M1.5 2.5 5 6l3.5-3.5'} />
    </svg>
  )
}

function Pill({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'h-[30px] px-3 rounded-[15px] border bg-white ' +
        (on ? 'border-(--color-accent) text-(--color-accent)' : 'border-[#e2e2e2] text-[#474747] hover:border-[#999]')
      }
    >
      {children}
    </button>
  )
}
