import { useCallback, useEffect, useState } from 'react'
import { ErrorState, Loader } from '../../components/ui'
import { fetchHome, type HomeBoard, type HomeSection, type HomeSort } from '../../features/home/api'
import { CompanyCard } from '../../features/home/components/CompanyCard'
import { CompanyPanel } from '../../features/home/components/CompanyPanel'
import { LogoMarquee } from '../../features/home/components/LogoMarquee'
import { RankSection } from '../../features/home/components/RankSection'
import { useCountUp } from '../../features/home/hooks/useCountUp'
import { onLinkClick, useRoute, useSetQuery } from '../../utils/navigation'
import { absUrl, useSeo } from '../../utils/seo'
import { paths, TAB_SEO } from '../../utils/urls'

const PAGE = 12
const SORTS: { key: HomeSort; label: string }[] = [
  { key: 'popular', label: '주목순' },
  { key: 'new', label: '최신 공고순' },
  { key: 'count', label: '공고 많은 순' },
]
// 맨 위 세 구역(경력 단계·새로움)과 그다음 세 구역(회사 성격). 나머지는 업종 구역.
const LEAD = ['entry', 'experienced', 'today']
const KIND = ['intern', 'midsmall', 'overseas']

/**
 * `/` — 회사별 메인. 캐치 첫 화면처럼 위에서 아래로 내리며 본다.
 *   ① 지금 뽑는 회사 로고 띠와 숫자(이 화면의 유일한 연출)
 *   ② 회사 카드 — 규모로만 고른다. 누르면 오른쪽 패널(휴대폰은 아래 시트)에 그 회사 IT 공고
 *   ③ 순위 구역 — 신입·경력·오늘 뜬 / 인턴·교육생·중견중소·해외 / 업종별(은행·금융·게임…).
 *      업종을 칩으로 골라 갈아 끼우지 않고, 구역마다 TOP 50 을 늘어놓고 더보기로 편다.
 * 공고 하나하나를 거르는 화면은 `/jobs`.
 */
export function HomePage() {
  const route = useRoute()
  const setQuery = useSetQuery()
  const [size, setSize] = useState('')
  const [sort, setSort] = useState<HomeSort>('popular')
  const [limit, setLimit] = useState(PAGE)
  const [d, setD] = useState<HomeBoard | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const open = route.query.get('company')

  useSeo({ title: TAB_SEO.home.title, description: TAB_SEO.home.desc, canonical: absUrl('/') })

  useEffect(() => {
    const ctl = new AbortController()
    fetchHome({ size, industry: '', sort, limit }, { signal: ctl.signal })
      .then((x) => {
        setD(x)
        setErr(null)
      })
      .catch((e: Error) => e.name !== 'AbortError' && setErr(e.message))
    return () => ctl.abort()
  }, [size, sort, limit])

  const pick = (f: () => void) => {
    f()
    setLimit(PAGE)
  }
  const openCompany = (slug: string) => setQuery('company', open === slug ? null : slug, { push: true })
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

  const allSizes = d.facets.sizes.reduce((a, x) => a + x.n, 0)
  const byKey = (keys: string[]) => keys.map((k) => d.sections.find((s) => s.key === k)).filter(Boolean) as HomeSection[]
  const lead = byKey(LEAD)
  const kind = byKey(KIND)
  const industries = d.sections.filter((s) => s.key.startsWith('ind:'))

  return (
    <div data-scroll className={'flex-1 min-h-0 overflow-auto jd-canvas ' + (open ? 'md:pr-[460px]' : '')}>
      <Hero d={d} onOpen={openCompany} />

      {/* 구역으로 건너뛰는 막대 — 고르는 필터가 아니라 목차다. 스크롤해도 위에 붙어 있다 */}
      <nav
        aria-label="구역"
        className="sticky top-0 z-20 bg-(--color-bg) border-b border-(--color-border-soft) shadow-[0_8px_16px_-12px_rgba(0,0,0,0.18)]"
      >
        <div className="mx-auto max-w-[1240px] px-4 sm:px-6 py-2.5 flex gap-1.5 overflow-x-auto no-scrollbar">
          <Jump to="sec-companies">회사별</Jump>
          {[...lead, ...kind, ...industries].map((s) => (
            <Jump key={s.key} to={`sec-${s.key}`}>{s.title}</Jump>
          ))}
        </div>
      </nav>

      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 pb-14">
        {/* ② 회사 카드 */}
        <section id="sec-companies" aria-label="회사" className="scroll-mt-16 pt-7">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
            <div>
              <h2 className="text-xl sm:text-2xl font-extrabold tracking-[-0.02em] text-(--color-text)">회사별로 보기</h2>
              <p className="mt-1 text-[13px] text-(--color-muted)">카드를 누르면 그 회사가 지금 구하는 IT 공고가 열려요</p>
            </div>
            <select
              value={sort}
              onChange={(e) => pick(() => setSort(e.target.value as HomeSort))}
              className="text-sm rounded-xl border border-(--color-border) bg-(--color-panel) px-2.5 py-2"
              aria-label="정렬"
            >
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
          <div role="tablist" aria-label="기업 규모" className="mb-4 flex overflow-x-auto no-scrollbar gap-1.5">
            <SizeTab on={!size} onClick={() => pick(() => setSize(''))} label="전체" n={allSizes} />
            {d.facets.sizes.map((s) => (
              <SizeTab key={s.name} on={size === s.name} onClick={() => pick(() => setSize(s.name))} label={s.name} n={s.n} />
            ))}
          </div>
          <div key={`${size}|${sort}`} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5 sm:gap-3">
            {d.companies.map((c, i) => (
              <CompanyCard key={c.slug} c={c} i={i % PAGE} active={open === c.slug} onOpen={() => openCompany(c.slug)} />
            ))}
          </div>
          {d.companies.length < d.totals.companies && (
            <div className="mt-5 text-center">
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE * 2)}
                className="home-press px-6 py-2.5 rounded-full border border-(--color-border) bg-(--color-panel) text-sm font-semibold hover:border-(--color-text)"
              >
                회사 더보기
                <span className="ml-2 font-normal text-(--color-faint) tabular-nums">
                  {d.companies.length} / {d.totals.companies.toLocaleString()}
                </span>
              </button>
            </div>
          )}
        </section>

        {/* ③ 순위 구역 */}
        <Group
          title="지금 많이 보는 공고"
          note="순위는 회사 규모, 그 회사가 이번 주에 낸 공고 수, 공고가 새것인지, 마감이 가까운지로 매겨요. 한 회사는 구역마다 두 건까지만."
        >
          {lead.map((s) => <RankSection key={s.key} s={s} />)}
        </Group>

        <Group title="회사 성격별">
          {kind.map((s) => <RankSection key={s.key} s={s} />)}
        </Group>

        <Group title="업종별" note="업종은 회사 이름으로 가른 추정이라, 어디에도 안 맞는 회사는 빠져 있어요.">
          {industries.map((s) => <RankSection key={s.key} s={s} />)}
        </Group>

        <p className="mt-12 text-center text-xs leading-relaxed text-(--color-faint)">
          공고 하나하나를 기술스택·지역으로 거르려면{' '}
          <a href={paths.jobs()} onClick={onLinkClick(paths.jobs())} className="text-(--color-accent) hover:underline">
            잡 리스트
          </a>
          에서 볼 수 있어요.
        </p>
      </div>

      {open && <CompanyPanel key={open} slug={open} onClose={closePanel} />}
    </div>
  )
}

