import { Fragment, useCallback, useEffect, useState } from 'react'
import { SiteFooter } from '../../components/SiteFooter'
import { ErrorState, Loader } from '../../components/ui'
import { fetchHome, type HomeBoard, type HomeSection } from '../../features/home/api'
import { PICK_ICONS, PickCard } from '../../features/home/components/CompanyCard'
import { CompanyPanel } from '../../features/home/components/CompanyPanel'
import { HeroRow } from '../../features/home/components/HeroBanner'
import { RankSection } from '../../features/home/components/RankSection'
import { TrendPick } from '../../features/home/components/TrendPick'
import { useJobBoardContext } from '../../features/jobs/hooks/useJobBoard'
import { onLinkClick, useRoute, useSetQuery } from '../../utils/navigation'
import { absUrl, useSeo } from '../../utils/seo'
import { paths, TAB_SEO } from '../../utils/urls'

const PAGE = 16
// 추천공고 줄(주목 회사 16곳 다음 회사들)까지 한 번에 받는다.
const FETCH_MIN = 48
// 위 줄 셋(경력 단계·새로움)과 아래 줄 셋(회사 성격). 업종 구역은 '전체 카테고리 보기' 로 편다.
const LEAD = ['entry', 'experienced', 'today']
const KIND = ['intern', 'midsmall', 'overseas']
/** 회사 카드가 놓인 구역 — 펼친 칸이 어느 구역 아래에 들어가나 */
type Where = 'cos' | 'trend' | 'picks'

/**
 * `/` — 회사별 메인(Penpot「JD Viewer」01 캐치형 1920). 위에서 아래로:
 *   ① 바로가기 넷 + 남색 배너   ② 가장 주목받는 회사 카드(4열, 누르면 그 줄 아래로 공고가 펼쳐진다)
 *   ③ 오늘의 트렌드 Pick(회색 띠)   ④ 카테고리별 인기 TOP 50(3열 × 2줄)
 *   ⑤ 추천공고 — 업종별 1위 공고(회색 띠)   ⑥ 바닥 띠
 * 공고 하나하나를 거르는 화면은 `/jobs`.
 */
