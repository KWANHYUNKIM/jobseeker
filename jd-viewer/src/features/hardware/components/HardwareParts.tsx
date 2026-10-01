import { useMemo, useState } from 'react'
import { CATEGORY_ORDER, SPEC_COLUMNS, fmtSpec, priceOf, tierOf, won, type Category, type HwData, type Part } from '../utils/hardware'
import { navigate, onLinkClick, useRoute, useSetQuery } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths, TAB_SEO } from '../../../utils/urls'
import { MoveBadge, NOINDEX, PriceChart } from './HardwarePrices'
import { GameCompare, PerfLadder, VendorBench } from './HardwareCharts'
import { OfficialImage } from './OfficialImage'
import { DurabilityNotes, ModelTable, SaleForms } from './HardwareModels'
import { TierBadge } from './HardwareView'
import { NameGuide, PopularPick } from './HardwarePopular'
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
    <div className="max-w-[1600px] mx-auto p-4 flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-lg font-bold">부품 비교</h1>
        <span className="text-xs text-(--color-muted)">{TAB_SEO.hardwareParts.desc}</span>
      </header>
      <div className="flex flex-wrap gap-1">
        {CATEGORY_ORDER.map((c) => (
          <button
            key={c}
            onClick={() => {
              setQuery('cat', c)
              setMaker('')
              setPicked([])
            }}
            className={`px-2.5 py-1 rounded-md text-sm ${c === cat ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'bg-(--color-band) hover:bg-(--color-border-soft)'}`}
          >
            {data.categories.find((d) => d.key === c)?.name ?? c}
          </button>
        ))}
      </div>

      {def && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
          <p className="text-sm">{def.why}</p>
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {def.tiers.map((t) => (
              <div key={t.tier} className="flex items-start gap-2 text-xs">
                <TierBadge tier={t.tier} />
                <div>
                  <span className="text-(--color-muted)">
                    {def.index_label} {t.min}+{' '}
                  </span>
                  {t.plain}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-(--color-faint)">
            {def.index_label}: {def.index_basis}
          </p>
        </section>
      )}

      {(cat === 'gpu' || cat === 'cpu') && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 grid gap-6 lg:grid-cols-2">
          <PerfLadder data={data} cat={cat} />
          {cat === 'cpu' ? <PerfLadder data={data} cat="cpu" measure="multi" /> : <LadderHelp />}
        </section>
      )}
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
  const peers = data.parts
    .filter((p) => p.category === part.category && p.id !== part.id && tierOf(p, data.categories)?.tier === tier?.tier)
    .map((p) => ({ p, price: priceOf(p, data.prices) }))
  return (
    <div className="max-w-[1500px] mx-auto p-4 flex flex-col gap-4">
      <a
        href={`${paths.hardwareParts()}?cat=${part.category}`}
        onClick={(e) => {
          e.preventDefault()
          navigate(`${paths.hardwareParts()}?cat=${part.category}`)
        }}
        className="text-xs text-(--color-accent) hover:underline"
      >
        ← {def?.name} 비교로
      </a>
      <header className="flex flex-wrap items-center gap-3">
        {part.image && (
          <a href={part.image.page} target="_blank" rel="noreferrer" title={`사진: ${part.image.credit} 공식 페이지`}>
            <OfficialImage image={part.image} alt={part.name} className="w-28 h-20 rounded border border-(--color-border-soft)" />
          </a>
        )}
        {tier && <TierBadge tier={tier.tier} />}
        <h1 className="text-xl font-bold">{part.name}</h1>
        <span className="text-sm text-(--color-muted)">
          {part.maker}
          {part.released && ` · ${part.released} 출시`}
        </span>
      </header>
      {tier && (
        <p className="text-sm">
          <b>{tier.tier} 등급</b> — {tier.plain}
        </p>
      )}
      {(part.category === 'gpu' || part.category === 'cpu' || part.category === 'case') && <PopularPick data={data} part={part} />}
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
      {peers.length > 0 && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold mb-2">같은 {tier?.tier} 등급</h2>
          <div className="flex flex-wrap gap-2">
            {peers.map(({ p, price }) => (
              <a key={p.id} href={paths.hardwarePart(p.id)} onClick={onLinkClick(paths.hardwarePart(p.id))} className="px-2.5 py-1.5 rounded-md bg-(--color-band) text-sm hover:bg-(--color-border-soft)">
                {p.name} <span className="text-xs text-(--color-muted)">지수 {p.perf.index} · {won(price)}</span>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function LadderHelp() {
  return (
    <div className="text-sm text-(--color-muted) flex flex-col gap-2 justify-center">
      <p>
        <b className="text-(--color-text)">읽는 법</b> — 막대 길이가 성능 지수다. RTX 4090 을 100 으로 두고 QHD 게임에서 몇 % 나오나를 잰 값이라, 50 이면
        4090 의 절반쯤 프레임이 나온다.
      </p>
      <p>막대 색이 진할수록 높은 등급이다. 오른쪽 숫자는 오늘 최저가 — 막대가 비슷한데 값이 크게 다르면 싼 쪽이 가성비다.</p>
      <p>막대를 누르면 그 카드의 게임별 예상 fps·제조사 공개 측정·제품별 사진과 스펙으로 간다.</p>
      <p>
        줄 끝의 <b className="text-(--color-text)">▾</b> 를 누르면 같은 칩을 얹은 제품들(MSI·GALAX·ZOTAC…)이 다나와 인기순으로 펼쳐진다 — 제품마다
        성능 지수와 최저가, 다나와·네이버쇼핑·쿠팡 링크가 붙는다. 맨 위 '대표' 가 가장 많이 팔리는 제품이다.
      </p>
    </div>
  )
}
