import type { FilterState } from '../lib/filter'
import type { Site } from '../types'
import { CAREER_BUCKETS } from '../types'
import { SidePanel } from './ui'

const SITES: Site[] = ['wanted', 'jumpit', 'jobkorea', 'saramin', 'dev']

interface Props {
  filter: FilterState
  setFilter: (f: FilterState) => void
  topStacks: { name: string; count: number }[]
  totalCount: number
  filteredCount: number
  open: boolean
  onClose: () => void
}

function toggle<T>(set: Set<T>, val: T): Set<T> {
  const next = new Set(set)
  if (next.has(val)) next.delete(val)
  else next.add(val)
  return next
}

export function Sidebar({ filter, setFilter, topStacks, totalCount, filteredCount, open, onClose }: Props) {
  return (
    <SidePanel side="left" desktopWidth="md:w-72" open={open} onClose={onClose}>
     <div className="p-4 overflow-y-auto flex flex-col gap-5 text-sm h-full">
      <div className="flex items-start">
        <div>
          <h1 className="text-lg font-semibold text-(--color-text)">JD Viewer</h1>
          <p className="text-xs text-(--color-muted) mt-1">
            {filteredCount.toLocaleString()} / {totalCount.toLocaleString()} 건
          </p>
        </div>
        <button
          onClick={onClose}
          className="md:hidden ml-auto -mt-1 -mr-1 text-(--color-muted) hover:text-(--color-text) text-2xl leading-none w-8 h-8 rounded hover:bg-white/5"
          aria-label="필터 닫기"
        >
          ×
        </button>
      </div>

      <div>
        <input
          type="search"
          placeholder="회사/제목/본문 검색"
          value={filter.query}
          onChange={(e) => setFilter({ ...filter, query: e.target.value })}
          className="w-full px-3 py-2 rounded bg-(--color-bg) border border-(--color-border) outline-none focus:border-(--color-accent)"
        />
      </div>

      <FilterGroup title="사이트">
        {SITES.map((s) => (
          <Chip
            key={s}
            label={s}
            active={filter.sites.has(s)}
            onClick={() => setFilter({ ...filter, sites: toggle(filter.sites, s) })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title="경력">
        {CAREER_BUCKETS.map((c) => (
          <Chip
            key={c}
            label={c}
            active={filter.careers.has(c)}
            onClick={() => setFilter({ ...filter, careers: toggle(filter.careers, c) })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title={`기술스택 (상위 ${Math.min(40, topStacks.length)})`}>
        {topStacks.slice(0, 40).map((s) => (
          <Chip
            key={s.name}
            label={`${s.name} (${s.count})`}
            active={filter.stacks.has(s.name)}
            onClick={() => setFilter({ ...filter, stacks: toggle(filter.stacks, s.name) })}
          />
        ))}
      </FilterGroup>

      {(filter.sites.size > 0 ||
        filter.careers.size > 0 ||
        filter.stacks.size > 0 ||
        filter.query.length > 0) && (
        <button
          onClick={() =>
            setFilter({
              sites: new Set(),
              careers: new Set(),
              stacks: new Set(),
              query: '',
            })
          }
          className="mt-auto px-3 py-2 rounded border border-(--color-border) hover:border-(--color-accent) text-(--color-muted) hover:text-(--color-text) transition"
        >
          필터 초기화
        </button>
      )}
     </div>
    </SidePanel>
  )
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs uppercase tracking-wider text-(--color-muted) mb-2">{title}</h3>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={
        'px-2 py-1 rounded text-xs border transition ' +
        (active
          ? 'bg-(--color-accent) text-black border-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text) hover:border-(--color-accent)')
      }
    >
      {label}
    </button>
  )
}