export function HomePage() {
  const route = useRoute()
  const setQuery = useSetQuery()
  const [limit, setLimit] = useState(PAGE)
  const [allCats, setAllCats] = useState(false)
  const [d, setD] = useState<HomeBoard | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const open = route.query.get('company')
  // 같은 회사가 여러 구역(주목 회사·트렌드·추천)에 나온다 — 누른 구역 아래에 펼친다.
  const [openIn, setOpenIn] = useState<Where | null>(null)
  const { countsReady, totalCount } = useJobBoardContext()

  useSeo({ title: TAB_SEO.home.title, description: TAB_SEO.home.desc, canonical: absUrl('/') })

  useEffect(() => {
    const ctl = new AbortController()
    // 상시 공고만 있는 회사(큰 회사 채용페이지의 늘 열린 공고)는 메인 카드에서 뺀다 — `/top/always` 에 따로 모은다.
    fetchHome({ size: '', industry: '', sort: 'popular', limit: Math.max(limit, FETCH_MIN), always: 'exclude' }, { signal: ctl.signal })
      .then((x) => {
        setD(x)
        setErr(null)
      })
      .catch((e: Error) => e.name !== 'AbortError' && setErr(e.message))
    return () => ctl.abort()
  }, [limit])

  const openCompany = (slug: string, where: Where) => {
    setOpenIn(where)
    setQuery('company', open === slug && openIn === where ? null : slug, { push: true })
  }
  const closePanel = useCallback(() => setQuery('company', null, { push: true }), [setQuery])

  if (err && !d) {
    return (
      <ErrorState
        title="메인 화면을 불러오지 못했습니다"
        detail={err}
        hint={
          <a href={paths.jobs()} onClick={onLinkClick(paths.jobs())} className="text-(--color-accent) underline">
            잡 리스트로 가기
          </a>
        }
      />
    )
  }
  if (!d) return <Loader label="회사별 공고 묶는 중…" />

  const byKey = (keys: string[]) => keys.map((k) => d.sections.find((s) => s.key === k)).filter(Boolean) as HomeSection[]
  const industries = d.sections.filter((s) => s.key.startsWith('ind:'))
  const always = d.sections.find((s) => s.key === 'always')
  const cats = [...byKey(LEAD), ...byKey(KIND), ...(allCats ? industries : [])]
  const shownCos = d.companies.slice(0, limit)
  // 추천공고 — 주목 회사 16곳 다음부터, 이번 주 새 공고가 많은 순으로 여덟 곳.
  const picks = [...d.companies.slice(PAGE)].sort((a, b) => b.new_7d - a.new_7d).slice(0, 8)
  // 주소(?company=)로 바로 들어왔으면 누른 구역을 모른다 — 카드가 있는 구역, 없으면 주목 회사 아래.
  const where: Where | null = !open
    ? null
    : (openIn ?? (shownCos.some((c) => c.slug === open) ? 'cos' : picks.some((c) => c.slug === open) ? 'picks' : 'cos'))
  const unfold = (w: Where) => (open && where === w ? <CompanyPanel key={open} slug={open} onClose={closePanel} /> : null)
  const orphan = where === 'cos' && !shownCos.some((c) => c.slug === open)

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[38px]">
        <HeroRow d={d} />

        {/* ② 가장 주목받는 회사 */}
        <section id="sec-companies" aria-label="회사" className="scroll-mt-16 mt-[39px]">
          <div className="flex flex-wrap items-baseline justify-between gap-2 pl-[10px]">
            <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
              지금, JD Viewer에서 가장 주목받는 회사예요!
            </h2>
            {always && (
              <a
                href={paths.top('always')}
                onClick={onLinkClick(paths.top('always'))}
                className="text-[13px] text-[#777] hover:text-[#272727]"
              >
                마감 없는 상시 채용 {always.total.toLocaleString()}건은 따로 모았어요 ›
              </a>
            )}
          </div>
          {/* grid-flow-dense — 펼친 칸(전체 너비)을 누른 카드 뒤에 꽂아도 같은 줄의 나머지 카드가 제자리를 지킨다 */}
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 grid-flow-dense gap-2">
            {shownCos.map((c, i) => (
              <Fragment key={c.slug}>
                <PickCard
                  name={c.name}
                  logo={c.logo}
                  dday={c.soonest_dday}
                  chip={`${PICK_ICONS[i % 4]} 이번 주 +${c.new_7d}${c.industry !== '기타' ? ` · ${c.industry}` : ''}`}
                  title={c.titles[0]?.title ?? ''}
                  active={open === c.slug && where === 'cos'}
                  onOpen={() => openCompany(c.slug, 'cos')}
                />
                {open === c.slug && unfold('cos')}
              </Fragment>
            ))}
            {orphan && unfold('cos')}
          </div>
          {shownCos.length < d.totals.companies && (
            <div className="mt-[14px] text-center">
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE)}
                className="home-press inline-flex items-center gap-[7px] h-[26px] pl-[15px] pr-[11px] rounded-[13px] border border-[#d8d8d8] bg-white text-xs font-medium tracking-[-0.3px] text-[#272727] hover:border-[#272727]"
              >
                회사 {d.totals.companies.toLocaleString()}곳 전체 보기
                <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
                  <circle cx="7" cy="7" r="7" fill="#272727" />
                  <path d="M5.5 4l3 3-3 3" fill="none" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" transform="rotate(90 7 7)" />
                </svg>
              </button>
            </div>
          )}
        </section>
      </div>

      {/* ③ 오늘의 트렌드 Pick */}
      <section aria-label="트렌드 Pick" className="mt-[70px] bg-[#f3f6f8] pt-[51px] pb-[61px]">
        <div className="jd-container">
          <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">회원님을 위한 오늘의 트렌드 Pick!</h2>
          <p className="text-base leading-6 tracking-[-0.16px] text-[#666]">이번 주 새로 뜬 공고를 기반으로 채용정보를 큐레이션 해드려요.</p>
          <div className="mt-[25px]">
            <TrendPick d={d} onOpen={(slug) => openCompany(slug, 'trend')} />
          </div>
          {where === 'trend' && <div className="mt-6">{unfold('trend')}</div>}
        </div>
      </section>

      {/* ④ 카테고리별 인기 공고 */}
      <section aria-label="카테고리별 인기 공고" className="jd-container pt-[61px] pb-[70px]">
        <div className="flex flex-wrap items-center justify-between gap-3 pl-[10px]">
          <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">다양한 카테고리별 인기 공고를 한눈에 볼 수 있어요.</h2>
          <button
            type="button"
            onClick={() => setAllCats((v) => !v)}
            aria-expanded={allCats}
            className="inline-flex items-center gap-[7px] h-8 px-[15px] rounded-2xl border border-(--color-accent) text-[13px] font-medium text-(--color-accent) hover:bg-(--color-accent-weak)"
          >
            {allCats ? '주요 카테고리만 보기' : '전체 카테고리 보기'}
            <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
              <path d="M2.5 1.5 6 5l-3.5 3.5" />
            </svg>
          </button>
        </div>
        <div className="mt-[26px] grid gap-7 md:grid-cols-2 lg:grid-cols-3 items-start">
          {cats.map((s) => (
            <RankSection key={s.key} s={s} ranked={LEAD.includes(s.key)} />
          ))}
        </div>
      </section>

      {/* ⑤ 추천공고 — 업종별 1위 */}
      {picks.length > 0 && (
        <section aria-label="추천공고" className="bg-[#f3f6f8] pt-[52px] pb-[80px]">
          <div className="jd-container">
            <p className="text-[13px] font-medium leading-[19px] text-(--color-accent)">› JD Viewer 추천공고</p>
            <h2 className="mt-[3px] text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">적극 채용중인 기업이에요</h2>
            <p className="mt-0.5 text-base leading-6 tracking-[-0.16px] text-[#666]">업종별 1위 공고를, 마감 전에 빠르게 확인해 보세요!</p>
            <div className="mt-[26px] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 grid-flow-dense gap-2">
              {picks.map((c, i) => (
                <Fragment key={c.slug}>
                  <PickCard
                    name={c.name}
                    logo={c.logo}
                    dday={c.soonest_dday}
                    chip={`${PICK_ICONS[(i + 1) % 4]} 이번 주 +${c.new_7d}${c.industry !== '기타' ? ` · ${c.industry}` : ''}`}
                    title={c.titles[0]?.title ?? ''}
                    active={open === c.slug && where === 'picks'}
                    onOpen={() => openCompany(c.slug, 'picks')}
                  />
                  {open === c.slug && unfold('picks')}
                </Fragment>
              ))}
            </div>
          </div>
        </section>
      )}

      <SiteFooter updated={d.generated_at} jobs={countsReady ? totalCount : d.totals.jobs} companies={d.totals.companies} />

    </div>
  )
}
