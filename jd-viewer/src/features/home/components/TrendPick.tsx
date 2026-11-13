import { useMemo, useState } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import type { HomeBoard, HomeCompany, HomeJob } from '../api'
import { ddayLabel, shortTitle } from '../utils'

/**
 * '오늘의 트렌드 Pick' 띠(캐치형 y=1630~2385) — 왼쪽은 이번 주 공고가 가장 많이 늘어난 회사,
 * 오른쪽 위는 직무별 인기 공고(탭), 아래 둘은 업종별 공고 1위 회사.
 */
export function TrendPick({ d, onOpen }: { d: HomeBoard; onOpen: (slug: string) => void }) {
  const pool = useMemo(() => {
    const seen = new Set<string>()
    const out: HomeJob[] = []
    for (const s of d.sections)
      for (const j of s.jobs) {
        const k = j.site + j.pid
        if (!seen.has(k)) {
          seen.add(k)
          out.push(j)
        }
      }
    return out
  }, [d])
  const hot = [...d.companies].sort((a, b) => b.new_7d - a.new_7d || b.active - a.active)[0]
  const tops = topByIndustry(d.companies)

  return (
    <div className="flex flex-col lg:flex-row gap-7">
      {hot && (
        <HotCompany
          c={hot}
          job={pool.find((j) => j.company_slug === hot.slug)}
          family={d.companies.filter((x) => x.name.startsWith(hot.name)).length}
          onOpen={onOpen}
        />
      )}
      <div className="flex-1 min-w-0 flex flex-col gap-7">
        <RoleBoard cos={d.companies} onOpen={onOpen} />
        <div className="grid sm:grid-cols-2 gap-7">
          {tops.map((t, k) => (
            <IndustryTop key={t.industry} industry={t.industry} c={t.c} second={k === 1} onOpen={onOpen} />
          ))}
        </div>
      </div>
    </div>
  )
}

/** 업종마다 공고가 가장 많은 회사 — 맨 앞 두 업종(주목순 회사 목록에서 먼저 나오는 업종). */
function topByIndustry(cos: HomeCompany[]): { industry: string; c: HomeCompany }[] {
  const best = new Map<string, HomeCompany>()
  for (const c of cos) {
    if (c.industry === '기타') continue
    const cur = best.get(c.industry)
    if (!cur || c.active > cur.active) best.set(c.industry, c)
  }
  return [...best.entries()].slice(0, 2).map(([industry, c]) => ({ industry, c }))
}

const CARD = 'rounded-[22px] border border-[#485071] shadow-[2px_4px_15px_rgba(0,0,0,0.07)]'

