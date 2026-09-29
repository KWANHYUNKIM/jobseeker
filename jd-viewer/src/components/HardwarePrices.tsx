import { useMemo, useState } from 'react'
import { CATEGORY_ORDER, priceMove, priceOf, tierOf, won, type Category, type HwData, type PricePoint, type PriceRec } from '../lib/hardware'
import { onLinkClick } from '../lib/router'
import { absUrl, useSeo } from '../lib/seo'
import { paths } from '../lib/urls'
import { TierBadge } from './HardwareView'

// 가격 추이 — 오르내림을 알 만큼.
//
// 다나와의 가격 차트는 robots 가 막고 있어서(/info/ajax/) 받아 오지 않는다. 여기 선은 전부
// crawl_hardware 가 매일 찍어 쌓은 값이고, 그래서 **기록을 시작한 날부터만** 있다.
// '지금 사도 되나'는 지난 30일 최저가의 가운데 값과 오늘을 견준 것이다 — 30일이 안 찼으면
// 있는 날만으로 세고, 며칠로 셌는지를 같이 적는다.
//
// 이 화면은 색인하지 않는다 — 다나와 가격을 검색엔진에 다시 싣지 않기로 했다.

export const NOINDEX = 'noindex, follow'

export function PriceChart({ history, height = 180 }: { history: PricePoint[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null)
  if (!history.length) return <div className="text-sm text-(--color-muted)">아직 가격 기록이 없다.</div>
  const W = 720
  const H = height
  const pad = { l: 62, r: 16, t: 12, b: 24 }
  const vals = history.flatMap((h) => [h.min, h.median])
  const lo = Math.min(...vals) * 0.97
  const hi = Math.max(...vals) * 1.03
  const x = (i: number) => (history.length === 1 ? (pad.l + W - pad.r) / 2 : pad.l + (i * (W - pad.l - pad.r)) / (history.length - 1))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (v - lo) / (hi - lo || 1))
  const ticks = [lo, (lo + hi) / 2, hi]
  const every = Math.max(1, Math.ceil(history.length / 7))
  const hp = hover != null ? history[hover] : null
  const line = (k: 'min' | 'median') => history.map((h, i) => `${x(i)},${y(h[k])}`).join(' ')
  return (
    <div className="relative" data-nosnippet>
      <div className="flex gap-3 text-[11px] text-(--color-muted) mb-1">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-(--color-accent)" />
          최저가
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 border-t border-dashed border-(--color-muted)" />
          매물 가운데 값
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        role="img"
        aria-label="일별 가격 추이"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          const px = ((e.clientX - r.left) / r.width) * W
          let best = 0
          history.forEach((_, i) => {
            if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i
          })
          setHover(best)
        }}
      >
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--color-border-soft)" />
            <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="var(--color-muted)">
              {won(Math.round(t))}
            </text>
          </g>
        ))}
        {history.map((h, i) =>
          i % every === 0 || i === history.length - 1 ? (
            <text key={h.d} x={x(i)} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--color-muted)">
              {h.d.slice(5)}
            </text>
          ) : null,
        )}
        {history.length > 1 && (
          <>
            <polyline points={line('median')} fill="none" stroke="var(--color-muted)" strokeDasharray="4 3" strokeWidth={1.2} />
            <polyline points={line('min')} fill="none" stroke="var(--color-accent)" strokeWidth={2} strokeLinejoin="round" />
          </>
        )}
        {history.map((h, i) => (
          <circle key={h.d} cx={x(i)} cy={y(h.min)} r={history.length > 40 ? 2 : 3.5} fill="var(--color-accent)" stroke="var(--color-panel)" strokeWidth={1.5} />
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} stroke="var(--color-muted)" strokeDasharray="3 3" />}
      </svg>
      {hp && (
        <div className="absolute top-6 right-2 rounded-md border border-(--color-border) bg-(--color-panel) px-2 py-1 text-xs shadow-sm tabular-nums">
          <div className="font-semibold">{hp.d}</div>
          <div>최저 {hp.min.toLocaleString()}원</div>
          <div className="text-(--color-muted)">
            가운데 {hp.median.toLocaleString()}원 · 매물 {hp.n}
          </div>
        </div>
      )}
      {history.length === 1 && <div className="text-[11px] text-(--color-faint) mt-1">{history[0].d} 부터 기록 중 — 선은 이틀째부터 그려진다.</div>}
    </div>
  )
}

