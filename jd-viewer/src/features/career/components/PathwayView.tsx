import { useMemo, useState, type ReactNode } from 'react'
import { useCareerMap, type CareerCluster, type CareerEdge } from '../hooks/useCareerMap'
import { Loader, ErrorState, CompanyMark, hits } from '../../../components/ui'

// 이동 경로 뷰 — "지금 여기서 어디로 갈 수 있고, 가려면 무엇이 비는가".
//
// 클러스터/트리 탭이 '누가 뽑고 있나'를 보여준다면 여기는 '내가 어디로 갈 수 있나'다.
// 군집도 인접도도 사람이 정한 직군 라벨이 아니라 JD 임베딩에서 나온다. 그래서
// 같은 '백엔드'라도 커머스 트래픽과 레거시 SI 가 다른 자리로 갈라져 나오고,
// 라벨이 달라도 하는 일이 겹치면 가깝게 붙는다.
//
// 캐치형(Penpot 19) — 왼쪽 군집 목록, 가운데 고른 군집(검은 띠·기술 막대·주요 기업·경력·대표 공고),
// 오른쪽 '여기서 갈 수 있는 자리'(근접도·이미 겹치는 것·더 필요한 것).

export function PathwayView({ query = '' }: { query?: string }) {
  const { data, loading, error } = useCareerMap()
  const [selected, setSelected] = useState<number | null>(null)

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
        hits(query, c.label, ...(c.tech ?? []).map((t) => t.name), ...(c.companies ?? []).map((x) => x.name)),
      ),
    [data, query],
  )

  const current = (selected != null ? byId.get(selected) : null) ?? shown[0] ?? data?.clusters[0]

  if (loading) return <Loader label="커리어 맵 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="career_map.json 로드 실패"
        detail={error}
        hint={
          <>
            생성: <code className="text-(--color-text)">catch_capture/.venv/bin/python bin/build_career_map.py</code> (jd-viewer)
          </>
        }
      />
    )
  if (!data || !current) return <div className="p-8 text-(--color-muted)">커리어 맵 데이터가 없습니다.</div>

  return (
    <div className="grid gap-6 lg:grid-cols-[282px_minmax(0,1fr)_358px] items-start">
      {/* 왼쪽: 군집 목록 */}
      <aside className="rounded-[22px] border border-[#e2e8ec] bg-white px-4 pt-5 pb-3">
        <h3 className="px-2 text-[17px] font-bold text-[#272727]">
          일자리 군집 <span className="ml-1 text-[13px] font-normal text-[#999]">{data.k}개</span>
        </h3>
        <p className="mt-1 px-2 text-xs leading-[18px] text-[#999]">
          공고 {data.jobs.toLocaleString()}건을 JD 내용으로 나눈 결과예요. 직군명이 아니라 임베딩이 정한 경계예요.
        </p>
        {query && (
          <p className="mt-2 px-2 text-xs text-[#777]">
            {data.clusters.length}개 중 <b className="text-[#272727]">{shown.length}개</b>
          </p>
        )}
        <ul className="mt-3 flex flex-col gap-0.5">
          {shown.map((c) => {
            const on = c.id === current.id
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setSelected(c.id)}
                  aria-pressed={on}
                  className={'w-full flex items-baseline gap-2 rounded-[10px] px-3 py-2 text-left ' + (on ? 'bg-(--color-accent) text-white' : 'text-[#474747] hover:bg-[#f7f9fa]')}
                >
                  <span className={'flex-1 truncate text-sm ' + (on ? 'font-bold' : '')}>{c.label}</span>
                  <span className={'shrink-0 text-xs tabular-nums ' + (on ? 'text-[#ffd9d9]' : 'text-[#999]')}>{c.size}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      {/* 가운데: 고른 군집 */}
      <main className="min-w-0 flex flex-col gap-5">
        <section className="rounded-[24px] bg-[#272727] px-7 py-6 text-white">
          <div className="text-[13px] text-[#bbb]">선택한 군집</div>
          <h2 className="mt-1 text-2xl font-bold leading-9 break-keep">{current.label}</h2>
          <div className="mt-4 grid grid-cols-3 gap-2.5">
            <Dark label="공고" value={`${current.size.toLocaleString()}건`} />
            <Dark label="전체에서" value={`${current.share}%`} />
            <Dark label="응집도" value={String(current.cohesion)} title="군집 중심과의 평균 코사인. 낮을수록 성격이 섞인 군집이에요." />
          </div>
        </section>

        <Card title="이 군집을 특징짓는 기술" hint="전체 대비 과대표집된 기술을 골라, 이 군집 공고에서 쓰이는 비율 순으로 늘어놓았어요.">
          <Bars items={[...current.tech].sort((a, b) => b.share - a.share).map((t) => ({ label: t.name, value: t.share, text: `${t.share}%` }))} />
        </Card>

        <div className="grid sm:grid-cols-2 gap-5 items-start">
          <Card title="주요 기업">
            <ul className="flex flex-col gap-2.5">
              {current.companies.map((x) => (
                <li key={x.name} className="flex items-center gap-2.5">
                  <span className="grid place-items-center w-7 h-7 rounded-lg overflow-hidden shrink-0">
                    <CompanyMark name={x.name} size={28} />
                  </span>
                  <span className="flex-1 truncate text-sm text-[#272727]">{x.name}</span>
                  <span className="text-sm font-bold text-[#272727] tabular-nums">{x.n}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="경력 요구">
            <Bars items={current.bands.map((x) => ({ label: x.name, value: x.n, text: String(x.n) }))} labelW={76} />
          </Card>
        </div>

        {current.samples.length > 0 && (
          <Card title="이 군집의 대표 공고" hint="군집 중심에 가장 가까운 공고 — 가장 '전형적인' 자리예요.">
            <ul>
              {current.samples.map((s) => (
                <li key={s.url} className="border-b border-[#eef1f3] last:border-b-0">
                  <a href={s.url} target="_blank" rel="noreferrer" className="group flex items-center gap-3 py-2.5">
                    <span className="grid place-items-center w-8 h-8 rounded-lg overflow-hidden shrink-0">
                      <CompanyMark name={s.company} size={32} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[15px] font-medium text-[#272727] group-hover:underline underline-offset-2">{s.title}</span>
                      <span className="block truncate text-xs text-[#999]">{s.company}</span>
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </main>

      {/* 오른쪽: 여기서 갈 수 있는 자리 */}
      <aside className="min-w-0">
        <h3 className="text-[19px] font-bold text-[#272727]">여기서 갈 수 있는 자리</h3>
        <p className="mt-1 text-[13px] leading-[19px] text-[#999]">
          JD 내용이 가장 가까운 군집들. <b className="font-medium text-[#666]">더 필요한 것</b>은 그쪽엔 흔한데 여기엔 드문 기술 — 그게 이동에 드는 학습 비용이에요.
        </p>
        <div className="mt-4 flex flex-col gap-3">
          {current.neighbors?.map((e) => (
            <EdgeCard key={e.to} e={e} onOpen={() => setSelected(e.to)} />
          ))}
        </div>
      </aside>
    </div>
  )
}

function Dark({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="rounded-2xl bg-white/8 px-4 py-3" title={title}>
      <div className="text-xs text-[#bbb]">{label}</div>
      <div className="mt-0.5 text-xl font-bold tabular-nums">{value}</div>
    </div>
  )
}

function Card({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-6 pt-[22px] pb-5">
      <h3 className="text-[17px] font-bold text-[#272727]" title={hint}>
        {title}
      </h3>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function Bars({ items, labelW = 112 }: { items: { label: string; value: number; text: string }[]; labelW?: number }) {
  if (!items.length) return <p className="text-sm text-[#999]">데이터 없음</p>
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((it) => (
        <li key={it.label} className="flex items-center">
          <span className="shrink-0 truncate text-sm text-[#474747]" style={{ width: labelW }}>
            {it.label}
          </span>
          <span className="flex-1 h-3 rounded-md bg-[#f1f3f5] overflow-hidden">
            <span className="block h-full rounded-md bg-[#f67979]" style={{ width: `${(it.value / max) * 100}%` }} />
          </span>
          <span className="w-14 shrink-0 text-right text-sm font-bold text-[#272727] tabular-nums">{it.text}</span>
        </li>
      ))}
    </ul>
  )
}

function EdgeCard({ e, onOpen }: { e: CareerEdge; onOpen: () => void }) {
  const maxGap = Math.max(...e.gap.map((g) => g.to_share), 1)
  return (
    <div className="rounded-[18px] border border-[#e2e8ec] bg-white px-5 py-[18px]">
      <button type="button" onClick={onOpen} className="group w-full flex items-start gap-2 text-left" title="이 군집으로 옮겨 보기">
        <span className="flex-1 min-w-0 text-[15px] font-bold leading-[22px] text-[#272727] group-hover:underline underline-offset-2 break-keep">{e.to_label}</span>
        <span className="shrink-0 rounded bg-(--color-accent-weak) px-[7px] text-xs leading-[22px] text-(--color-accent) tabular-nums">근접도 {e.similarity}</span>
      </button>

      {e.shared.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-[#999]">이미 겹치는 것</div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {e.shared.map((s) => (
              <span key={s} className="rounded bg-[#eaf8f0] px-[7px] text-xs leading-[22px] text-[#1e9e5a]">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3">
        <div className="text-xs text-[#999]">더 필요한 것 (여기 → 저기, 공고 점유율)</div>
        {e.gap.length === 0 ? (
          <p className="mt-1.5 text-xs text-[#999]">요구 스택 차이가 뚜렷하지 않아요 — 기술보다 도메인 경험이 갈림길인 이동이에요.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1.5">
            {e.gap.map((g) => (
              <li key={g.name} className="flex items-center gap-2">
                <span className="w-20 shrink-0 truncate text-[13px] text-[#272727]">{g.name}</span>
                <span className="relative flex-1 h-2 rounded bg-[#f1f3f5] overflow-hidden">
                  <span className="absolute inset-y-0 left-0 bg-[#c4c4c4]" style={{ width: `${(g.from_share / maxGap) * 100}%` }} />
                  <span
                    className="absolute inset-y-0 bg-(--color-accent)"
                    style={{ left: `${(g.from_share / maxGap) * 100}%`, width: `${((g.to_share - g.from_share) / maxGap) * 100}%` }}
                  />
                </span>
                <span className="w-[88px] shrink-0 text-right text-xs text-[#777] tabular-nums">
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
