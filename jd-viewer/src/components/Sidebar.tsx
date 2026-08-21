import { emptyFilter, type FilterState } from '../lib/filter'
import type { Site } from '../types'
import { CAREER_BUCKETS } from '../types'
import { SidePanel } from './ui'

const SITES: Site[] = ['wanted', 'jumpit', 'jobkorea', 'saramin', 'dev', 'remote', 'ats']

// remote/ats 는 원문 그대로면 뜻이 안 통해 라벨을 붙인다.
const SITE_LABEL: Partial<Record<Site, string>> = {
  remote: '해외·원격',
  ats: '자체채용',
}

interface Props {
  filter: FilterState
  setFilter: (f: FilterState) => void
  topStacks: { name: string; count: number }[]
  roleCounts: { name: string; count: number }[]
  totalCount: number
  filteredCount: number
  open: boolean
  onClose: () => void
  /** 의미 검색 토글. 검색 API 가 없는 배포에서는 넘기지 않아 UI 자체가 안 뜬다. */
  semantic?: { on: boolean; setOn: (v: boolean) => void; loading: boolean; engines: { fts: number; vector: number } | null }
}

function toggle<T>(set: Set<T>, val: T): Set<T> {
  const next = new Set(set)
  if (next.has(val)) next.delete(val)
  else next.add(val)
  return next
}

export function Sidebar({ filter, setFilter, topStacks, roleCounts, totalCount, filteredCount, open, onClose, semantic }: Props) {
  return (
    <SidePanel side="left" desktopWidth="md:w-72" open={open} onClose={onClose} className="jd-side-panel">
     <div className="p-4 overflow-y-auto flex flex-col gap-5 text-sm h-full">
      <div className="flex items-start">
        <div>
          <h1 className="text-lg font-semibold text-(--color-text)"><span className="jd-head jd-head-lg">JD Viewer</span></h1>
          <p className="text-xs text-(--color-muted) mt-1">
            {filteredCount.toLocaleString()} / {totalCount.toLocaleString()} 건
          </p>
        </div>
        <button
          onClick={onClose}
          className="md:hidden ml-auto -mt-1 -mr-1 text-(--color-muted) hover:text-(--color-text) text-2xl leading-none w-8 h-8 rounded hover:bg-(--hover)"
          aria-label="필터 닫기"
        >
          ×
        </button>
      </div>

      <div>
        <input
          type="search"
          placeholder={semantic?.on ? '예: 재택 되는 백엔드 자리' : '회사/제목/본문 검색'}
          value={filter.query}
          onChange={(e) => setFilter({ ...filter, query: e.target.value })}
          className="w-full px-3 py-2 rounded bg-(--color-bg) border border-(--color-border) outline-none focus:border-(--color-accent)"
        />
        {semantic && (
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => semantic.setOn(!semantic.on)}
              role="switch"
              aria-checked={semantic.on}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs border transition ${
                semantic.on
                  ? 'bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40'
                  : 'text-(--color-muted) border-(--color-border) hover:bg-(--hover)'
              }`}
              title="키워드와 의미를 함께 보는 검색 (문장으로 물어도 됩니다)"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  semantic.on ? 'bg-(--color-accent)' : 'bg-(--color-muted)'
                }`}
              />
              의미 검색
            </button>
            {semantic.on && semantic.loading && (
              <span className="text-xs text-(--color-muted)">찾는 중…</span>
            )}
            {semantic.on && !semantic.loading && semantic.engines && (
              <span className="text-xs text-(--color-muted) tabular-nums">
                키워드 {semantic.engines.fts} · 의미 {semantic.engines.vector}
              </span>
            )}
          </div>
        )}
      </div>

      <FilterGroup title="모집 상태">
        {([
          ['hide', '모집중만'],
          ['show', '마감 포함'],
          ['only', '마감만'],
        ] as const).map(([v, label]) => (
          <Chip
            key={v}
            label={label}
            active={filter.closed === v}
            onClick={() => setFilter({ ...filter, closed: v })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title="사이트">
        {SITES.map((s) => (
          <Chip
            key={s}
            label={SITE_LABEL[s] ?? s}
            active={filter.sites.has(s)}
            onClick={() => setFilter({ ...filter, sites: toggle(filter.sites, s) })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title="직군">
        {roleCounts.map((r) => (
          <Chip
            key={r.name}
            label={`${r.name} (${r.count})`}
            active={filter.roles.has(r.name)}
            onClick={() => setFilter({ ...filter, roles: toggle(filter.roles, r.name) })}
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
        filter.roles.size > 0 ||
        filter.query.length > 0 ||
        filter.closed !== 'hide') && (
        <button
          onClick={() => setFilter(emptyFilter())}
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
          ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text) hover:border-(--color-accent)')
      }
    >
      {label}
    </button>
  )
}
