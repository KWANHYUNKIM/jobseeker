import { useMemo, useState } from 'react'
import { CATEGORY_ORDER, priceMove, priceOf, priceSuspect, tierOf, usedPrice, won, type Category, type HwData, type PricePoint, type PriceRec } from '../utils/hardware'
import { onLinkClick } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
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
  if (h.length < 2)
    return (
      <span className="inline-flex items-center text-[11.7px] text-[#999]">
        <span className="inline-block w-20 h-0.5 bg-[#ddd]" aria-hidden />
        기록 {h.length}일
      </span>
    )
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
  if (!m || m.days < 3) return <span className="text-sm text-[#999]">판단 이르다</span>
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

/** 가격 원장에 쌓인 날 수 — 모든 부품의 기록 날짜를 합친 것 */
export function priceDays(data: HwData): number {
  return new Set(Object.values(data.prices).flatMap((r) => r.history.map((h) => h.d))).size
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
  const days = priceDays(data)
  const suspects = rows.filter((r) => priceSuspect(r.p, r.price)).length
  const th = 'bg-[#fafafa] px-3 h-12 text-left text-sm font-bold text-[#272727] border-b border-[#e2e2e2]'
  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap gap-2">
        {CATEGORY_ORDER.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={c === cat}
            onClick={() => setCat(c)}
            className={
              'h-9 px-4 rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
              (c === cat ? 'border-(--color-accent) bg-(--color-accent) text-white' : 'border-[#d8d8d8] bg-white text-[#272727] hover:border-[#272727]')
            }
          >
            {data.categories.find((d) => d.key === c)?.name ?? c}
          </button>
        ))}
      </div>
      {(days < 3 || suspects > 0) && (
        <p className="mt-[18px] rounded-[14px] bg-[#fff8e6] px-[18px] py-3.5 text-sm leading-[21px] text-[#8a6100]">
          ⚠ {days < 3 && `기록이 아직 ${days}일이라 흐름은 판단이 일러요. `}
          {suspects > 0 && (
            <>
              {days < 3 ? '또 ' : ''}10만원 미만으로 잡힌 상위 그래픽카드는 부품(쿨링 팬 등)이 섞인 값일 수 있어{' '}
              <b className="font-bold text-(--color-accent)">가격 확인 필요</b>로 표시했어요.
            </>
          )}
        </p>
      )}
      <div className="mt-[19px] overflow-x-auto">
        <table className="w-full min-w-[900px] border-collapse" data-nosnippet>
          <thead>
            <tr>
              <th className={th + ' w-[85px]'}>등급</th>
              <th className={th + ' w-[344px]'}>부품</th>
              <th className={th + ' w-[295px]'}>오늘</th>
              <th className={th + ' w-[190px]'}>지난 30일 대비</th>
              <th className={th + ' w-[253px]'}>흐름</th>
              <th className={th}>매물</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, price, rec, tier }) => (
              <tr key={p.id} className="h-[53px] border-b border-[#e2e2e2] hover:bg-[#fafbfc]">
                <td className="px-3">{tier && <TierBadge tier={tier.tier} size={26} />}</td>
                <td className="px-3">
                  <a href={paths.hardwarePart(p.id)} onClick={onLinkClick(paths.hardwarePart(p.id))} className="text-[15px] font-medium text-[#272727] hover:underline underline-offset-2">
                    {p.name}
                  </a>
                </td>
                <td className="px-3 whitespace-nowrap">
                  <span className="text-[15px] font-bold text-[#272727] tabular-nums">{won(price)}</span>
                  {priceSuspect(p, price) && price != null && (
                    <span className="ml-[3px] rounded bg-[#f67979] px-[7px] text-[13px] leading-[22px] text-white">가격 확인 필요</span>
                  )}
                  {p.price_basis === 'median' && <span className="ml-1.5 text-xs text-[#999]">급 가운데 값</span>}
                  {usedPrice(data.prices[p.id]) && (
                    <span className="ml-1.5 rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]" title="새 제품이 없어 다나와 중고 시세로 대신했어요">
                      중고 시세
                    </span>
                  )}
                </td>
                <td className="px-3">
                  <MoveBadge rec={rec} />
                </td>
                <td className="px-3">
                  <Spark rec={rec} />
                </td>
                <td className="px-3 text-sm text-[#474747] tabular-nums">{rec?.n != null ? `${rec.n}개` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-xs text-[#999]">
        가격은 다나와 통합검색에 잡힌 매물 중 부품 조건에 맞는 것의 최저가다. 급(쿨러·케이스)은 한 상품이 아니라 그 급 매물의 가운데 값이다. 상세에서 매물을 누르면 다나와 원문으로 간다.
      </p>
    </div>
  )
}
