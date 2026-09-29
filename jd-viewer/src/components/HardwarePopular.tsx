import {
  caseFans,
  fanLayout,
  namesIn,
  pickOf,
  priceOf,
  shopLinks,
  useGuide,
  useModels,
  variantsOf,
  whyPopular,
  won,
  type Category,
  type Guide,
  type HwData,
  type NameNote,
  type Part,
  type Variant,
} from '../lib/hardware'
import { onLinkClick } from '../lib/router'
import { paths } from '../lib/urls'
import { ShopLink } from './HardwareBuy'

// 같은 칩의 여러 제품 — "RTX 5060 은 종류가 엄청 많은데 뭘 사나".
//
//  VariantList  사다리에서 칩 한 줄을 펼치면 나오는 제품 목록. 인기순(다나와 인기상품순)으로
//               세우고, 제품마다 성능 지수(클럭 비례 추정)·최저가·판매처 링크를 단다.
//  PopularPick  부품 상세의 '대표 제품' — 가장 많이 팔리는 것 하나와 왜 그런지.
//  NameGuide    이름 읽는 법 — Ti·SUPER·XT·X3D·F·K 와 OC·2X·LP. 차이는 우리 목록의 숫자로 보인다.

function ShopLinks({ v, guide }: { v: Variant; guide: Guide | null }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[11px]">
      {shopLinks(v, guide).map((l) => (
        <ShopLink key={l.label} shop={l.label} url={l.url} strong={l.label === '다나와'} />
      ))}
    </span>
  )
}

function useVariants(data: HwData, part: Part) {
  const models = useModels(part.id)
  const guide = useGuide()
  const vs = models == null ? null : variantsOf(part, data.prices[part.id], models, guide)
  return { vs, guide }
}

const perfCell = (v: Variant, part: Part) => {
  // 케이스는 성능 지수가 아니라 기본 팬 배치로 견준다
  if (part.category === 'case') return <span>{v.model ? fanLayout(caseFans(v.model.specs).included) : '—'}</span>
  if (v.index == null) return <span className="text-(--color-faint)">{part.perf.index} (칩)</span>
  if (v.clockPct == null) return <span>{v.index}</span>
  const d = v.clockPct
  return (
    <span title="칩 지수 × 이 제품의 부스트 클럭 ÷ 기준 클럭 — 게임 성능은 클럭만큼 늘지 않으니 상한이다">
      {v.index}
      <span className={`ml-1 text-[10px] ${d > 0 ? 'text-(--color-accent)' : 'text-(--color-muted)'}`}>
        {d >= 0 ? '+' : ''}
        {d.toFixed(1)}%
      </span>
    </span>
  )
}

