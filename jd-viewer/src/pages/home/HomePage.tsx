import { useCallback, useEffect, useState } from 'react'
import { ErrorState, Loader } from '../../components/ui'
import { fetchHome, type ExpBucket, type HomeBoard, type HomeSort } from '../../features/home/api'
import { CompanyCard } from '../../features/home/components/CompanyCard'
import { CompanyPanel } from '../../features/home/components/CompanyPanel'
import { JobLine } from '../../features/home/components/JobLine'
import { LogoMarquee } from '../../features/home/components/LogoMarquee'
import { useCountUp } from '../../features/home/hooks/useCountUp'
import { onLinkClick, useRoute, useSetQuery } from '../../utils/navigation'
import { absUrl, useSeo } from '../../utils/seo'
import { paths, TAB_SEO } from '../../utils/urls'

const PAGE = 24
const SORTS: { key: HomeSort; label: string }[] = [
  { key: 'popular', label: '주목순' },
  { key: 'new', label: '최신 공고순' },
  { key: 'count', label: '공고 많은 순' },
]

/**
 * `/` — 회사별로 묶은 메인. 캐치 첫 화면처럼 회사가 먼저, 그 아래 신입·경력 공고.
 *   첫 화면: 지금 뽑는 회사 로고가 흐르는 띠와 숫자(한 번 올라간다) — 이 화면의 유일한 '연출'.
 *   그다음: 규모 → 업종으로 좁히는 막대(위에 붙는다), 회사 카드, 신입·경력.
 *   카드를 누르면 오른쪽 패널(휴대폰은 아래 시트)에 그 회사의 IT 공고. 고른 회사는 `?company=`.
 * 공고 하나하나를 거르는 화면은 `/jobs`.
 */
