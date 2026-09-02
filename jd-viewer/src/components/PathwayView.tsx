import { useMemo, useState } from 'react'
import { useCareerMap, type CareerCluster, type CareerEdge } from '../lib/useCareerMap'
import { Loader, ErrorState, SearchInput, hits } from './ui'

// 이동 경로 뷰 — "지금 여기서 어디로 갈 수 있고, 가려면 무엇이 비는가".
//
// 클러스터/트리 탭이 '누가 뽑고 있나'를 보여준다면 여기는 '내가 어디로 갈 수 있나'다.
// 군집도 인접도도 사람이 정한 직군 라벨이 아니라 JD 임베딩에서 나온다. 그래서
// 같은 '백엔드'라도 커머스 트래픽과 레거시 SI 가 다른 자리로 갈라져 나오고,
// 라벨이 달라도 하는 일이 겹치면 가깝게 붙는다.

export function PathwayView() {
  const { data, loading, error } = useCareerMap()
  const [selected, setSelected] = useState<number | null>(null)
  const [query, setQuery] = useState('')

  const byId = useMemo(() => {
    const m = new Map<number, CareerCluster>()
    for (const c of data?.clusters ?? []) m.set(c.id, c)
    return m
  }, [data])

  // 군집 이름은 자동으로 붙은 라벨이라 사람 머릿속의 말과 다를 때가 많다.
  // 그래서 대표 기술·기업까지 걸어야 '내가 아는 말' 로 군집을 찾을 수 있다.
  const shown = useMemo(
    () =>
      (data?.clusters ?? []).filter((c) =>
        hits(
          query,
          c.label,
          ...(c.tech ?? []).map((t) => t.name),
          ...(c.companies ?? []).map((x) => x.name),
        ),
      ),
    [data, query],
  )

  const current = selected != null ? byId.get(selected) : data?.clusters[0]
  const maxSize = Math.max(...(data?.clusters ?? []).map((c) => c.size), 1)

  if (loading) return <Loader label="커리어 맵 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="career_map.json 로드 실패"
        detail={error}
        hint={
          <>
            생성:{' '}
            <code className="text-(--color-text)">
              catch_capture/.venv/bin/python bin/build_career_map.py
            </code>{' '}
            (jd-viewer)
          </>
        }
      />
    )
  if (!data || !current)
    return <div className="p-8 text-(--color-muted)">커리어 맵 데이터가 없습니다.</div>

  return (
    <div className="flex flex-col md:flex-row flex-1 min-h-0 min-w-0 overflow-y-auto md:overflow-hidden">
      {/* 좌: 군집 목록 */}
      <aside className="w-full md:w-72 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-3">
        <h3 className="text-sm font-semibold text-(--color-text) px-1">일자리 군집</h3>
        <p className="text-[11px] text-(--color-muted) px-1 mb-2 leading-relaxed">
          공고 {data.jobs.toLocaleString()}건을 내용으로 {data.k}개로 나눈 결과.
          직군명이 아니라 JD 임베딩이 정한 경계다.
        </p>
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="군집·기술·기업 검색"
          className="mb-2"
        />
        {query && (
          <p className="text-[11px] text-(--color-muted) px-1 mb-1">
            {data.clusters.length}개 중 <b className="text-(--color-text)">{shown.length}개</b>
          </p>
        )}
        <ul className="flex flex-col gap-0.5">
          {shown.map((c) => {
            const on = c.id === current.id
            return (
              <li key={c.id}>
                <button
                  onClick={() => setSelected(c.id)}
                  className={`w-full text-left px-2 py-1.5 rounded ${
                    on ? 'bg-(--color-accent)/15' : 'hover:bg-(--color-bg)'
                  }`}
                >
                  <div className="flex items-baseline gap-2">
                    <span className="flex-1 text-xs text-(--color-text) truncate">{c.label}</span>
                    <span className="text-[11px] text-(--color-muted) tabular-nums shrink-0">
                      {c.size}
                    </span>
                  </div>
                  <span className="mt-1 block h-1 rounded bg-(--color-bg) overflow-hidden">
                    <span
                      className="block h-full bg-(--color-accent)"
                      style={{ width: `${(c.size / maxSize) * 100}%` }}
                    />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      {/* 우: 선택한 군집 + 이동 경로 */}
      <main className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5 flex flex-col gap-5">
        <ClusterHead c={current} totalJobs={data.jobs} />

        <section>
          <h3 className="text-base font-semibold text-(--color-text)">
            여기서 갈 수 있는 자리
          </h3>
          <p className="text-xs text-(--color-muted) mb-3">
            JD 내용이 가장 가까운 군집들. <b>격차</b>는 그쪽엔 흔한데 여기엔 드문
            기술 — 그게 이동에 드는 학습 비용이다.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {current.neighbors?.map((e) => (
              <EdgeCard key={e.to} e={e} onOpen={() => setSelected(e.to)} />
            ))}
          </div>
        </section>

        {current.samples.length > 0 && (
          <section>
            <h3 className="text-base font-semibold text-(--color-text) mb-1">
              이 군집의 대표 공고
            </h3>
            <p className="text-xs text-(--color-muted) mb-2">
              군집 중심에 가장 가까운 공고 — 가장 '전형적인' 자리다.
            </p>
            <ul className="flex flex-col gap-1">
              {current.samples.map((s) => (
                <li key={s.url}>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-baseline gap-2 px-2 py-1 rounded hover:bg-(--color-bg) text-sm text-(--color-text)"
                  >
                    <span className="truncate">{s.title}</span>
                    <span className="text-xs text-(--color-muted) shrink-0">{s.company}</span>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  )
}

function ClusterHead({ c, totalJobs }: { c: CareerCluster; totalJobs: number }) {
  return (
    <section>
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="text-xl font-semibold text-(--color-text)">{c.label}</h2>
        <span className="text-xs text-(--color-muted)">
          공고 {c.size.toLocaleString()}건 · 전체의 {c.share}%
        </span>
        <span
          className="text-[11px] px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)"
          title="군집 중심과의 평균 코사인. 낮을수록 성격이 섞인 군집이다."
        >
          응집도 {c.cohesion}
        </span>
      </div>

      <ChipRow
        title="이 군집을 특징짓는 기술"
        hint="전체 대비 과대표집된 순서. 단순 빈도로 뽑으면 어느 군집이든 Python·AWS 가 1등이라 구분이 안 된다."
        items={c.tech.map((t) => ({ key: t.name, label: t.name, sub: `${t.share}%` }))}
      />
      <ChipRow
        title="주요 기업"
        items={c.companies.map((x) => ({ key: x.name, label: x.name, sub: String(x.n) }))}
      />
      <ChipRow
        title="경력 요구"
        items={c.bands.map((x) => ({ key: x.name, label: x.name, sub: String(x.n) }))}
      />
      <p className="mt-2 text-[11px] text-(--color-muted)">
        전체 {totalJobs.toLocaleString()}건 기준
      </p>
    </section>
  )
}

function ChipRow({
  title,
  hint,
  items,
}: {
  title: string
  hint?: string
  items: { key: string; label: string; sub?: string }[]
}) {
  if (items.length === 0) return null
  return (
    <div className="mt-3">
      <div className="text-xs font-medium text-(--color-muted) mb-1" title={hint}>
        {title}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it) => (
          <span
            key={it.key}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border border-(--color-border) bg-(--color-bg) text-(--color-text)"
          >
            {it.label}
            {it.sub && <span className="text-(--color-muted)">{it.sub}</span>}
          </span>
        ))}
      </div>
    </div>
  )
}

function EdgeCard({ e, onOpen }: { e: CareerEdge; onOpen: () => void }) {
  const maxGap = Math.max(...e.gap.map((g) => g.to_share), 1)
  return (
    <div className="rounded border border-(--color-border) bg-(--color-bg) p-3">
      <button
        onClick={onOpen}
        className="text-left w-full group"
        title="이 군집으로 이동해서 보기"
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-(--color-text) group-hover:text-(--color-accent) truncate">
            {e.to_label}
          </span>
          <span className="text-[11px] text-(--color-muted) shrink-0 tabular-nums">
            근접도 {e.similarity}
          </span>
        </div>
      </button>

      {e.shared.length > 0 && (
        <div className="mt-2">
          <div className="text-[11px] text-(--color-muted) mb-1">이미 겹치는 것</div>
          <div className="flex flex-wrap gap-1">
            {e.shared.map((s) => (
              <span
                key={s}
                className="px-1.5 py-0.5 text-[11px] rounded bg-(--color-accent)/10 text-(--color-accent)"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2">
        <div className="text-[11px] text-(--color-muted) mb-1">
          더 필요한 것 (여기 → 저기, 공고 점유율)
        </div>
        {e.gap.length === 0 ? (
          <p className="text-[11px] text-(--color-muted)">
            요구 스택 차이가 뚜렷하지 않다 — 기술보다 도메인 경험이 갈림길인 이동이다.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {e.gap.map((g) => (
              <li key={g.name} className="flex items-center gap-2">
                <span className="w-24 shrink-0 text-xs text-(--color-text) truncate">{g.name}</span>
                <span className="flex-1 h-1.5 rounded bg-(--color-panel) overflow-hidden relative">
                  <span
                    className="absolute inset-y-0 left-0 bg-(--color-muted)/40"
                    style={{ width: `${(g.from_share / maxGap) * 100}%` }}
                  />
                  <span
                    className="absolute inset-y-0 bg-(--color-accent)"
                    style={{
                      left: `${(g.from_share / maxGap) * 100}%`,
                      width: `${((g.to_share - g.from_share) / maxGap) * 100}%`,
                    }}
                  />
                </span>
                <span className="w-24 shrink-0 text-right text-[11px] text-(--color-muted) tabular-nums">
                  {g.from_share}% → {g.to_share}%
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