export function VariantList({ data, part, limit = 8 }: { data: HwData; part: Part; limit?: number }) {
  const { vs, guide } = useVariants(data, part)
  if (vs == null) return <div className="text-xs text-(--color-muted) py-2">불러오는 중…</div>
  if (!vs.length) return <div className="text-xs text-(--color-muted) py-2">오늘 받은 매물이 없다.</div>
  const pick = pickOf(vs)
  const shown = vs.slice(0, limit)
  return (
    <div className="flex flex-col gap-1">
      <table className="w-full text-xs" data-nosnippet>
        <thead>
          <tr className="text-[10px] text-(--color-muted) text-left">
            <th className="font-normal px-1 w-10">{vs[0].pop != null ? '인기' : '순서'}</th>
            <th className="font-normal px-1">제품</th>
            <th className="font-normal px-1 text-right whitespace-nowrap">{part.category === 'case' ? '기본 팬' : '성능 지수'}</th>
            <th className="font-normal px-1 text-right">최저가</th>
            <th className="font-normal px-1">사는 곳</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((v) => (
            <tr key={v.key} className={`border-t border-(--color-border-soft) ${v === pick ? 'bg-(--color-accent)/8' : ''}`}>
              <td className="px-1 py-1 tabular-nums text-(--color-muted)">{v.pop ?? '—'}</td>
              <td className="px-1 py-1">
                <span className={v === pick ? 'font-semibold' : ''}>{v.name}</span>
                {v === pick && <span className="ml-1 text-[10px] px-1 rounded bg-(--color-accent) text-(--color-on-accent)">대표</span>}
                {v.form && <span className="ml-1 text-[10px] text-(--color-muted)">{v.form.label}</span>}
                {v.distributor && <span className="ml-1 text-[10px] text-(--color-faint)">{v.distributor.name}</span>}
              </td>
              <td className="px-1 py-1 text-right tabular-nums">{perfCell(v, part)}</td>
              <td className="px-1 py-1 text-right tabular-nums">{won(v.price)}</td>
              <td className="px-1 py-1">
                <ShopLinks v={v} guide={guide} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-(--color-faint)">
        {vs.length > limit && `${vs.length}종 중 ${limit}종 · `}
        {part.category === 'case'
          ? '같은 급이라도 크기·기본 팬·흡기면이 제품마다 다르다. 스펙을 아직 조사 안 한 제품은 기본 팬 칸이 비어 있다 — 아래 제품별 스펙에서 펼쳐 본다.'
          : part.category === 'gpu'
          ? '성능 지수는 칩 지수를 제품 부스트 클럭으로 옮긴 추정(상한)이다. 제품 사양을 아직 조사 안 한 것은 칩 지수만 적었다 — 같은 칩이면 차이는 대개 1~2% 안이다.'
          : '같은 칩이라 성능은 같다. 차이는 판매 형태(정품·멀티팩·벌크)와 보증이다.'}
        {' '}네이버쇼핑·쿠팡은 같은 이름의 검색 결과로 이어진다.
      </p>
    </div>
  )
}

export function PopularPick({ data, part }: { data: HwData; part: Part }) {
  const { vs, guide } = useVariants(data, part)
  if (!vs?.length) return null
  const pick = pickOf(vs)
  if (!pick) return null
  const why = whyPopular(pick, vs, part, data)
  const names = [
    ...namesIn(part.name, guide?.names ?? [], [part.category === 'cpu' ? 'cpu' : 'gpu']),
    ...(part.category === 'gpu' ? namesIn(pick.name, guide?.names ?? [], ['product']) : []),
  ]
  return (
    <section className="rounded-lg border border-(--color-accent)/40 bg-(--color-panel) p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-semibold">가장 많이 쓰는 {part.name}</h2>
        <span className="text-xs text-(--color-muted)">{data.prices[part.id]?.day ?? ''} 다나와 인기상품순 기준 · 그날 검색에 걸린 제품 {vs.length}종</span>
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-lg font-bold">{pick.name}</span>
        <span className="text-base font-semibold tabular-nums" data-nosnippet>
          {won(pick.price)}
        </span>
        <span className="text-xs text-(--color-muted)">
          {part.category === 'case' ? '기본 팬' : '성능 지수'} {perfCell(pick, part)}
        </span>
        <ShopLinks v={pick} guide={guide} />
      </div>
      <div>
        <div className="text-xs font-semibold text-(--color-muted) mb-1">왜 많이 쓰나</div>
        <ul className="text-sm flex flex-col gap-0.5 list-disc pl-5">
          {why.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </div>
      {names.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-(--color-muted) mb-1">이름에 붙은 말</div>
          <NameCards data={data} notes={names} />
        </div>
      )}
      <div>
        <div className="text-xs font-semibold text-(--color-muted) mb-1">{part.category === 'case' ? '같은 급의 다른 제품' : '같은 칩의 다른 제품'}</div>
        <VariantList data={data} part={part} limit={12} />
      </div>
    </section>
  )
}

// ── 이름 읽는 법 ─────────────────────────────────────────────────────

const DIFF_KEYS: Record<string, { key: string; label: string; unit?: string }[]> = {
  gpu: [
    { key: 'cores', label: '코어' },
    { key: 'vram_gb', label: 'VRAM', unit: 'GB' },
  ],
  cpu: [
    { key: 'cores', label: '코어' },
    { key: 'l3_mb', label: 'L3', unit: 'MB' },
    { key: 'igpu', label: '내장 그래픽' },
  ],
}

function Compare({ data, ids }: { data: HwData; ids: string[] }) {
  const ps = ids.map((id) => data.parts.find((p) => p.id === id)).filter((p): p is Part => !!p)
  if (!ps.length) return null
  const keys = DIFF_KEYS[ps[0].category] ?? []
  const fmt = (v: unknown, unit?: string) => (v == null ? '—' : typeof v === 'boolean' ? (v ? '있음' : '없음') : `${v}${unit ?? ''}`)
  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {ps.map((p) => (
        <a
          key={p.id}
          href={paths.hardwarePart(p.id)}
          onClick={onLinkClick(paths.hardwarePart(p.id))}
          className="rounded bg-(--color-band) px-2 py-1 text-[11px] tabular-nums hover:bg-(--color-border-soft)"
        >
          <b>{p.name.replace('GeForce ', '').replace('Radeon ', '')}</b> 지수 {p.perf.index}
          {keys.map((k) => ` · ${k.label} ${fmt(p.specs[k.key], k.unit)}`).join('')}
          <span className="text-(--color-muted)" data-nosnippet>
            {' '}
            · {won(priceOf(p, data.prices))}
          </span>
        </a>
      ))}
    </div>
  )
}

function NameCards({ data, notes }: { data: HwData; notes: NameNote[] }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {notes.map((n) => (
        <div key={n.key} className="rounded-md border border-(--color-border-soft) p-2 text-sm">
          <div className="flex items-baseline gap-2">
            <code className="text-xs font-bold px-1.5 rounded bg-(--color-band)">{n.token}</code>
            <span className="font-semibold text-xs">{n.title}</span>
          </div>
          <p className="text-xs text-(--color-muted) mt-1">{n.plain}</p>
          {n.compare && n.compare.length > 0 && <Compare data={data} ids={n.compare} />}
          <div className="text-[10px] mt-1 flex flex-wrap gap-x-2">
            {n.sources.map((s) => (
              <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-faint) hover:underline">
                {s.title}
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function NameGuide({ data, cat }: { data: HwData; cat: Category }) {
  const guide = useGuide()
  const all = guide?.names ?? []
  const chip = all.filter((n) => n.applies === cat)
  const product = cat === 'gpu' ? all.filter((n) => n.applies === 'product') : []
  if (!chip.length && !product.length) return null
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold">이름 읽는 법</h2>
        <p className="text-xs text-(--color-muted)">
          {cat === 'gpu'
            ? '칩 이름(Ti·SUPER·XT)은 성능이 다르고, 제품 이름(OC·2X·LP·WHITE)은 같은 칩의 만듦새가 다르다. 누르면 그 부품으로 간다.'
            : '같은 숫자라도 뒤에 붙은 글자에 따라 캐시·클럭·내장 그래픽이 다르다. 누르면 그 부품으로 간다.'}
        </p>
      </div>
      {chip.length > 0 && <NameCards data={data} notes={chip} />}
      {product.length > 0 && (
        <>
          <div className="text-xs font-semibold text-(--color-muted)">제품 이름 — 같은 칩, 다른 만듦새</div>
          <NameCards data={data} notes={product} />
        </>
      )}
    </section>
  )
}
