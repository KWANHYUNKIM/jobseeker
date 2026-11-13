import { useMemo, useState } from 'react'
import { CATEGORY_ORDER, SPEC_COLUMNS, fmtSpec, priceOf, priceSuspect, tierOf, won, type Category, type HwData, type Part } from '../utils/hardware'
import { navigate, onLinkClick, useRoute, useSetQuery } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
import { MoveBadge, NOINDEX, PriceChart } from './HardwarePrices'
import { GameCompare, PerfLadder, VendorBench } from './HardwareCharts'
import { OfficialImage } from './OfficialImage'
import { DurabilityNotes, ModelTable, SaleForms } from './HardwareModels'
import { TIER_COLOR, TierBadge } from './HardwareView'
import { NameGuide, PopularPick, SameTierCard } from './HardwarePopular'
import { FieldNotes } from './HardwareNotes'

// 부품 비교 — 전문가용.
//
// 같은 성능이면 같은 등급이다(등급은 index.json 의 문턱으로 계산한다). 그래서 기본 정렬은
// 등급 → 같은 등급 안에서 '성능 1점에 얼마'(원/지수)다. 같은 일을 하는 부품 중 무엇이 싸게
// 먹히는지가 바로 보인다. 체크한 부품은 아래에 나란히 놓고, 가장 좋은 값에 표시를 한다.

type SortKey = 'tier' | 'index' | 'price' | 'value' | 'name'

const confLabel: Record<Part['perf']['confidence'], string> = {
  seed: '검증 전',
  low: '추정',
  medium: '리뷰 평균',
  high: '공식·실측',
}

function valueOf(p: Part, data: HwData): number | null {
  const pr = priceOf(p, data.prices)
  return pr == null || !p.perf.index ? null : pr / p.perf.index
}

export function HardwareParts({ data, partId }: { data: HwData; partId: string | null }) {
  const part = partId ? data.parts.find((p) => p.id === partId) : null
  if (partId) return part ? <PartDetail data={data} part={part} /> : <div className="p-8 text-sm text-(--color-muted)">없는 부품입니다: {partId}</div>
  return <PartTable data={data} />
}

