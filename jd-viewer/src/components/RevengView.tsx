import { useMemo, useState } from 'react'
import { useRevengIndex, type IndexEntry } from '../lib/useReveng'
import { CompanyTeardown } from './CompanyTeardown'
import { Loader, ErrorState, EmptyState } from './ui'

// 기술 역설계 — 회사가 무엇으로 돈을 벌고, 그 돈이 어떤 도메인으로 쪼개지고,
// 각 기능이 어떻게 구현되고 서로 어떻게 이어지는지.
//
// 다른 탭들은 공고 데이터를 집계해 보여준다. 여기는 성격이 다르다 — 공개 자료를 읽고
// 사람이 재구성한 내용이라, 어디까지가 회사가 말한 것이고 어디부터가 추정인지를
// 화면이 항상 같이 보여줘야 한다. 그래서 신뢰도 뱃지가 이 탭의 1급 요소다.

export function RevengView() {
  const { data, loading, error } = useRevengIndex()
  const [slug, setSlug] = useState<string | null>(null)
  const [country, setCountry] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)

  const companies = useMemo(() => data?.companies ?? [], [data])
  const categories = useMemo(
    () => [...new Set(companies.map((c) => c.category))].sort(),
    [companies],
  )
  const countries = useMemo(
    () => [...new Set(companies.map((c) => c.country))].sort(),
    [companies],
  )
  const shown = useMemo(
    () =>
      companies.filter(
        (c) => (!country || c.country === country) && (!category || c.category === category),
      ),
    [companies, country, category],
  )

  if (slug) return <CompanyTeardown slug={slug} onBack={() => setSlug(null)} />
  if (loading) return <Loader label="역설계 데이터 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="reveng/index.json 로드 실패"
        detail={error}
        hint={
          <>
            엔진이 아직 한 번도 안 돌았을 수 있습니다. 확인:{' '}
            <code className="text-(--color-text)">python engine/validate.py</code>
          </>
        }
      />
    )

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0 overflow-y-auto">
      <header className="px-4 py-3 border-b border-(--color-border) bg-(--color-panel)/60">
        <h2 className="text-base font-semibold text-(--color-text)">기술 역설계</h2>
        <p className="text-xs text-(--color-muted) mt-0.5">
          비즈니스 모델 → 도메인 → 기능 구현 → 시스템 연결. 공개 자료만으로 재구성하고,
          회사가 직접 말한 것과 추정한 것을 구분해 표시합니다.
          {data?.updated_at && <span className="ml-1">· 갱신 {data.updated_at}</span>}
        </p>
      </header>

      {companies.length === 0 ? (
        <EmptyState
          title="아직 공개된 회사가 없습니다"
          hint={
            <>
              엔진이 사이클을 돌면 여기에 쌓입니다. 대기열:{' '}
              <code className="text-(--color-text)">engine/state/QUEUE.md</code>
            </>
          }
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-1.5 px-4 py-2 border-b border-(--color-border)">
            <FilterChip active={!country && !category} onClick={() => { setCountry(null); setCategory(null) }}>
              전체 {companies.length}
            </FilterChip>
            <span className="w-px h-4 bg-(--color-border) mx-1" />
            {countries.map((k) => (
              <FilterChip key={k} active={country === k} onClick={() => setCountry(country === k ? null : k)}>
                {data?.countries?.[k] ?? k}
              </FilterChip>
            ))}
            <span className="w-px h-4 bg-(--color-border) mx-1" />
            {categories.map((k) => (
              <FilterChip key={k} active={category === k} onClick={() => setCategory(category === k ? null : k)}>
                {k}
              </FilterChip>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
            {shown.map((c) => (
              <CompanyCard key={c.slug} c={c} countryLabel={data?.countries?.[c.country] ?? c.country} onOpen={() => setSlug(c.slug)} />
            ))}
          </div>

          {data && data.domains.length > 0 && (
            <section className="px-4 pb-6">
              <h3 className="text-sm font-semibold text-(--color-text) mb-2">
                지금까지 나온 도메인{' '}
                <span className="text-xs font-normal text-(--color-muted)">
                  여러 회사가 같은 문제를 어떻게 다르게 풀었는지 비교하는 축
                </span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {data.domains.map((d) => (
                  <span
                    key={d}
                    className="px-2 py-0.5 rounded border border-(--color-border) text-xs text-(--color-muted)"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}

function CompanyCard({
  c,
  countryLabel,
  onOpen,
}: {
  c: IndexEntry
  countryLabel: string
  onOpen: () => void
}) {
  return (
    <button
      onClick={onOpen}
      className="text-left rounded-lg border border-(--color-border) bg-(--color-panel) p-3 hover:border-(--color-accent) transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-semibold text-(--color-text) truncate">{c.name}</div>
          <div className="text-[11px] text-(--color-muted) truncate">{c.name_en}</div>
        </div>
        <span
          className={
            'shrink-0 px-1.5 py-0.5 rounded text-[10px] border ' +
            (c.status === 'done'
              ? 'border-(--color-accent)/40 text-(--color-accent)'
              : 'border-(--color-border) text-(--color-muted)')
          }
          title={c.status === 'done' ? '도메인이 모두 채워짐' : '아직 파는 중'}
        >
          {c.status === 'done' ? '완료' : '진행 중'}
        </span>
      </div>
      <p className="text-xs text-(--color-muted) mt-2 line-clamp-2">{c.one_liner}</p>
      <div className="flex items-center gap-1.5 mt-2.5 text-[11px] text-(--color-muted)">
        <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border)">
          {countryLabel}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border)">
          {c.category}
        </span>
        <span className="ml-auto tabular-nums">기능 {c.features_done}</span>
      </div>
    </button>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={
        'px-2 py-0.5 rounded text-xs border transition-colors ' +
        (active
          ? 'border-(--color-accent) text-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text)')
      }
    >
      {children}
    </button>
  )
}
