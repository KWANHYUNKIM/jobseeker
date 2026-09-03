import { emptyFilter, type FilterState, type Facets } from '../lib/filter'
import type { Site } from '../types'
import { CAREER_BUCKETS } from '../types'
import { CareerIcon, RoleIcon, SizeIcon } from './ChipIcons'
import { RegionIcon } from './RegionIcon'
import { SidePanel, TechIcon } from './ui'

const SITES: Site[] = ['wanted', 'jumpit', 'jobkorea', 'saramin', 'dev', 'remote', 'ats']

// remote/ats 는 원문 그대로면 뜻이 안 통해 라벨을 붙인다.
const SITE_LABEL: Partial<Record<Site, string>> = {
  remote: '해외·원격',
  ats: '자체채용',
}

interface Props {
  filter: FilterState
  setFilter: (f: FilterState) => void
  /**
   * 칩에 붙는 건수. 축마다 "자기 축을 뺀 나머지 필터"를 적용해 센 값이라
   * (computeFacets), 숫자가 곧 "이걸 누르면 몇 건이 되는지"다.
   */
  facets: Facets
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

export function Sidebar({ filter, setFilter, facets, totalCount, filteredCount, open, onClose, semantic }: Props) {
  const { regions, districts, sizes, roles, stacks, siteCount, careerCount } = facets
  // 시군구는 지역을 딱 하나 골랐을 때만 의미가 있다 — 여러 시도의 구를 한 줄에
  // 늘어놓으면 같은 이름(중구·남구)이 뒤섞여 무엇을 고른 건지 알 수 없다.
  const onlyRegion = filter.regions.size === 1 ? [...filter.regions][0] : null

  // 지역을 바꾸면 앞서 고른 시군구는 뜻을 잃는다(다른 시도의 구다). 같이 비운다.
  const toggleRegion = (name: string) =>
    setFilter({ ...filter, regions: toggle(filter.regions, name), districts: new Set() })

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
            count={siteCount.get(s) ?? 0}
            active={filter.sites.has(s)}
            onClick={() => setFilter({ ...filter, sites: toggle(filter.sites, s) })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title="지역">
        {regions.map((r) => (
          <Chip
            key={r.name}
            label={r.name}
            count={r.count}
            leading={<RegionIcon region={r.name} />}
            active={filter.regions.has(r.name)}
            onClick={() => toggleRegion(r.name)}
          />
        ))}
      </FilterGroup>

      {districts.length > 0 && (
        <FilterGroup title={`${onlyRegion} 시·군·구`}>
          {districts.map((d) => (
            <Chip
              key={d.name}
              label={d.name}
              count={d.count}
              active={filter.districts.has(d.name)}
              onClick={() => setFilter({ ...filter, districts: toggle(filter.districts, d.name) })}
            />
          ))}
        </FilterGroup>
      )}

      {sizes.length > 0 && (
        <FilterGroup title="기업 규모">
          {sizes.map((s) => (
            <Chip
              key={s.name}
              label={s.name}
              count={s.count}
              leading={<SizeIcon size={s.name} />}
              active={filter.sizes.has(s.name)}
              onClick={() => setFilter({ ...filter, sizes: toggle(filter.sizes, s.name) })}
            />
          ))}
        </FilterGroup>
      )}

      <FilterGroup title="직군">
        {roles.map((r) => (
          <Chip
            key={r.name}
            label={r.name}
            count={r.count}
            leading={<RoleIcon role={r.name} />}
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
            count={careerCount.get(c) ?? 0}
            leading={<CareerIcon career={c} />}
            active={filter.careers.has(c)}
            onClick={() => setFilter({ ...filter, careers: toggle(filter.careers, c) })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title={`기술스택 (상위 ${Math.min(40, stacks.length)})`}>
        {stacks.slice(0, 40).map((s) => (
          <Chip
            key={s.name}
            label={s.name}
            count={s.count}
            icon={s.name}
            active={filter.stacks.has(s.name)}
            onClick={() => setFilter({ ...filter, stacks: toggle(filter.stacks, s.name) })}
          />
        ))}
      </FilterGroup>

      {(filter.sites.size > 0 ||
        filter.regions.size > 0 ||
        filter.districts.size > 0 ||
        filter.sizes.size > 0 ||
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
  icon,
  count,
  leading,
}: {
  label: string
  active: boolean
  onClick: () => void
  /** 이 칩이 가리키는 기술 이름. 로고가 있으면 앞에 붙는다. */
  icon?: string
  /** 이 칩을 누르면 남는 건수. 안 넘기면 숫자를 붙이지 않는다. */
  count?: number
  /** 라벨 앞에 놓을 그림(지역 랜드마크 등). icon 과 달리 그리는 쪽이 정한다. */
  leading?: React.ReactNode
}) {
  // 0건 칩은 흐리게. 사이트·지역·규모·경력처럼 목록이 고정된 축은 0건이어도 자리를
  // 지키므로(computeFacets), 여기서 흐리게 만들어 "눌러도 빈 목록"임을 알린다.
  // 직군·기술스택은 성격상 동적 목록이라 0건이면 애초에 오지 않는다.
  const empty = count === 0 && !active
  return (
    <button
      onClick={onClick}
      className={
        'inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs border transition ' +
        (active
          ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text) hover:border-(--color-accent)') +
        (empty ? ' opacity-40' : '')
      }
    >
      {leading}
      {icon && <TechIcon tech={icon} size={13} />}
      {label}
      {count !== undefined && (
        <span className={'tabular-nums ' + (active ? 'opacity-80' : 'opacity-60')}>
          {count.toLocaleString()}
        </span>
      )}
    </button>
  )
}
