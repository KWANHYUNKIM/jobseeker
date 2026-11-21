import { useMemo, useState } from 'react'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import { EmptyState, ErrorState, Loader } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { SiteFooter } from '../../../components/SiteFooter'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths, TAB_SEO } from '../../../utils/urls'
import { useContests } from '../hooks/useContests'
import {
  ALL_FILTER,
  countBy,
  ddayLabel,
  dupsByRep,
  filterContests,
  periodLabel,
  statusOf,
  todayKst,
  type Contest,
  type ContestFilter,
} from '../utils/contests'

// IT·디자인 공모전 — 개발·AI·데이터·해커톤·앱·게임, 컴퓨터로 만드는 디자인(UI·웹툰·포스터)과 영상.
//
// 요약과 링크만 싣는다(요강 본문·포스터·연락처 없음). 그래서 상세 화면이 없고, 줄마다 '원문에서
// 보기 ↗' 로 나간다. 남의 목록을 다시 보여 주는 화면이라 색인하지 않는다.
// 데이터: public/contests.json (catch_capture/crawlers/crawl_contests.py 가 누적한다).

const NOINDEX = 'noindex, follow'

export function ContestsView() {
  const { data, loading, error } = useContests()
  const [f, setF] = useState<ContestFilter>(ALL_FILTER)
  const today = todayKst()

  useSeo({ title: TAB_SEO.contests.title, description: TAB_SEO.contests.desc, robots: NOINDEX, canonical: absUrl(paths.contests()) })

  const rows = useMemo(() => data?.contests ?? [], [data])
  const shown = useMemo(() => filterContests(rows, f, today), [rows, f, today])
  const dups = useMemo(() => dupsByRep(rows), [rows])
  const catCount = useMemo(() => countBy(rows, 'category', f, today), [rows, f, today])
  const srcCount = useMemo(() => countBy(rows, 'source', f, today), [rows, f, today])
  const openN = useMemo(
    () => filterContests(rows, { ...ALL_FILTER, status: 'open' }, today).length,
    [rows, today],
  )
  const paged = usePaged(shown, PAGE_SIZE)

  if (loading) return <Loader label="공모전 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="contests.json 로드 실패"
        detail={error}
        hint={
          <>
            생성: <code className="text-(--color-text)">python -m crawlers.crawl_contests --force</code>
          </>
        }
      />
    )
  if (!data) return null

  const set = (patch: Partial<ContestFilter>) => setF((x) => ({ ...x, ...patch }))
  const sourceNames = Object.values(data.sources).join('·')

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[40px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">IT·디자인 공모전</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          개발·AI·데이터, 해커톤, 앱·게임, 그리고 컴퓨터로 만드는 디자인·영상 공모전{' '}
          <b className="font-bold text-(--color-accent)">{openN.toLocaleString()}건</b>이 접수 중이에요. 요강과 접수는 원문에서 해요.
        </p>

        <section data-contests-top className="mt-[29px] scroll-mt-4">
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="모집 상태" className="inline-flex h-9 rounded-[18px] border border-[#d8d8d8] p-[3px]">
              {(['all', 'open', 'closed'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={f.status === s}
                  onClick={() => set({ status: s })}
                  className={
                    'px-[14px] rounded-[15px] text-sm font-medium tracking-[-0.3px] ' +
                    (f.status === s ? 'bg-[#272727] text-white' : 'text-[#474747] hover:text-[#272727]')
                  }
                >
                  {s === 'all' ? '전체' : s === 'open' ? '접수중' : '마감'}
                </button>
              ))}
            </div>
            <div role="group" aria-label="출처" className="ml-auto flex flex-wrap gap-2">
              <Chip small on={!f.source} onClick={() => set({ source: null })} label="모든 출처" />
              {Object.entries(data.sources).map(([k, name]) => (
                <Chip key={k} small on={f.source === k} onClick={() => set({ source: f.source === k ? null : k })} label={name} n={srcCount.get(k) ?? 0} />
              ))}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Chip on={!f.category} onClick={() => set({ category: null })} label="전체" n={[...catCount.values()].reduce((a, b) => a + b, 0)} />
            {data.categories.map((cat) => (
              <Chip key={cat} on={f.category === cat} onClick={() => set({ category: cat })} label={cat} n={catCount.get(cat) ?? 0} />
            ))}
          </div>

          {shown.length === 0 ? (
            <EmptyState title="조건에 맞는 공모전이 없습니다" hint="다른 분류나 출처를 골라 보세요." />
          ) : (
            <ul className="mt-[23px] border-t border-[#e2e2e2]">
              {paged.slice.map((c) => (
                <ContestRow key={c.id} c={c} today={today} sources={data.sources} also={f.source ? [] : (dups.get(c.id) ?? [])} />
              ))}
            </ul>
          )}
          <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} scrollTo="[data-contests-top]" />
        </section>

        <p className="text-xs leading-5 text-[#999]">
          {sourceNames}에서 컴퓨터로 하는 공모전만 골라 제목·주최·상금·접수 기간·참가 대상과 원문 링크만 옮겼어요. 마감일이 지나거나 원문이
          내려가면 마감으로 옮기고 목록에는 남겨 둬요. 여러 곳에 같이 올라온 공모전은 한 줄로 묶었어요. 수집{' '}
          {data.updated_at.slice(0, 16).replace('T', ' ')}
        </p>
      </div>
      <SiteFooter updated={data.updated_at} sources={sourceNames} />
    </div>
  )
}