function HotCompany({ c, job, family, onOpen }: { c: HomeCompany; job?: HomeJob; family: number; onOpen: (slug: string) => void }) {
  const meta = [job?.region, c.size, [c.industry, ...(job?.stacks ?? c.roles)].filter((x) => x && x !== '기타').slice(0, 5).join(', ')]
    .filter(Boolean)
    .join(' | ')
  const title = shortTitle(c.titles[0]?.title ?? '')
  return (
    <section className={`${CARD} shrink-0 lg:w-[400px] lg:h-[562px] bg-[#f3f6f8] px-[31px] pt-[30px] pb-[29px]`}>
      <h3 className="text-[24px] leading-[35px] tracking-[-0.24px] text-[#1a1a1a]">
        <span className="font-bold text-(--color-accent)">{c.name}</span>에
        <br />
        지원자들이 몰리고 있어요.
      </h3>
      <div className="relative mt-[29px] rounded-[20px] bg-white px-[30px] pt-[20px] pb-[22px]">
        <div className="absolute right-[24px] top-[18px] flex items-center gap-2">
          <span className="text-sm leading-[21px] text-[#666]">{ddayLabel(c.soonest_dday)}</span>
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="#b7b7b7" strokeWidth="1.6" aria-hidden>
            <path d="M11 18s-6.5-4-6.5-8.5A3.5 3.5 0 0 1 11 7.2a3.5 3.5 0 0 1 6.5 2.3C17.5 14 11 18 11 18Z" />
          </svg>
        </div>
        <div className="flex justify-center pt-[24px]">
          <CompanyMark name={c.name} logo={c.logo} size={52} />
        </div>
        <p className="mt-[0px] text-lg font-bold leading-[26px] tracking-[-0.18px] text-[#272727]">{c.name}</p>
        <p className="mt-[11px] text-base font-medium leading-6 tracking-[-0.16px] text-[#272727] truncate">{title}</p>
        <p className="mt-px text-[13px] leading-[19px] tracking-[-0.13px] text-[#666] truncate">{meta}</p>
        <button
          type="button"
          onClick={() => onOpen(c.slug)}
          className="mt-[15px] w-full h-[38px] rounded bg-[#272727] text-sm text-white hover:bg-black"
        >
          공고 보러가기
        </button>
        <div className="mt-[35px] flex gap-1">
          <span className="rounded bg-[#f2f2f2] px-2 text-xs leading-[26px] tracking-[-0.12px] text-[#272727]">#이번 주 +{c.new_7d}</span>
          <span className="rounded bg-[#f2f2f2] px-2 text-xs leading-[26px] tracking-[-0.12px] text-[#272727]">#공고 {c.active}건</span>
        </div>
        <p className="mt-3 text-sm leading-5 tracking-[-0.14px] text-[#666] line-clamp-2">
          {family > 1 ? `${c.name} 계열 ${family}개 회사가 동시에 채용 중이에요.` : `이번 주에만 새 공고가 ${c.new_7d}건 올라왔어요.`}{' '}
          {c.roles.length > 0 ? `${c.roles.slice(0, 3).join('·')} 직무가 가장 많아요.` : `지금 ${c.active}건을 모집 중이에요.`}
        </p>
        <div className="mt-[18px] text-right">
          <button type="button" onClick={() => onOpen(c.slug)} className="text-[13px] font-medium text-[#474747] hover:text-[#272727]">
            더보기 ›
          </button>
        </div>
      </div>
    </section>
  )
}

// 직무 탭은 회사의 직무 묶음(roles)으로, 규모 탭은 회사 규모로 가른다 — 주목순 회사 목록 그대로.
const TABS: { key: string; label: string; note: string; test: (c: HomeCompany) => boolean }[] = [
  { key: 'be', label: '서버·백엔드', note: '추천직무', test: (c) => c.roles.includes('백엔드') },
  { key: 'ai', label: 'AI·ML', note: '추천직무', test: (c) => c.roles.includes('AI/ML') },
  { key: 'sec', label: '보안', note: '추천직무', test: (c) => c.roles.includes('보안') },
  { key: 'big', label: '대기업', note: '추천규모', test: (c) => c.size === '대기업' },
]
const PER = 6

