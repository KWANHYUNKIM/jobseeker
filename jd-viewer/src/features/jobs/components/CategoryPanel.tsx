import { useState, type ReactNode } from 'react'
import { CAREER_BUCKETS, type Site } from '../../../types'
import { emptyFilter, type Facets, type FilterState } from '../utils/filter'

export const SITES: Site[] = ['wanted', 'jumpit', 'jobkorea', 'saramin', 'dev', 'remote', 'ats', 'boards']

// remote/ats/boards 는 원문 그대로면 뜻이 안 통해 라벨을 붙인다.
export const SITE_LABEL: Partial<Record<Site, string>> = {
  remote: '해외·원격',
  ats: '자체채용',
  boards: '기타 보드·공공',
}

function toggle<T>(set: Set<T>, val: T): Set<T> {
  const next = new Set(set)
  if (next.has(val)) next.delete(val)
  else next.add(val)
  return next
}

type Axis = 'roles' | 'careers' | 'regions' | 'sizes' | 'stacks' | 'sites'
const TABS: { key: Axis; label: string }[] = [
  { key: 'roles', label: '직군' },
  { key: 'careers', label: '경력' },
  { key: 'regions', label: '지역' },
  { key: 'sizes', label: '기업 규모' },
  { key: 'stacks', label: '기술스택' },
  { key: 'sites', label: '사이트' },
]
// 큰 칸 아래 한 줄짜리 빠른 칸 — 지금 탭이 아닌 축 셋.
const QUICK: { key: Axis; label: string }[] = [
  { key: 'careers', label: '경력' },
  { key: 'regions', label: '지역' },
  { key: 'stacks', label: '기술' },
  { key: 'roles', label: '직군' },
]

type Item = { name: string; count: number }

/**
 * 전체 카테고리(캐치형 잡 리스트의 큰 필터 칸) — 탭 여섯(직군·경력·지역·기업 규모·기술스택·사이트),
 * 고른 탭의 칩이 회색 칸에 크게 깔리고, 그 아래 다른 축 셋이 한 줄씩 빠르게 놓인다.
 * 칩 건수는 "이걸 누르면 몇 건이 되는지"다(computeFacets 가 자기 축을 빼고 센 값).
 */
export function CategoryPanel({
  filter,
  setFilter,
  facets,
}: {
  filter: FilterState
  setFilter: (f: FilterState) => void
  facets: Facets
}) {
  const [tab, setTab] = useState<Axis>('roles')

  const items = (axis: Axis): Item[] => {
    switch (axis) {
      case 'roles':
        return facets.roles
      case 'careers':
        return CAREER_BUCKETS.map((c) => ({ name: c, count: facets.careerCount.get(c) ?? 0 }))
      case 'regions':
        return facets.regions
      case 'sizes':
        return facets.sizes
      case 'stacks':
        return facets.stacks.slice(0, 40)
      case 'sites':
        return SITES.map((s) => ({ name: s, count: facets.siteCount.get(s) ?? 0 }))
    }
  }
  const selected = (axis: Axis): Set<string> => filter[axis] as Set<string>
  const flip = (axis: Axis, name: string) => {
    if (axis === 'regions') {
      // 지역을 바꾸면 앞서 고른 시군구는 뜻을 잃는다(다른 시도의 구다). 같이 비운다.
      setFilter({ ...filter, regions: toggle(filter.regions, name), districts: new Set() })
      return
    }
    setFilter({ ...filter, [axis]: toggle(selected(axis), name) } as FilterState)
  }
  const label = (axis: Axis, name: string) => (axis === 'sites' ? (SITE_LABEL[name as Site] ?? name) : name)

  return (
    <section aria-label="전체 카테고리" className="rounded-xl bg-white shadow-[0_2px_12px_rgba(0,0,0,0.12)] overflow-hidden">
      <div className="flex items-center justify-between px-[26px] pt-5">
        <h2 className="text-lg font-bold leading-[26px] tracking-[-0.16px] text-[#272727]">전체 카테고리</h2>
        <button
          type="button"
          onClick={() => setFilter({ ...emptyFilter(), query: filter.query })}
          className="text-sm tracking-[-0.16px] text-[#474747] hover:text-[#272727]"
        >
          전체 초기화 ↻
        </button>
      </div>
      <div role="tablist" className="mt-[17px] grid grid-cols-3 sm:grid-cols-6">
        {TABS.map((t) => {
          const on = t.key === tab
          const n = selected(t.key).size
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setTab(t.key)}
              className={
                'relative h-[38px] text-base tracking-[-0.16px] ' +
                (on ? 'font-bold text-(--color-accent) after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-(--color-accent)' : 'font-medium text-[#474747] hover:text-[#272727]')
              }
            >
              {t.label}
              {n > 0 && <span className="ml-1 text-xs font-medium text-(--color-accent)">{n}</span>}
            </button>
          )
        })}
      </div>
      <div className="bg-[#f8f8f8] min-h-[120px] px-[26px] py-5 flex flex-wrap content-start gap-2">
        {items(tab).length === 0 && <p className="text-sm text-[#999]">아직 집계된 항목이 없습니다</p>}
        {items(tab).map((it) => (
          <BigChip key={it.name} on={selected(tab).has(it.name)} count={it.count} onClick={() => flip(tab, it.name)}>
            {label(tab, it.name)}
          </BigChip>
        ))}
      </div>
      <div className="px-[26px] pt-3 pb-4 flex flex-col gap-3">
        {QUICK.filter((q) => q.key !== tab)
          .slice(0, 3)
          .map((q) => (
            <div key={q.key} className="flex items-center gap-[30px] min-w-0">
              <span className="shrink-0 w-[26px] text-sm font-bold tracking-[-0.16px] text-[#272727]">{q.label}</span>
              <div className="flex gap-2 min-w-0 overflow-x-auto no-scrollbar">
                {items(q.key)
                  .slice(0, 12)
                  .map((it) => (
                    <SmallChip key={it.name} on={selected(q.key).has(it.name)} count={it.count} onClick={() => flip(q.key, it.name)}>
                      {label(q.key, it.name)}
                    </SmallChip>
                  ))}
              </div>
            </div>
          ))}
      </div>
    </section>
  )
}

function BigChip({ on, count, onClick, children }: { on: boolean; count: number; onClick: () => void; children: ReactNode }) {
  const empty = count === 0 && !on
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'inline-flex items-center gap-1.5 h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] transition ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]') +
        (empty ? ' opacity-40' : '')
      }
    >
      {children}
      <span className={'text-xs font-normal tabular-nums ' + (on ? 'text-[#ffd9d9]' : 'text-[#999]')}>{count.toLocaleString()}</span>
    </button>
  )
}

function SmallChip({ on, count, onClick, children }: { on: boolean; count: number; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'shrink-0 inline-flex items-center gap-1.5 h-[30px] px-[13px] rounded-[15px] border text-[13px] tracking-[-0.16px] whitespace-nowrap ' +
        (on ? 'border-(--color-accent) text-(--color-accent)' : 'border-[#e2e2e2] text-[#474747] hover:border-[#999]')
      }
    >
      {children}
      <span className={'tabular-nums ' + (on ? 'text-(--color-accent)' : 'text-[#999]')}>{count.toLocaleString()}</span>
    </button>
  )
}