function PartTable({ data }: { data: HwData }) {
  const route = useRoute()
  const setQuery = useSetQuery()
  const cat = (route.query.get('cat') as Category) || 'gpu'
  const def = data.categories.find((c) => c.key === cat)
  useSeo({
    title: `${def?.name ?? ''} 등급·스펙 비교`,
    description: `${def?.name} — ${def?.why ?? ''} 같은 성능이면 같은 등급으로 묶고 성능 1점당 가격으로 줄 세웠습니다.`,
    canonical: absUrl(`${paths.hardwareParts()}?cat=${cat}`),
  })
  const [sort, setSort] = useState<SortKey>('tier')
  const [maker, setMaker] = useState('')
  const [picked, setPicked] = useState<string[]>([])

  const rows = useMemo(() => {
    const xs = data.parts
      .filter((p) => p.category === cat && (!maker || p.maker === maker))
      .map((p) => ({ p, tier: tierOf(p, data.categories), price: priceOf(p, data.prices), value: valueOf(p, data) }))
    const nul = (v: number | null, dir = 1) => (v == null ? Infinity : v * dir)
    xs.sort((a, b) => {
      switch (sort) {
        case 'index':
          return b.p.perf.index - a.p.perf.index
        case 'price':
          return nul(a.price) - nul(b.price)
        case 'value':
          return nul(a.value) - nul(b.value)
        case 'name':
          return a.p.name.localeCompare(b.p.name)
        default: // 등급 높은 순 → 같은 등급 안에서는 성능 1점이 싼 순
          return (b.tier?.min ?? 0) - (a.tier?.min ?? 0) || nul(a.value) - nul(b.value) || b.p.perf.index - a.p.perf.index
      }
    })
    return xs
  }, [data, cat, maker, sort])
  const makers = [...new Set(data.parts.filter((p) => p.category === cat).map((p) => p.maker))]
  const cols = SPEC_COLUMNS[cat]
  // 같은 등급 안에서 원/지수가 가장 낮은 부품 — '이 등급의 가성비'
  const bestInTier = new Map<string, string>()
  for (const r of rows) {
    if (!r.tier || r.value == null) continue
    const cur = bestInTier.get(r.tier.tier)
    const curV = cur ? valueOf(data.parts.find((p) => p.id === cur)!, data) : null
    if (curV == null || r.value < curV) bestInTier.set(r.tier.tier, r.p.id)
  }
  const toggle = (id: string) => setPicked((xs) => (xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id].slice(-4)))
  const th = (k: SortKey, label: string, cls = '') => (
    <th className={`font-normal px-2 py-2 whitespace-nowrap ${cls}`}>
      <button onClick={() => setSort(k)} className={sort === k ? 'text-(--color-accent) font-semibold' : 'hover:text-(--color-text)'}>
        {label}
        {sort === k && ' ↓'}
      </button>
    </th>
  )

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap gap-2">
        {CATEGORY_ORDER.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={c === cat}
            onClick={() => {
              setQuery('cat', c)
              setMaker('')
              setPicked([])
            }}
            className={
              'h-9 px-4 rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
              (c === cat ? 'border-(--color-accent) bg-(--color-accent) text-white' : 'border-[#d8d8d8] bg-white text-[#272727] hover:border-[#272727]')
            }
          >
            {data.categories.find((d) => d.key === c)?.name ?? c}
          </button>
        ))}
      </div>

      {def && (
        <>
          <p className="mt-4 text-base leading-6 tracking-[-0.16px] text-[#474747]">{def.why}</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-[repeat(var(--n),minmax(0,1fr))]" style={{ '--n': def.tiers.length } as React.CSSProperties}>
            {def.tiers.map((t) => (
              <div key={t.tier} className="rounded-[20px] border border-[#e2e8ec] bg-white px-[21px] pt-[19px] pb-4">
                <TierBadge tier={t.tier} size={32} />
                <div className="mt-2.5 text-[15px] font-bold leading-[21px] text-[#272727]">
                  {def.index_label} {t.min}+
                </div>
                <p className="mt-1 text-[13px] leading-[19px] text-[#666]">{t.plain}</p>
              </div>
            ))}
          </div>
        </>
      )}

      <TierLadder data={data} cat={cat} />
      {cat === 'cpu' && <TierLadder data={data} cat="cpu" measure="multi" />}

      <div className="mt-6 flex flex-col gap-4">
      {(cat === 'gpu' || cat === 'cpu') && <NameGuide data={data} cat={cat} />}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {makers.length > 1 && (
          <select value={maker} onChange={(e) => setMaker(e.target.value)} className="border border-(--color-border) rounded px-2 py-1 bg-(--color-panel)">
            <option value="">제조사 전체</option>
            {makers.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        )}
        <span className="text-xs text-(--color-muted)">체크하면 아래에 나란히 비교한다(최대 4개) · ★ 는 그 등급에서 성능 1점이 가장 싼 부품</span>
      </div>

      <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
              <th className="w-8" />
              {th('tier', '등급')}
              {th('name', '부품')}
              {th('index', def?.index_label ?? '지수', 'text-right')}
              {cat === 'cpu' && <th className="font-normal px-2 py-2 text-right">멀티</th>}
              {cols.map((c) => (
                <th key={c.key} className="font-normal px-2 py-2 whitespace-nowrap">
                  {c.label}
                </th>
              ))}
              {th('price', '가격', 'text-right')}
              {th('value', '원/지수', 'text-right')}
              <th className="font-normal px-2 py-2">흐름</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, tier, price, value }) => (
              <tr key={p.id} className={`border-t border-(--color-border-soft) ${picked.includes(p.id) ? 'bg-(--color-accent)/8' : 'hover:bg-(--color-band)'}`}>
                <td className="px-2 text-center">
                  <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} aria-label={`${p.name} 비교에 넣기`} className="accent-(--color-accent)" />
                </td>
                <td className="px-2 py-1.5">{tier && <TierBadge tier={tier.tier} />}</td>
                <td className="px-2 py-1.5 min-w-44">
                  <div className="flex items-center gap-2">
                  {p.image ? (
                    <OfficialImage image={p.image} alt="" className="w-10 h-10 rounded shrink-0" />
                  ) : null}
                  <div>
                  <a href={paths.hardwarePart(p.id)} onClick={onLinkClick(paths.hardwarePart(p.id))} className="font-medium hover:underline">
                    {p.name}
                  </a>
                  {bestInTier.get(tier?.tier ?? '') === p.id && <span className="ml-1 text-(--color-accent)" title="이 등급에서 성능 1점이 가장 싸다">★</span>}
                  <div className="text-[10px] text-(--color-faint)">
                    {p.maker}
                    {p.released && ` · ${p.released}`}
                    {p.perf.confidence === 'seed' && <span className="text-(--color-amber-400)"> · {confLabel.seed}</span>}
                  </div>
                  </div>
                  </div>
                </td>
                <td className="px-2 text-right font-bold tabular-nums">{p.perf.index}</td>
                {cat === 'cpu' && <td className="px-2 text-right tabular-nums">{p.perf.multi ?? '—'}</td>}
                {cols.map((c) => (
                  <td key={c.key} className="px-2 whitespace-nowrap tabular-nums text-(--color-muted)">
                    {fmtSpec(p.specs[c.key], c.unit)}
                  </td>
                ))}
                <td className="px-2 text-right font-semibold tabular-nums whitespace-nowrap" data-nosnippet>
                  {won(price)}
                </td>
                <td className="px-2 text-right tabular-nums text-(--color-muted) whitespace-nowrap" data-nosnippet>
                  {value == null ? '—' : `${Math.round(value).toLocaleString()}원`}
                </td>
                <td className="px-2 whitespace-nowrap" data-nosnippet>
                  <MoveBadge rec={data.prices[p.id]} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {picked.length >= 2 && <Compare data={data} ids={picked} cat={cat} />}
      </div>
    </div>
  )
}