function Chip({ on, onClick, label, n, small }: { on: boolean; onClick: () => void; label: string; n?: number; small?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={
        (small ? 'h-8 px-[12px] rounded-[16px] text-[13px] ' : 'h-9 px-[15px] rounded-[18px] text-sm ') +
        'border font-medium tracking-[-0.3px] ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {label} {n !== undefined && <span className={'tabular-nums ' + (on ? 'text-white/80' : 'text-[#999]')}>{n}</span>}
    </button>
  )
}

function ContestRow({ c, today, sources, also }: { c: Contest; today: string; sources: Record<string, string>; also: Contest[] }) {
  const closed = statusOf(c, today) === 'closed'
  const dday = closed ? '' : ddayLabel(c.period_end, today)
  const period = periodLabel(c, today)
  return (
    <li className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4 border-b border-[#e2e2e2] px-[14px] py-[18px]">
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap gap-1">
          <span className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] text-[#5b4fd6]">{c.category}</span>
          <span className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]">{sources[c.source] ?? c.source}</span>
          {closed && (
            <span className="rounded bg-[#fdecec] px-[7px] text-[13px] font-bold leading-[22px] text-[#b42318]" title={c.closed_reason ?? '접수 마감'}>
              마감
            </span>
          )}
        </div>
        <div className={`mt-2 truncate text-[17px] font-medium leading-[25px] tracking-[-0.16px] ${closed ? 'text-[#999]' : 'text-[#272727]'}`}>{c.title}</div>
        <div className="mt-1 flex flex-wrap gap-x-[14px] text-[13px] leading-[19px] text-[#666]">
          {c.host && <span>{c.host}</span>}
          {period && <span>접수 {period}</span>}
          {c.target && <span>{c.target}</span>}
          {also.length > 0 && (
            <span>
              같은 공모전:{' '}
              {also.map((d, i) => (
                <span key={d.id}>
                  {i > 0 && ' · '}
                  <a href={d.url} target="_blank" rel="noopener noreferrer nofollow" className="underline-offset-2 hover:underline">
                    {sources[d.source] ?? d.source}
                  </a>
                </span>
              ))}
            </span>
          )}
        </div>
      </div>
      <div className="md:w-[170px] md:shrink-0 md:text-right">
        {dday && <div className="text-base font-bold leading-6 text-(--color-accent) tabular-nums">{dday}</div>}
        <div className={'text-[13px] leading-5 ' + (c.prize ? 'text-[#272727]' : 'text-[#999]')}>{c.prize || '상금 표기 없음'}</div>
      </div>
      <a
        href={c.url}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className="md:w-[120px] md:shrink-0 text-sm font-medium text-[#272727] underline-offset-2 hover:underline md:text-right"
      >
        원문에서 보기 ↗
      </a>
    </li>
  )
}
