import { useCallback, useEffect, useState } from 'react'
import { ErrorState, Loader } from '../../components/ui'
import { fetchHome, type ExpBucket, type HomeBoard, type HomeSort } from '../../features/home/api'
import { CompanyCard } from '../../features/home/components/CompanyCard'
import { CompanyPanel } from '../../features/home/components/CompanyPanel'
import { JobLine } from '../../features/home/components/JobLine'
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
 * `/` — 회사별로 묶은 메인 화면. 캐치 첫 화면처럼 회사 카드가 먼저, 그 아래 신입·경력 공고.
 *   규모(대기업·중견·중소) → 업종(금융·게임·제조…) 으로 좁히고, 카드를 누르면 오른쪽 패널에
 *   그 회사의 IT 공고. 고른 회사는 `?company=<슬러그>` 로 주소에 남는다(공유·새로고침).
 * 공고 하나하나를 거르는 화면은 `/jobs` 다.
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

  return (
    <div data-scroll className={'flex-1 min-h-0 overflow-auto jd-canvas ' + (open ? 'md:pr-[460px]' : '')}>
      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 py-6 sm:py-8">
        {/* 머리 */}
        <header className="mb-6">
          <h1 className="text-2xl sm:text-[28px] font-extrabold tracking-tight text-(--color-text)">기업별 IT 채용</h1>
          <p className="mt-1 text-sm text-(--color-muted)">
            지금 모집중인 국내 IT 공고 <b className="text-(--color-text) tabular-nums">{d.totals.jobs.toLocaleString()}</b>건을{' '}
            <b className="text-(--color-text) tabular-nums">{d.totals.companies.toLocaleString()}</b>개 회사로 묶었습니다 ·
            신입 가능 {d.totals.entry.toLocaleString()} · 경력 {d.totals.experienced.toLocaleString()}
          </p>
        </header>

        {/* 규모 → 업종 → 정렬 */}
        <div className="sticky top-0 z-10 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 bg-(--color-bg)/95 backdrop-blur border-b border-(--color-border-soft) mb-5">
          <div className="flex flex-wrap items-center gap-2">
            <div role="tablist" aria-label="기업 규모" className="flex rounded-lg border border-(--color-border) bg-(--color-panel) p-0.5">
              <SizeTab on={!size} onClick={() => pick(() => setSize(''))} label="전체" n={allSizes} />
              {d.facets.sizes.map((s) => (
                <SizeTab key={s.name} on={size === s.name} onClick={() => pick(() => setSize(s.name))} label={s.name} n={s.n} />
              ))}
            </div>
            <select
              value={sort}
              onChange={(e) => pick(() => setSort(e.target.value as HomeSort))}
              className="ml-auto text-sm rounded-lg border border-(--color-border) bg-(--color-panel) px-2.5 py-1.5"
              aria-label="정렬"
            >
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className="mt-2.5 flex gap-1.5 overflow-x-auto no-scrollbar" aria-label="업종">
            <IndChip on={!industry} onClick={() => pick(() => setIndustry(''))}>전체 업종</IndChip>
            {d.facets.industries.map((x) => (
              <IndChip key={x.name} on={industry === x.name} onClick={() => pick(() => setIndustry(industry === x.name ? '' : x.name))}>
                {x.name} <span className="tabular-nums opacity-70">{x.n}</span>
              </IndChip>
            ))}
          </div>
        </div>

        {/* 회사 카드 */}
        <section aria-label="회사">
          {d.companies.length === 0 ? (
            <p className="py-16 text-center text-sm text-(--color-faint)">이 조건에 맞는 회사가 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {d.companies.map((c) => (
                <CompanyCard key={c.slug} c={c} active={open === c.slug} onOpen={() => openCompany(c.slug)} />
              ))}
            </div>
          )}
          {d.companies.length < d.totals.companies && (
            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE * 2)}
                className="px-5 py-2 rounded-full border border-(--color-border) bg-(--color-panel) text-sm hover:border-(--color-text)"
              >
                회사 더 보기 <span className="text-(--color-faint) tabular-nums">{d.companies.length} / {d.totals.companies.toLocaleString()}</span>
              </button>
            </div>
          )}
        </section>

        {/* 신입 · 경력 */}
        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <section className="rounded-xl border border-(--color-border) bg-(--color-panel) p-5">
            <SectionHead title={<><span className="text-(--color-accent)">신입</span> 가능한 IT 공고</>} n={d.totals.entry} />
            <div className="flex flex-col">
              {d.entry.map((j) => <JobLine key={j.site + j.pid} j={j} />)}
              {d.entry.length === 0 && <Empty />}
            </div>
          </section>

          <section className="rounded-xl border border-(--color-border) bg-(--color-panel) p-5">
            <SectionHead title={<><span className="text-(--color-accent)">경력</span> IT 공고</>} n={d.totals.experienced} />
            <div role="tablist" aria-label="경력 구간" className="flex gap-1.5 mb-2">
              {d.experienced.map((x) => (
                <button
                  key={x.bucket}
                  type="button"
                  role="tab"
                  aria-selected={exp?.bucket === x.bucket}
                  onClick={() => setBucket(x.bucket)}
                  className={
                    'px-3 py-1.5 rounded-full text-xs font-medium border transition ' +
                    (exp?.bucket === x.bucket
                      ? 'bg-(--color-text) text-(--color-panel) border-(--color-text)'
                      : 'border-(--color-border) text-(--color-muted) hover:border-(--color-text)')
                  }
                >
                  {x.bucket === '8년+' ? '8년 이상' : x.bucket} <span className="tabular-nums opacity-70">{x.n.toLocaleString()}</span>
                </button>
              ))}
            </div>
            <div className="flex flex-col">
              {exp?.jobs.map((j) => <JobLine key={j.site + j.pid} j={j} />)}
              {exp && exp.jobs.length === 0 && <Empty />}
            </div>
          </section>
        </div>

        <p className="mt-8 text-center text-xs text-(--color-faint)">
          공고 하나하나를 기술스택·지역으로 거르려면{' '}
          <a href={paths.jobs()} onClick={onLinkClick(paths.jobs())} className="text-(--color-accent) hover:underline">
            잡 리스트
          </a>
          . 규모는 공고·명단으로, 업종은 회사 이름으로 가른 추정입니다.
        </p>
      </div>

      {open && <CompanyPanel key={open} slug={open} onClose={closePanel} />}
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
        'px-3 py-1.5 rounded-md text-sm font-medium transition whitespace-nowrap ' +
        (on ? 'bg-(--color-text) text-(--color-panel)' : 'text-(--color-muted) hover:text-(--color-text)')
      }
    >
      {label} <span className="tabular-nums text-xs opacity-70">{n.toLocaleString()}</span>
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
        'shrink-0 px-3 py-1 rounded-full text-[13px] border transition whitespace-nowrap ' +
        (on
          ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent)'
          : 'bg-(--color-panel) border-(--color-border) text-(--color-muted) hover:border-(--color-accent)')
      }
    >
      {children}
    </button>
  )
}

function SectionHead({ title, n }: { title: React.ReactNode; n: number }) {
  return (
    <div className="flex items-baseline justify-between mb-3">
      <h2 className="text-lg font-bold text-(--color-text)">{title}</h2>
      <span className="text-xs text-(--color-faint) tabular-nums">{n.toLocaleString()}건</span>
    </div>
  )
}

function Empty() {
  return <p className="py-8 text-center text-sm text-(--color-faint)">이 조건에 맞는 공고가 없습니다.</p>
}