function Compare({ data, ids, cat }: { data: HwData; ids: string[]; cat: Category }) {
  const ps = ids.map((id) => data.parts.find((p) => p.id === id)!).filter(Boolean)
  const cols = SPEC_COLUMNS[cat]
  // 숫자 칸은 가장 큰 값(전력·가격은 가장 작은 값)이 '좋은' 값이다
  const lowerBetter = new Set(['tdp_w', 'max_power_w', 'psu_w', 'latency_ns', 'cl', 'height_mm'])
  const best = (key: string) => {
    const vs = ps.map((p) => p.specs[key]).filter((v): v is number => typeof v === 'number')
    if (vs.length < 2) return null
    return lowerBetter.has(key) ? Math.min(...vs) : Math.max(...vs)
  }
  const prices = ps.map((p) => priceOf(p, data.prices))
  const minPrice = Math.min(...prices.filter((v): v is number => v != null))
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 overflow-x-auto">
      <h2 className="text-sm font-semibold mb-2">나란히 보기</h2>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th />
            {ps.map((p) => (
              <th key={p.id} className="text-left px-2 pb-2 font-semibold">
                {p.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-(--color-border-soft)">
            <td className="py-1.5 text-xs text-(--color-muted)">등급 · 지수</td>
            {ps.map((p) => (
              <td key={p.id} className="px-2">
                <span className="inline-flex items-center gap-1.5">
                  <TierBadge tier={tierOf(p, data.categories)?.tier ?? '-'} />
                  <b className={p.perf.index === Math.max(...ps.map((x) => x.perf.index)) ? 'text-(--color-accent)' : ''}>{p.perf.index}</b>
                </span>
              </td>
            ))}
          </tr>
          {cols.map((c) => {
            const b = best(c.key)
            return (
              <tr key={c.key} className="border-t border-(--color-border-soft)">
                <td className="py-1.5 text-xs text-(--color-muted) whitespace-nowrap">{c.label}</td>
                {ps.map((p) => (
                  <td key={p.id} className={`px-2 tabular-nums ${b != null && p.specs[c.key] === b ? 'text-(--color-accent) font-semibold' : ''}`}>
                    {fmtSpec(p.specs[c.key], c.unit)}
                  </td>
                ))}
              </tr>
            )
          })}
          <tr className="border-t border-(--color-border-soft)" data-nosnippet>
            <td className="py-1.5 text-xs text-(--color-muted)">가격</td>
            {ps.map((p, i) => (
              <td key={p.id} className={`px-2 tabular-nums ${prices[i] === minPrice ? 'text-(--color-accent) font-semibold' : ''}`}>
                {won(prices[i])}
              </td>
            ))}
          </tr>
          <tr className="border-t border-(--color-border-soft)" data-nosnippet>
            <td className="py-1.5 text-xs text-(--color-muted)">성능 1점에</td>
            {ps.map((p) => {
              const v = valueOf(p, data)
              return (
                <td key={p.id} className="px-2 tabular-nums">
                  {v == null ? '—' : `${Math.round(v).toLocaleString()}원`}
                </td>
              )
            })}
          </tr>
        </tbody>
      </table>
    </section>
  )
}

function PartDetail({ data, part }: { data: HwData; part: Part }) {
  // 상세에는 가격 이력과 매물이 실린다 — 색인하지 않는다(가격 DB 를 검색엔진에 다시 싣지 않는다).
  useSeo({ title: `${part.name} 스펙·가격`, description: `${part.name} 등급과 스펙, 가격 추이`, robots: NOINDEX, canonical: absUrl(paths.hardwarePart(part.id)) })
  const def = data.categories.find((c) => c.key === part.category)
  const tier = tierOf(part, data.categories)
  const rec = data.prices[part.id]
  // 등급 안에서 성능 1점이 몇 번째로 싼가 — 값을 아는 부품끼리
  const ranked = data.parts
    .filter((p) => p.category === part.category && tierOf(p, data.categories)?.tier === tier?.tier)
    .map((p) => ({ id: p.id, v: valueOf(p, data) }))
    .filter((x): x is { id: string; v: number } => x.v != null)
    .sort((a, b) => a.v - b.v)
  const rank = ranked.findIndex((x) => x.id === part.id)
  const tone = TIER_COLOR[tier?.tier ?? ''] ?? '#9aa1a8'
  const listTo = `${paths.hardwareParts()}?cat=${part.category}`
  return (
    <div className="flex flex-col">
      <nav aria-label="경로" className="text-sm text-[#777]">
        <a href={paths.hardware()} onClick={onLinkClick(paths.hardware())} className="hover:text-[#272727]">
          PC 하드웨어
        </a>
        {' › '}
        <a
          href={listTo}
          onClick={(e) => {
            e.preventDefault()
            navigate(listTo)
          }}
          className="hover:text-[#272727]"
        >
          부품 비교
        </a>
        {` › ${def?.name ?? ''}`}
      </nav>

      <header className="mt-5 flex flex-col lg:flex-row lg:items-center gap-6 rounded-[30px] bg-[#f7f9fa] px-[34px] py-[30px]">
        <div className="flex items-center gap-[26px] min-w-0 flex-1">
          {tier ? (
            <span className="shrink-0 grid place-items-center w-[84px] h-[84px] rounded-[22px] text-[42px] font-bold text-white" style={{ background: tone }}>
              {tier.tier}
            </span>
          ) : null}
          <div className="min-w-0">
            <h1 className="text-[32px] font-bold leading-[47px] tracking-[-0.6px] text-[#272727]">{part.name}</h1>
            <div className="text-sm text-[#888]">
              {part.maker}
              {part.released && ` · ${part.released} 출시`}
            </div>
            {tier && (
              <p className="mt-2 text-[17px] font-medium leading-[25px]" style={{ color: tone }}>
                {tier.tier} 등급 — {tier.plain}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2.5 shrink-0">
          {[
            ['성능 지수', String(part.perf.index)],
            ['등급 내 가성비', rank >= 0 ? `${ranked.length}개 중 ${rank + 1}위` : '—'],
            ['최저가', won(priceOf(part, data.prices))],
          ].map(([k, v]) => (
            <div key={k} className="w-[140px] h-[87px] rounded-2xl bg-white px-5 pt-4" data-nosnippet={k === '최저가' || undefined}>
              <div className="text-[13px] text-[#777]">{k}</div>
              <div className="mt-1 text-[22px] font-bold leading-8 text-[#272727] tabular-nums">{v}</div>
            </div>
          ))}
        </div>
      </header>

      <div className="mt-[49px] flex flex-col lg:flex-row gap-7 items-start">
        <div className="w-full lg:flex-1 min-w-0">
          {part.category === 'gpu' || part.category === 'cpu' || part.category === 'case' ? (
            <PopularPick data={data} part={part} />
          ) : null}
        </div>
        <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4">
          <SameTierCard data={data} part={part} />
        </aside>
      </div>

      <div className="mt-10 flex flex-col gap-4">
      {part.category === 'gpu' && (
        <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 empty:hidden">
          <FieldNotes gpus={[part.id]} limit={4} title={`${part.name.replace('GeForce ', '').replace('Radeon ', '')} 를 AI 에 쓰는 사람들 이야기`} />
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold mb-2">스펙</h2>
          <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-y-1 text-sm">
            <dt className="text-(--color-muted)">{def?.index_label}</dt>
            <dd className="font-bold">
              {part.perf.index}
              {part.perf.multi != null && <span className="font-normal text-(--color-muted)"> · 멀티 {part.perf.multi}</span>}
            </dd>
            {SPEC_COLUMNS[part.category].map((c) => (
              <div key={c.key} className="contents">
                <dt className="text-(--color-muted)">{c.label}</dt>
                <dd className="tabular-nums">{fmtSpec(part.specs[c.key], c.unit)}</dd>
              </div>
            ))}
          </dl>
          <p className="text-[11px] text-(--color-faint) mt-3">
            지수 기준: {part.perf.basis} · 신뢰도 <b>{confLabel[part.perf.confidence]}</b> · 확인 {part.checked_at}
          </p>
          <ul className="text-[11px] mt-1 flex flex-col gap-0.5">
            {part.sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2" data-nosnippet>
          <div className="flex items-baseline gap-2">
            <h2 className="text-sm font-semibold">가격</h2>
            <span className="text-lg font-bold tabular-nums">{won(priceOf(part, data.prices))}</span>
            <span className="ml-auto">
              <MoveBadge rec={rec} />
            </span>
          </div>
          <PriceChart history={rec?.history ?? []} />
        </section>
      </div>
      {(part.category === 'gpu' || part.category === 'cpu') && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 grid gap-6 lg:grid-cols-2">
          {part.category === 'gpu' ? <GameCompare data={data} part={part} /> : <PerfLadder data={data} cat="cpu" highlight={part.id} measure="multi" />}
          <PerfLadder data={data} cat={part.category} highlight={part.id} />
        </section>
      )}
      {part.category === 'gpu' && (data.bench.vendor ?? []).some((v) => v.gpu === part.id) && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <VendorBench data={data} part={part} />
        </section>
      )}
      <DurabilityNotes part={part} />
      {part.category === 'cpu' ? <SaleForms data={data} part={part} /> : <ModelTable data={data} part={part} />}
      </div>
    </div>
  )
}

// ── 성능 사다리 카드(Penpot 28) ─────────────────────────────────────────
// 줄마다 등급 · 이름 · 등급 색 막대(안에 지수) · 오늘 최저가 · 가격 꼬리표 · 상세로. 처음엔 12줄,
// 아래 검은 단추로 전부 편다. 단품 판매가 끝난 칩은 매물이 남은 중고·오매칭 값이라 '가격 확인 필요'.
const LADDER_FIRST = 12

function TierLadder({ data, cat, measure = 'index' }: { data: HwData; cat: Category; measure?: 'index' | 'multi' }) {
  const [all, setAll] = useState(false)
  const def = data.categories.find((c) => c.key === cat)
  const rows = data.parts
    .filter((p) => p.category === cat && (measure === 'index' || p.perf.multi != null))
    .map((p) => ({ p, v: measure === 'multi' ? (p.perf.multi ?? 0) : p.perf.index, t: tierOf(p, data.categories)?.tier, price: priceOf(p, data.prices) }))
    .sort((a, b) => b.v - a.v)
  if (rows.length === 0) return null
  const max = Math.max(...rows.map((r) => r.v), 1)
  const shown = all ? rows : rows.slice(0, LADDER_FIRST)
  const label = measure === 'multi' ? '멀티 지수' : def?.index_label
  return (
    <section className="mt-6 rounded-[30px] border border-[#e2e8ec] bg-white px-[31px] pt-[26px] pb-[29px]">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="text-[20px] font-bold leading-[29px] tracking-[-0.2px] text-[#272727]">
          성능 사다리 — {def?.name} {label}
        </h2>
        <span className="ml-auto text-[13px] text-[#999]">{measure === 'multi' ? '9950X = 100 · 멀티스레드 상대 성능' : def?.index_basis}</span>
      </div>
      <ol className="mt-3.5">
        {shown.map(({ p, v, t, price }) => {
          const to = paths.hardwarePart(p.id)
          const check = priceSuspect(p, price)
          return (
            <li key={p.id} className="border-b border-[#f1f3f5]">
              <a href={to} onClick={onLinkClick(to)} className="group flex items-center h-[51px] hover:bg-[#fafbfc]">
                {t ? <TierBadge tier={t} size={26} /> : <span className="w-[26px] shrink-0" />}
                <span className="ml-3.5 w-[184px] shrink-0 truncate text-base font-bold text-[#272727] group-hover:underline underline-offset-2">
                  {p.name.replace('GeForce ', '').replace('Radeon ', '')}
                </span>
                <span className="relative flex-1 min-w-0 h-[22px] rounded-md bg-[#f4f5f7]">
                  <span
                    className="absolute inset-y-0 left-0 flex items-center rounded-md pl-2.5 text-[13px] font-bold text-white tabular-nums"
                    style={{ width: `${Math.max((v / max) * 100, 4)}%`, background: TIER_COLOR[t ?? ''] ?? '#9aa1a8' }}
                  >
                    {v}
                  </span>
                </span>
                <span className="w-[115px] shrink-0 text-right text-base font-bold text-[#272727] tabular-nums" data-nosnippet>
                  {won(price)}
                </span>
                <span
                  className={
                    'ml-[13px] w-[100px] shrink-0 rounded text-center text-[13px] leading-[22px] tracking-[-0.13px] ' +
                    (check ? 'bg-[#f67979] text-white' : 'bg-[#f4f4f4] text-[#474747]')
                  }
                  data-nosnippet
                >
                  {check ? '가격 확인 필요' : '최저가'}
                </span>
                <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#bbb" strokeWidth="1.5" strokeLinecap="round" aria-hidden className="ml-3.5 shrink-0">
                  <path d="M2.5 1.5 6 5l-3.5 3.5" />
                </svg>
              </a>
            </li>
          )
        })}
      </ol>
      {rows.length > LADDER_FIRST && (
        <button
          type="button"
          onClick={() => setAll((x) => !x)}
          aria-expanded={all}
          className="mt-[22px] w-full h-11 rounded-[22px] bg-[#272727] text-base font-medium text-white hover:bg-black inline-flex items-center justify-center gap-2"
        >
          {all ? '접기' : `${def?.name} 전체 보기 (${rows.length}종)`}
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden className={all ? 'rotate-180' : ''}>
            <path d="M1 1l4 4 4-4" />
          </svg>
        </button>
      )}
    </section>
  )
}