function Spark({ rec }: { rec?: PriceRec }) {
  const h = rec?.history ?? []
  if (h.length < 2) return <span className="text-[10px] text-(--color-faint)">기록 {h.length}일</span>
  const W = 90
  const H = 24
  const vs = h.map((p) => p.min)
  const lo = Math.min(...vs)
  const hi = Math.max(...vs)
  const pts = vs.map((v, i) => `${(i / (vs.length - 1)) * W},${H - 2 - ((v - lo) / (hi - lo || 1)) * (H - 4)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden>
      <polyline points={pts} fill="none" stroke="var(--color-accent)" strokeWidth={1.5} />
    </svg>
  )
}

export function MoveBadge({ rec }: { rec?: PriceRec }) {
  const m = priceMove(rec)
  if (!m || m.days < 3) return <span className="text-[11px] text-(--color-faint)">판단 이르다</span>
  const pct = Math.round(m.pct * 10) / 10
  const [word, cls] =
    pct <= -3 ? ['싸다', 'text-(--color-accent) font-semibold'] : pct >= 3 ? ['비싸다', 'text-(--color-red-400) font-semibold'] : ['평소', 'text-(--color-muted)']
  return (
    <span className={`text-xs ${cls}`} title={`지난 ${m.days}일 최저가 가운데 값 대비 · 범위 ${won(m.low)} ~ ${won(m.high)}`}>
      {word} {pct > 0 ? '+' : ''}
      {pct}%
    </span>
  )
}

export function HardwarePrices({ data }: { data: HwData }) {
  useSeo({ title: 'PC 부품 가격 추이', description: '부품별 다나와 최저가를 매일 기록한 추이.', robots: NOINDEX, canonical: absUrl(paths.hardwarePrices()) })
  const [cat, setCat] = useState<Category>('gpu')
  const rows = useMemo(
    () =>
      data.parts
        .filter((p) => p.category === cat)
        .map((p) => ({ p, price: priceOf(p, data.prices), rec: data.prices[p.id], tier: tierOf(p, data.categories) }))
        .sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity)),
    [data, cat],
  )
  const days = new Set(Object.values(data.prices).flatMap((r) => r.history.map((h) => h.d))).size
  return (
    <div className="max-w-[1200px] mx-auto p-4 flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-lg font-bold">PC 부품 가격 추이</h1>
        <span className="text-xs text-(--color-muted)">
          다나와 최저가를 하루 한 번 찍어 쌓는다 · 기록 {days}일 · 중고·병행수입·해외구매는 뺐다
        </span>
      </header>
      <div className="flex flex-wrap gap-1">
        {CATEGORY_ORDER.map((c) => (
          <button
            key={c}
            onClick={() => setCat(c)}
            className={`px-2.5 py-1 rounded-md text-sm ${c === cat ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'bg-(--color-band) hover:bg-(--color-border-soft)'}`}
          >
            {data.categories.find((d) => d.key === c)?.name ?? c}
          </button>
        ))}
      </div>
      <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]" data-nosnippet>
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
              <th className="font-normal px-3 py-2">부품</th>
              <th className="font-normal px-3 py-2 text-right">오늘</th>
              <th className="font-normal px-3 py-2">지난 30일 대비</th>
              <th className="font-normal px-3 py-2">흐름</th>
              <th className="font-normal px-3 py-2 text-right">매물</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, price, rec, tier }) => (
              <tr key={p.id} className="border-t border-(--color-border-soft) hover:bg-(--color-band)">
                <td className="px-3 py-2">
                  <a href={paths.hardwarePart(p.id)} onClick={onLinkClick(paths.hardwarePart(p.id))} className="flex items-center gap-2 hover:underline">
                    {tier && <TierBadge tier={tier.tier} />}
                    <span className="font-medium">{p.name}</span>
                  </a>
                </td>
                <td className="px-3 py-2 text-right font-bold tabular-nums">
                  {won(price)}
                  {p.price_basis === 'median' && <div className="text-[10px] font-normal text-(--color-faint)">급 가운데 값</div>}
                </td>
                <td className="px-3 py-2">
                  <MoveBadge rec={rec} />
                </td>
                <td className="px-3 py-2">
                  <Spark rec={rec} />
                </td>
                <td className="px-3 py-2 text-right text-(--color-muted) tabular-nums">{rec?.n ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-(--color-faint)">
        가격은 다나와 통합검색에 잡힌 매물 중 부품 조건에 맞는 것의 최저가다. 급(쿨러·케이스)은 한 상품이 아니라 그 급 매물의 가운데 값이다. 상세에서 매물을 누르면 다나와 원문으로 간다.
      </p>
    </div>
  )
}
