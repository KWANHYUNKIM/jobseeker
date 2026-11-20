import { useMemo, useState } from 'react'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import { EmptyState, ErrorState, Loader } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { SiteFooter } from '../../../components/SiteFooter'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths, TAB_SEO } from '../../../utils/urls'
import { useAlba } from '../hooks/useAlba'
import { ALL_FILTER, countBy, dayLabel, filterPosts, payLabel, type AlbaFilter, type AlbaPost } from '../utils/alba'

// 당근알바 IT 공고 — 동네 알바 중 웹·앱 제작, 코딩 강사, 영상 편집, 엑셀 자동화 같은 IT 일감만.
//
// 약관상 요약과 링크만 싣는다(본문·상호·연락처 없음). 그래서 상세 화면이 없고, 줄마다
// '원문에서 보기 ↗' 로 당근알바에 나간다. 남의 목록을 다시 보여 주는 화면이라 색인하지 않는다.
// 데이터: public/alba.json (catch_capture/crawlers/crawl_daangn_alba.py 가 누적한다).

const NOINDEX = 'noindex, follow'

export function AlbaView() {
  const { data, loading, error } = useAlba()
  const [f, setF] = useState<AlbaFilter>(ALL_FILTER)

  useSeo({ title: TAB_SEO.alba.title, description: TAB_SEO.alba.desc, robots: NOINDEX, canonical: absUrl(paths.alba()) })

  const posts = useMemo(() => data?.posts ?? [], [data])
  const shown = useMemo(() => filterPosts(posts, f), [posts, f])
  const catCount = useMemo(() => countBy(posts, 'category', f), [posts, f])
  const sidoCount = useMemo(() => countBy(posts, 'sido', f), [posts, f])
  const openN = useMemo(() => posts.filter((p) => p.status === 'open').length, [posts])
  const paged = usePaged(shown, PAGE_SIZE)

  if (loading) return <Loader label="당근알바 IT 공고 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="alba.json 로드 실패"
        detail={error}
        hint={
          <>
            생성: <code className="text-(--color-text)">python -m crawlers.crawl_daangn_alba</code>
          </>
        }
      />
    )
  if (!data) return null

  const sidos = [...sidoCount.entries()].sort((a, b) => b[1] - a[1])
  const set = (patch: Partial<AlbaFilter>) => setF((x) => ({ ...x, ...patch }))

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[40px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">당근알바 IT 공고</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          동네 알바 중 웹·앱 제작, 코딩 강사, 영상 편집, 엑셀 자동화 같은 IT 일감{' '}
          <b className="font-bold text-(--color-accent)">{openN.toLocaleString()}건</b>을 모았어요. 자세한 내용과 지원은 원문에서 해요.
        </p>

        <section data-alba-top className="mt-[29px] scroll-mt-4">
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="모집 상태" className="inline-flex h-9 rounded-[18px] border border-[#d8d8d8] p-[3px]">
              {(['open', 'closed'] as const).map((s) => (
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
                  {s === 'open' ? '모집중' : '마감'}
                </button>
              ))}
            </div>
            <label className="ml-auto relative inline-flex items-center h-9 rounded-[18px] border border-(--color-accent) bg-white">
              <select
                aria-label="지역"
                value={f.sido ?? ''}
                onChange={(e) => set({ sido: e.target.value || null })}
                className="appearance-none h-full bg-transparent pl-[17px] pr-[34px] text-sm font-medium tracking-[-0.3px] text-(--color-accent) outline-none cursor-pointer"
              >
                <option value="">전국</option>
                {sidos.map(([k, n]) => (
                  <option key={k} value={k}>
                    {k} ({n})
                  </option>
                ))}
              </select>
              <svg className="pointer-events-none absolute right-[17px]" width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#f45757" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                <path d="M1.5 2.5 5 6l3.5-3.5" />
              </svg>
            </label>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Chip on={!f.category} onClick={() => set({ category: null })} label="전체" n={[...catCount.values()].reduce((a, b) => a + b, 0)} />
            {data.categories.map((c) => (
              <Chip key={c} on={f.category === c} onClick={() => set({ category: c })} label={c} n={catCount.get(c) ?? 0} />
            ))}
          </div>

          {shown.length === 0 ? (
            <EmptyState title="조건에 맞는 공고가 없습니다" hint="다른 분류나 지역을 골라 보세요." />
          ) : (
            <ul className="mt-[23px] border-t border-[#e2e2e2]">
              {paged.slice.map((p) => (
                <AlbaRow key={p.id} p={p} />
              ))}
            </ul>
          )}
          <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} scrollTo="[data-alba-top]" />
        </section>

        <p className="text-xs leading-5 text-[#999]">
          당근알바 사이트맵에서 IT 공고로 보이는 것만 골라 제목·급여·지역(시/군/구까지)·근무 시간과 원문 링크만 옮겼어요. 원본이 마감하거나 내리면
          다음 수집 때 마감으로 옮겨요. 수집 {data.updated_at.slice(0, 16).replace('T', ' ')}
        </p>
      </div>
      <SiteFooter updated={data.updated_at} sources="당근알바(jobs.daangn.com)" />
    </div>
  )
}

function Chip({ on, onClick, label, n }: { on: boolean; onClick: () => void; label: string; n: number }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={
        'h-9 px-[15px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {label} <span className={'tabular-nums ' + (on ? 'text-white/80' : 'text-[#999]')}>{n}</span>
    </button>
  )
}

function AlbaRow({ p }: { p: AlbaPost }) {
  const where = [p.sido, p.sigungu].filter(Boolean).join(' ')
  return (
    <li className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4 border-b border-[#e2e2e2] px-[14px] py-[18px]">
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap gap-1">
          <span className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] text-[#5b4fd6]">{p.category}</span>
          {p.employment && <span className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]">{p.employment}</span>}
          {p.status === 'closed' && (
            <span className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#999]" title={p.closed_reason}>
              마감 {dayLabel(p.closed_at)}
            </span>
          )}
        </div>
        <div className="mt-2 truncate text-[17px] font-medium leading-[25px] tracking-[-0.16px] text-[#272727]">{p.title}</div>
        <div className="mt-1 flex flex-wrap gap-x-[14px] text-[13px] leading-[19px] text-[#666]">
          {where && <span>{where}</span>}
          {p.hours && <span>{p.hours}</span>}
          {p.posted_at ? <span>{dayLabel(p.posted_at)} 등록</span> : <span title="등록일을 못 받아 처음 본 날로 대신했어요">{dayLabel(p.first_seen_at)} 처음 봄</span>}
        </div>
      </div>
      <div className="md:w-[170px] md:shrink-0 md:text-right">
        <div className={'text-base font-bold leading-6 ' + (p.pay?.amount ? 'text-(--color-accent)' : 'text-[#999] font-medium')}>{payLabel(p.pay)}</div>
      </div>
      <a
        href={p.url}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className="md:w-[120px] md:shrink-0 text-sm font-medium text-[#272727] underline-offset-2 hover:underline md:text-right"
      >
        원문에서 보기 ↗
      </a>
    </li>
  )
}