export function HomePage() {
  const route = useRoute()
  const setQuery = useSetQuery()
  const [size, setSize] = useState('')
  const [industry, setIndustry] = useState('')
  const [sort, setSort] = useState<HomeSort>('popular')
  const [limit, setLimit] = useState(PAGE)
  const [bucket, setBucket] = useState<ExpBucket>('3-4년')
  const [d, setD] = useState<HomeBoard | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const open = route.query.get('company')

  useSeo({ title: TAB_SEO.home.title, description: TAB_SEO.home.desc, canonical: absUrl('/') })

  useEffect(() => {
    const ctl = new AbortController()
    fetchHome({ size, industry, sort, limit }, { signal: ctl.signal })
      .then((x) => {
        setD(x)
        setErr(null)
      })
      .catch((e: Error) => e.name !== 'AbortError' && setErr(e.message))
    return () => ctl.abort()
  }, [size, industry, sort, limit])

  // 칸을 바꾸면 '더 보기' 로 늘린 개수는 처음으로
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

  const exp = d.experienced.find((x) => x.bucket === bucket) ?? d.experienced[0]
  const allSizes = d.facets.sizes.reduce((a, x) => a + x.n, 0)
  // 칸이 바뀔 때마다 카드 묶음을 새로 그려 차례로 자리 잡게 한다('더 보기'는 제외 — 아래에 이어 붙는다)
  const gridKey = `${size}|${industry}|${sort}`

  return (
    <div data-scroll className={'flex-1 min-h-0 overflow-auto jd-canvas ' + (open ? 'md:pr-[460px]' : '')}>
      <Hero d={d} onOpen={openCompany} />

      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 pb-12">
        {/* 규모 → 업종 → 정렬. 스크롤해도 위에 붙어 있다 */}
        <div className="sticky top-0 z-20 -mx-4 sm:-mx-6 px-4 sm:px-6 pt-3 pb-2.5 bg-(--color-bg) shadow-[0_8px_16px_-12px_rgba(0,0,0,0.18)] border-b border-(--color-border-soft)">
          <div className="flex items-center gap-2">
            <div role="tablist" aria-label="기업 규모" className="flex min-w-0 overflow-x-auto no-scrollbar rounded-xl border border-(--color-border) bg-(--color-panel) p-1">
              <SizeTab on={!size} onClick={() => pick(() => setSize(''))} label="전체" n={allSizes} />
              {d.facets.sizes.map((s) => (
                <SizeTab key={s.name} on={size === s.name} onClick={() => pick(() => setSize(s.name))} label={s.name} n={s.n} />
              ))}
            </div>
            <select
              value={sort}
              onChange={(e) => pick(() => setSort(e.target.value as HomeSort))}
              className="ml-auto shrink-0 text-sm rounded-xl border border-(--color-border) bg-(--color-panel) px-2.5 py-2"
              aria-label="정렬"
            >
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className="mt-2 flex gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1" aria-label="업종">
            <IndChip on={!industry} onClick={() => pick(() => setIndustry(''))}>모든 업종</IndChip>
            {d.facets.industries.map((x) => (
              <IndChip key={x.name} on={industry === x.name} onClick={() => pick(() => setIndustry(industry === x.name ? '' : x.name))}>
                {x.name} <span className="tabular-nums opacity-60">{x.n}</span>
              </IndChip>
            ))}
          </div>
        </div>

        {/* 회사 카드 */}
        <section aria-label="회사" className="mt-5">
          <div className="flex items-baseline justify-between gap-3 mb-3">
            <h2 className="text-lg sm:text-xl font-bold text-(--color-text)">
              {size || '모든 규모'}
              {industry ? ` ${industry}` : ''} 회사{' '}
              <span className="tabular-nums text-(--color-accent)">{d.totals.companies.toLocaleString()}</span>
            </h2>
            <span className="hidden sm:inline text-xs text-(--color-faint)">카드를 누르면 그 회사 공고가 열려요</span>
          </div>
          {d.companies.length === 0 ? (
            <p className="py-16 text-center text-sm text-(--color-faint)">
              이 조건에 맞는 회사가 없습니다. 업종이나 규모를 하나 풀어 보세요.
            </p>
          ) : (
            <div key={gridKey} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5 sm:gap-3">
              {d.companies.map((c, i) => (
                <CompanyCard key={c.slug} c={c} i={i} active={open === c.slug} onOpen={() => openCompany(c.slug)} />
              ))}
            </div>
          )}
          {d.companies.length < d.totals.companies && (
            <div className="mt-5 text-center">
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE * 2)}
                className="home-press px-6 py-2.5 rounded-full border border-(--color-border) bg-(--color-panel) text-sm font-medium hover:border-(--color-text)"
              >
                회사 더 보기
                <span className="ml-2 text-(--color-faint) tabular-nums">
                  {d.companies.length} / {d.totals.companies.toLocaleString()}
                </span>
              </button>
            </div>
          )}
        </section>

        {/* 신입 · 경력 */}
        <div className="mt-12 grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-(--color-border) bg-(--color-panel) p-4 sm:p-5">
            <SectionHead title="신입도 지원할 수 있는 공고" n={d.totals.entry} />
            <div className="flex flex-col -mx-1">
              {d.entry.map((j) => <JobLine key={j.site + j.pid} j={j} />)}
              {d.entry.length === 0 && <Empty />}
            </div>
          </section>

          <section className="rounded-2xl border border-(--color-border) bg-(--color-panel) p-4 sm:p-5">
            <SectionHead title="경력 공고" n={d.totals.experienced} />
            <div role="tablist" aria-label="경력 구간" className="flex gap-1.5 mb-2 overflow-x-auto no-scrollbar">
              {d.experienced.map((x) => (
                <button
                  key={x.bucket}
                  type="button"
                  role="tab"
                  aria-selected={exp?.bucket === x.bucket}
                  onClick={() => setBucket(x.bucket)}
                  className={
                    'shrink-0 px-3 py-1.5 rounded-full text-[13px] font-medium border transition-colors ' +
                    (exp?.bucket === x.bucket
                      ? 'bg-(--color-text) text-(--color-panel) border-(--color-text)'
                      : 'border-(--color-border) text-(--color-muted) hover:border-(--color-text)')
                  }
                >
                  {x.bucket === '8년+' ? '8년 이상' : x.bucket} <span className="tabular-nums opacity-60">{x.n.toLocaleString()}</span>
                </button>
              ))}
            </div>
            <div key={exp?.bucket} className="flex flex-col -mx-1 jd-fade-in">
              {exp?.jobs.map((j) => <JobLine key={j.site + j.pid} j={j} />)}
              {exp && exp.jobs.length === 0 && <Empty />}
            </div>
          </section>
        </div>

        <p className="mt-10 text-center text-xs leading-relaxed text-(--color-faint)">
          공고 하나하나를 기술스택·지역으로 거르려면{' '}
          <a href={paths.jobs()} onClick={onLinkClick(paths.jobs())} className="text-(--color-accent) hover:underline">
            잡 리스트
          </a>
          에서 볼 수 있어요.
          <br className="sm:hidden" /> 규모는 공고와 명단으로, 업종은 회사 이름으로 가른 추정입니다.
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
  const entry = useCountUp(d.totals.entry)
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
        'shrink-0 px-3 py-1.5 rounded-lg text-[13.5px] font-semibold transition-colors whitespace-nowrap ' +
        (on ? 'bg-(--color-text) text-(--color-panel)' : 'text-(--color-muted) hover:text-(--color-text)')
      }
    >
      {label} <span className="tabular-nums text-xs font-medium opacity-60">{n.toLocaleString()}</span>
    </button>
  )
}

function IndChip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={
        'home-press shrink-0 px-3 py-1.5 rounded-full text-[13px] border transition-colors whitespace-nowrap ' +
        (on
          ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent) font-semibold'
          : 'bg-(--color-panel) border-(--color-border) text-(--color-muted) hover:border-(--color-accent)')
      }
    >
      {children}
    </button>
  )
}

function SectionHead({ title, n }: { title: string; n: number }) {
  return (
    <div className="flex items-baseline justify-between mb-3 px-1">
      <h2 className="text-lg font-bold text-(--color-text)">{title}</h2>
      <span className="text-xs text-(--color-faint) tabular-nums">{n.toLocaleString()}건</span>
    </div>
  )
}

function Empty() {
  return <p className="py-8 text-center text-sm text-(--color-faint)">이 조건에 맞는 공고가 없습니다. 위에서 규모나 업종을 풀어 보세요.</p>
}
