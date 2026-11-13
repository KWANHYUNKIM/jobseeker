import { useState } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import type { HomeCompany } from '../../home/api'
import { ddayLabel, ddayUrgent, shortTitle } from '../../home/utils'

const PER = 8
const PAGES = 2

/** 카드 머리 칩 — 칸마다 다른 근거(이번 주 새 공고·공고 수·신입·규모·업종·마감·직군)를 하나씩. */
function chipOf(c: HomeCompany, i: number): string {
  const by = [
    () => `💼 이번 주 +${c.new_7d}`,
    () => `🔥 공고 ${c.active}건`,
    () => (c.entry > 0 ? `🎮 신입 ${c.entry}건` : `🎮 이번 주 +${c.new_7d}`),
    () => `📌 ${c.size}`,
    () => `🏷 ${c.industry}`,
    () => (c.soonest_dday != null && c.soonest_dday <= 7 ? '⏰ 마감 임박' : `⏰ 공고 ${c.active}건`),
    () => `🛡 ${c.roles[0] ?? c.industry}`,
    () => `🛒 ${c.industry}`,
  ]
  return by[i % by.length]()
}

/** 계열사(토스·토스증권…, 카카오·카카오페이…)는 앞에 나온 한 곳만 — 한 화면이 한 그룹으로 차지 않게. */
function oneEach(all: HomeCompany[]): HomeCompany[] {
  const out: HomeCompany[] = []
  for (const c of all) {
    if (c.titles.length === 0) continue
    if (out.some((o) => c.name.startsWith(o.name) || o.name.startsWith(c.name))) continue
    out.push(c)
  }
  return out
}

/**
 * '지금 주목받는 공고'(캐치형 잡 리스트 맨 위) — 주목순 회사의 대표 공고 여덟 칸, 두 쪽.
 * 회사 목록은 메인과 같은 `/api/home` 이다(페이지가 받아 넘긴다). 없으면 칸 자체를 그리지 않는다.
 */
export function HotJobs({ companies }: { companies: HomeCompany[] | null }) {
  const [page, setPage] = useState(0)
  if (!companies) return null
  const cos = oneEach(companies)
  if (cos.length === 0) return null
  const pages = Math.min(PAGES, Math.ceil(cos.length / PER))
  const shown = cos.slice(page * PER, page * PER + PER)

  return (
    <section aria-label="지금 주목받는 공고">
      <div className="flex items-center justify-between pl-[10px] pr-[23px]">
        <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">지금 주목받는 공고</h2>
        {pages > 1 && (
          <div className="flex gap-[5px]">
            {Array.from({ length: pages }, (_, k) => (
              <button
                key={k}
                type="button"
                aria-label={`${k + 1}쪽`}
                aria-current={k === page}
                onClick={() => setPage(k)}
                className={'w-2 h-2 rounded-full ' + (k === page ? 'bg-black' : 'bg-[#f0f0f0]')}
              />
            ))}
          </div>
        )}
      </div>
      <div className="mt-[14px] grid grid-cols-2 lg:grid-cols-4 rounded-[10px] border border-[#666] overflow-hidden">
        {shown.map((c, i) => {
          const t = c.titles[0]
          const to = paths.job({ site: t.site as never, pid: t.pid })
          return (
            <a
              key={c.slug}
              href={to}
              onClick={onLinkClick(to)}
              className={
                'group relative h-[200px] px-[25px] pt-[25px] bg-white hover:bg-[#fafafa] ' +
                (i < shown.length - (shown.length % 4 || 4) ? 'border-b border-[#ddd]' : '')
              }
            >
              <span className="absolute right-[25px] top-[31px] text-base font-medium tracking-[-0.16px] tabular-nums">
                <span className={ddayUrgent(c.soonest_dday) ? 'text-(--color-accent)' : 'text-[#999]'}>{ddayLabel(c.soonest_dday)}</span>
              </span>
              <span className="grid place-items-center w-16 h-16 rounded-[14px] bg-white overflow-hidden">
                <CompanyMark name={c.name} logo={c.logo} size={64} />
              </span>
              <span className="mt-4 inline-block rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] text-[#474747]">
                {chipOf(c, i)}
              </span>
              <span className="mt-2 block text-lg font-bold leading-[26px] tracking-[-0.3px] text-[#272727] truncate">{c.name}</span>
              <span className="mt-0.5 block text-[15px] leading-[21px] tracking-[-0.16px] text-[#666] truncate group-hover:text-[#272727]">
                {shortTitle(t.title)}
              </span>
            </a>
          )
        })}
      </div>
    </section>
  )
}