/** 첫 화면 — 숫자 셋이 한 번 올라가고, 그 아래로 지금 뽑는 회사 로고가 흐른다. */
function Hero({ d, onOpen }: { d: HomeBoard; onOpen: (slug: string) => void }) {
  const jobs = useCountUp(d.totals.jobs)
  const cos = useCountUp(d.totals.companies)
  const entry = useCountUp(d.sections.find((s) => s.key === 'entry')?.total ?? 0)
  return (
    <section className="relative overflow-hidden border-b border-(--color-border-soft) bg-(--color-panel)">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -right-32 w-[520px] h-[520px] rounded-full opacity-[0.12] blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--color-accent) 0%, transparent 65%)' }}
      />
      <div className="relative mx-auto max-w-[1240px] px-4 sm:px-6 pt-7 sm:pt-10 pb-6">
        <h1 className="text-[26px] sm:text-[34px] lg:text-[40px] font-extrabold leading-[1.15] tracking-[-0.03em] text-(--color-text)">
          오늘 개발자를 찾는 회사
          <span className="block text-(--color-muted) font-bold text-[17px] sm:text-[21px] lg:text-[23px] tracking-[-0.02em] mt-1.5">
            공고를 회사별로 묶어, 큰 곳부터 보여드려요
          </span>
        </h1>
        <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
          <Stat label="모집중인 IT 공고" value={jobs} />
          <Stat label="회사" value={cos} />
          <Stat label="신입 지원 가능" value={entry} accent />
        </dl>
      </div>
      <div className="relative pb-6">
        <LogoMarquee items={d.spotlight} onOpen={onOpen} />
      </div>
    </section>
  )
}

function Group({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="mt-14">
      <div className="mb-4">
        <h2 className="text-xl sm:text-2xl font-extrabold tracking-[-0.02em] text-(--color-text)">{title}</h2>
        {note && <p className="mt-1 max-w-[62ch] text-[13px] leading-relaxed text-(--color-muted)">{note}</p>}
      </div>
      <div className="grid gap-3 sm:gap-4 md:grid-cols-2 xl:grid-cols-3 items-start">{children}</div>
    </div>
  )
}

function Jump({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <a
      href={`#${to}`}
      onClick={(e) => {
        e.preventDefault()
        document.getElementById(to)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }}
      className="home-press shrink-0 px-3 py-1.5 rounded-full text-[13px] font-medium border border-(--color-border) bg-(--color-panel) text-(--color-muted) hover:text-(--color-text) hover:border-(--color-text) whitespace-nowrap"
    >
      {children}
    </a>
  )
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div>
      <dt className="text-[12.5px] text-(--color-muted)">{label}</dt>
      <dd className={'text-2xl sm:text-[28px] font-extrabold tabular-nums tracking-[-0.02em] ' + (accent ? 'text-(--color-accent)' : 'text-(--color-text)')}>
        {value.toLocaleString()}
      </dd>
    </div>
  )
}

function SizeTab({ on, onClick, label, n }: { on: boolean; onClick: () => void; label: string; n: number }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={on}
      onClick={onClick}
      className={
        'home-press shrink-0 px-3.5 py-2 rounded-full text-[13.5px] font-semibold border transition-colors whitespace-nowrap ' +
        (on
          ? 'bg-(--color-text) text-(--color-panel) border-(--color-text)'
          : 'bg-(--color-panel) border-(--color-border) text-(--color-muted) hover:text-(--color-text)')
      }
    >
      {label} <span className="tabular-nums text-xs font-medium opacity-60">{n.toLocaleString()}</span>
    </button>
  )
}