function RoleBoard({ cos, onOpen }: { cos: HomeCompany[]; onOpen: (slug: string) => void }) {
  const [tab, setTab] = useState(TABS[0].key)
  const [page, setPage] = useState(0)
  const t = TABS.find((x) => x.key === tab) ?? TABS[0]
  const list = cos.filter((c) => c.titles.length > 0 && t.test(c))
  const pages = Math.max(1, Math.ceil(list.length / PER))
  const shown = list.slice((page % pages) * PER, (page % pages) * PER + PER)
  return (
    <section className={`${CARD} relative bg-white px-[29px] pt-[23px] pb-[17px] lg:h-[402px]`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="mt-1 text-lg font-medium leading-[26px] tracking-[-0.18px] text-[#272727]">실시간 직무별 인기공고</h3>
        <a
          href={paths.jobs()}
          onClick={onLinkClick(paths.jobs())}
          className="shrink-0 h-[30px] px-[14px] rounded bg-(--color-accent) text-[13px] font-medium leading-[30px] text-white hover:bg-(--color-accent-deep)"
        >
          + 관심 기술 설정하기
        </a>
      </div>
      <div role="tablist" className="mt-4 flex gap-2 overflow-x-auto no-scrollbar">
        {TABS.map((x) => (
          <button
            key={x.key}
            type="button"
            role="tab"
            aria-selected={x.key === tab}
            onClick={() => {
              setTab(x.key)
              setPage(0)
            }}
            className={
              'shrink-0 h-[30px] px-[15px] rounded-[15px] border text-[13px] leading-[19px] tracking-[-0.3px] ' +
              (x.key === tab ? 'border-(--color-accent) text-(--color-accent)' : 'border-[#d8d8d8] text-[#272727]')
            }
          >
            {x.label}
            <span className="ml-[5px] text-xs text-[#999]">{x.note}</span>
          </button>
        ))}
      </div>
      <div className="mt-[18px] grid grid-cols-2 md:grid-cols-3 gap-2">
        {shown.map((c) => (
          <button
            key={c.slug}
            type="button"
            onClick={() => onOpen(c.slug)}
            className="home-press relative text-left h-[130px] rounded-2xl border border-[#e2e8ec] px-[17px] pt-[15px] hover:border-[#272727]"
          >
            <span className="absolute right-[17px] top-3 text-[13px] text-[#999] tabular-nums">{ddayLabel(c.soonest_dday)}</span>
            <CompanyMark name={c.name} logo={c.logo} size={32} />
            <span className="mt-[6px] block text-base font-medium leading-6 tracking-[-0.16px] text-[#272727] truncate">{c.name}</span>
            <span className="mt-px line-clamp-2 text-[13px] leading-[19px] tracking-[-0.13px] text-[#474747]">{shortTitle(c.titles[0].title)}</span>
          </button>
        ))}
        {shown.length === 0 && <p className="col-span-full py-10 text-center text-sm text-[#999]">지금 이 직무의 인기 공고가 없어요.</p>}
      </div>
      {pages > 1 && (
        <button
          type="button"
          onClick={() => setPage((p) => p + 1)}
          aria-label="다음 공고"
          className="absolute -right-4 top-[237px] w-8 h-8 rounded-full border border-[#d8d8d8] bg-white shadow-[2px_4px_15px_rgba(0,0,0,0.07)] grid place-items-center"
        >
          <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#272727" strokeWidth="1.5" strokeLinecap="round">
            <path d="M2.5 1.5 6 5l-3.5 3.5" />
          </svg>
        </button>
      )}
    </section>
  )
}

function IndustryTop({ industry, c, second, onOpen }: { industry: string; c: HomeCompany; second: boolean; onOpen: (slug: string) => void }) {
  const rows: [string, string][] = second
    ? [
        ['공고', `${c.active}건`],
        ['신입', `${c.entry}건`],
      ]
    : [
        ['공고', `${c.active}건`],
        ['이번 주', `+${c.new_7d}`],
      ]
  return (
    <button
      type="button"
      onClick={() => onOpen(c.slug)}
      className="home-press text-left rounded-2xl border border-[#485071] bg-white shadow-[2px_4px_15px_rgba(0,0,0,0.07)] px-[21px] pt-[17px] h-[132px] hover:border-[#272727]"
    >
      <p className="text-base leading-6 tracking-[-0.16px] text-[#272727]">
        <span className="font-bold text-(--color-accent)">#{industry.split('·')[0]}</span> 채용중인 공고 1위 기업
      </p>
      <div className="mt-3 h-px bg-[#e2e8ec]" />
      <div className="mt-[11px] flex items-center">
        <CompanyMark name={c.name} logo={c.logo} size={32} />
        <span className="ml-[14px] w-[110px] text-base font-medium leading-6 text-[#272727] truncate">{c.name}</span>
        <dl className="ml-auto mr-auto grid grid-cols-[auto_auto] gap-x-2 text-sm leading-5 text-[#474747]">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-medium">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </button>
  )
}
