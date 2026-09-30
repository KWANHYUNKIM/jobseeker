import { useState } from 'react'
import { RES_LABEL, estimateFps, priceOf, tierOf, won, type Category, type HwData, type Part, type Res } from './hardware'
import { onLinkClick } from '../../shared/lib/router'
import { paths } from '../../shared/lib/urls'
import { VariantList } from './HardwarePopular'

// 성능을 눈으로 — 세 가지 차트와 한 가지 그림.
//
//  PerfLadder     성능 사다리. 한 분류(GPU·CPU)를 지수 순으로 세운 막대. 값 하나(크기)라 한 색이고,
//                 등급은 순서가 있는 값이라 같은 색의 진하기로 가른다. 보고 있는 부품만 테두리로 짚는다.
//                 줄 끝의 ▾ 를 누르면 그 칩을 얹은 제품들(인기순·제품별 지수·판매처)이 펼쳐진다.
//  GameCompare    게임별 예상 fps — 이 카드 vs 바로 위·아래 카드. 주인공 하나 + 비교 둘이라
//                 주인공은 강조색, 비교는 회색 두 단계(강조형). 막대 끝에 값, 위에 범례.
//  VendorBench    제조사가 공개한 측정값. 게임·옵션이 우리 추정과 달라 한 차트에 섞지 않는다.
//  CardDrawing    그래픽카드 실측 비율 그림(길이 × 높이, 팬 수, 슬롯). 사진이 없을 때 대신한다.
//
// 막대마다 마우스를 올리면 설명이 뜬다. 차트 아래에는 늘 '어떻게 잰 값인가'를 적는다.

const TIER_SHADE: Record<string, number> = { S: 100, A: 80, B: 60, C: 42, D: 28 }
const tierFill = (t?: string) => `color-mix(in srgb, var(--color-accent) ${TIER_SHADE[t ?? ''] ?? 35}%, var(--color-panel))`

interface Tip {
  x: number
  y: number
  lines: string[]
}

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null
  return (
    <div
      className="pointer-events-none absolute z-10 rounded-md border border-(--color-border) bg-(--color-panel) px-2 py-1 text-xs shadow-md tabular-nums"
      style={{ left: tip.x + 12, top: tip.y + 8 }}
    >
      {tip.lines.map((l, i) => (
        <div key={i} className={i === 0 ? 'font-semibold' : 'text-(--color-muted)'}>
          {l}
        </div>
      ))}
    </div>
  )
}

function useTip() {
  const [tip, setTip] = useState<Tip | null>(null)
  const on = (lines: string[]) => (e: React.MouseEvent) => {
    const r = (e.currentTarget.closest('[data-chart]') as HTMLElement).getBoundingClientRect()
    setTip({ x: e.clientX - r.left, y: e.clientY - r.top, lines })
  }
  return { tip, on, off: () => setTip(null) }
}

// ── 성능 사다리 ─────────────────────────────────────────────────────

export function PerfLadder({ data, cat, highlight, measure = 'index' }: { data: HwData; cat: Category; highlight?: string; measure?: 'index' | 'multi' }) {
  const { tip, on, off } = useTip()
  const [open, setOpen] = useState<string | null>(null)
  const rows = data.parts
    .filter((p) => p.category === cat)
    .map((p) => ({ p, v: measure === 'multi' ? (p.perf.multi ?? 0) : p.perf.index, t: tierOf(p, data.categories)?.tier, price: priceOf(p, data.prices) }))
    .sort((a, b) => b.v - a.v)
  const max = Math.max(...rows.map((r) => r.v), 1)
  const def = data.categories.find((c) => c.key === cat)
  const label = measure === 'multi' ? '멀티 지수' : def?.index_label
  return (
    <figure className="relative" data-chart onMouseLeave={off}>
      <figcaption className="flex flex-wrap items-baseline gap-2 mb-2">
        <span className="text-sm font-semibold">성능 사다리 — {def?.name} {label}</span>
        <span className="text-[11px] text-(--color-muted)">{measure === 'multi' ? '9950X = 100' : def?.index_basis} · 막대 색이 진할수록 높은 등급</span>
      </figcaption>
      <div className="flex flex-col gap-[2px]" role="list">
        {rows.map(({ p, v, t, price }) => {
          const me = p.id === highlight
          const shown = open === p.id
          return (
            <div key={p.id} role="listitem" className="flex flex-col">
              <div className="flex items-center gap-1">
                <a
                  href={paths.hardwarePart(p.id)}
                  onClick={onLinkClick(paths.hardwarePart(p.id))}
                  className={`flex-1 min-w-0 grid grid-cols-[9.5rem_minmax(0,1fr)_6.5rem] items-center gap-2 py-0.5 rounded ${me ? 'bg-(--color-accent)/8' : 'hover:bg-(--color-band)'} ${p.status === 'legacy' ? 'opacity-60' : ''}`}
                  onMouseMove={on([
                    p.name,
                    `${label} ${v}${t ? ` · ${t} 등급` : ''}`,
                    price != null ? `가격 ${won(price)} · 1점당 ${Math.round(price / (v || 1)).toLocaleString()}원` : '가격 모름',
                    ...(p.status === 'legacy' ? ['단품 판매 끝남'] : []),
                  ])}
                >
                  <span className={`text-xs truncate text-right ${me ? 'font-bold text-(--color-text)' : 'text-(--color-muted)'}`}>{p.name.replace('GeForce ', '').replace('Radeon ', '')}</span>
                  <span className="relative h-4">
                    <span
                      className="absolute inset-y-0 left-0 rounded-r-[4px]"
                      style={{ width: `${(v / max) * 100}%`, background: tierFill(t), outline: me ? '2px solid var(--color-text)' : undefined, outlineOffset: 1 }}
                    />
                    <span className="absolute inset-y-0 flex items-center text-[11px] font-semibold tabular-nums pl-1" style={{ left: `${(v / max) * 100}%` }}>
                      {v}
                    </span>
                  </span>
                  <span className="text-[11px] text-(--color-muted) tabular-nums text-right" data-nosnippet>
                    {price != null ? won(price) : '—'}
                  </span>
                </a>
                <button
                  type="button"
                  onClick={() => setOpen(shown ? null : p.id)}
                  aria-expanded={shown}
                  aria-label={`${p.name} 제품별 보기`}
                  title="이 칩을 얹은 제품들 — 인기순·제품별 성능·판매처"
                  className={`w-5 h-5 shrink-0 rounded text-[11px] leading-none ${shown ? 'bg-(--color-accent) text-(--color-on-accent)' : 'text-(--color-muted) hover:bg-(--color-band)'}`}
                >
                  {shown ? '▴' : '▾'}
                </button>
              </div>
              {shown && (
                <div className="ml-2 my-1 pl-2 border-l-2 border-(--color-accent)/50">
                  <VariantList data={data} part={p} />
                </div>
              )}
            </div>
          )
        })}
      </div>
      <Tooltip tip={tip} />
    </figure>
  )
}

// ── 게임별 예상 fps 비교 ────────────────────────────────────────────

const SERIES = ['var(--color-accent)', 'color-mix(in srgb, var(--color-muted) 80%, var(--color-panel))', 'color-mix(in srgb, var(--color-muted) 40%, var(--color-panel))']

export function GameCompare({ data, part }: { data: HwData; part: Part }) {
  const [res, setRes] = useState<Res>('qhd')
  const { tip, on, off } = useTip()
  const gpus = data.parts.filter((p) => p.category === 'gpu' && p.status === 'current').sort((a, b) => a.perf.index - b.perf.index)
  const i = gpus.findIndex((g) => g.id === part.id)
  const above = gpus.slice(i + 1).find((g) => g.perf.index > part.perf.index)
  const below = [...gpus.slice(0, Math.max(0, i))].reverse().find((g) => g.perf.index < part.perf.index)
  const set = [part, ...(above ? [above] : []), ...(below ? [below] : [])]
  // CPU 가 발목을 잡지 않게 가장 빠른 CPU 로 잰다 — 그래픽카드끼리의 차이만 보려는 것이다
  const cpu = data.parts.filter((p) => p.category === 'cpu').sort((a, b) => b.perf.index - a.perf.index)[0] ?? null
  const games = data.bench.games
  const vals = games.map((g) => set.map((p) => estimateFps(g, res, p, cpu)))
  const max = Math.max(...vals.flat().map((v) => v.fps), 60)
  return (
    <figure className="relative" data-chart onMouseLeave={off}>
      <figcaption className="flex flex-wrap items-center gap-2 mb-2">
        <span className="text-sm font-semibold">게임별 예상 fps</span>
        <div className="flex flex-wrap gap-3 text-[11px] text-(--color-muted)">
          {set.map((p, k) => (
            <span key={p.id} className="inline-flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ background: SERIES[k] }} />
              {p.name.replace('GeForce ', '').replace('Radeon ', '')}
              {k === 1 && ' (위 급)'}
              {k === 2 && ' (아래 급)'}
            </span>
          ))}
        </div>
        <div className="ml-auto inline-flex rounded-md border border-(--color-border) overflow-hidden">
          {(Object.keys(RES_LABEL) as Res[]).map((r) => (
            <button key={r} onClick={() => setRes(r)} className={`px-2.5 py-1 text-xs ${r === res ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'text-(--color-muted)'}`}>
              {RES_LABEL[r]}
            </button>
          ))}
        </div>
      </figcaption>
      <div className="flex flex-col gap-2.5">
        {games.map((g, gi) => (
          <div key={g.key} className="grid grid-cols-[8rem_minmax(0,1fr)] gap-2 items-center">
            <div className="text-xs text-right">
              <div className="font-medium truncate">{g.name}</div>
              <div className="text-[10px] text-(--color-faint) truncate">{g.preset}</div>
            </div>
            <div className="flex flex-col gap-[2px]">
              {set.map((p, k) => {
                const e = vals[gi][k]
                const w = (Math.min(e.fps, max) / max) * 100
                return (
                  <div
                    key={p.id}
                    className="relative h-3"
                    onMouseMove={on([`${p.name} · ${g.name}`, `${RES_LABEL[res]} ${g.preset}: ${e.fps} fps`, e.vramShort ? `VRAM ${e.vramShort}GB 부족으로 깎임` : `그래픽카드 한계 ${e.gpuFps} fps`])}
                  >
                    <div className="absolute inset-y-0 left-0 rounded-r-[4px]" style={{ width: `${w}%`, background: SERIES[k] }} />
                    <span className={`absolute inset-y-0 flex items-center pl-1 text-[10px] tabular-nums ${k === 0 ? 'font-bold' : 'text-(--color-muted)'}`} style={{ left: `${w}%` }}>
                      {e.fps}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-(--color-faint) mt-2">
        우리 추정 — 기준 카드 실측에서 성능 지수로 환산했다(bench.json). CPU 는 {cpu?.name} 로 잡아 그래픽카드끼리의 차이만 보인다. 업스케일·프레임 생성은 끈 값이다.
      </p>
      <Tooltip tip={tip} />
    </figure>
  )
}

// ── 제조사 공개 측정 ────────────────────────────────────────────────

export function VendorBench({ data, part }: { data: HwData; part: Part }) {
  const { tip, on, off } = useTip()
  const blocks = (data.bench.vendor ?? []).filter((v) => v.gpu === part.id)
  if (!blocks.length) return null
  return (
    <figure className="relative flex flex-col gap-4" data-chart onMouseLeave={off}>
      {blocks.map((b, bi) => {
        const max = Math.max(...b.games.map((g) => g.fps))
        return (
          <div key={bi}>
            <figcaption className="text-sm font-semibold mb-1.5">
              {b.by} 공개 측정 — {RES_LABEL[b.res as Res]} {b.preset}
              <span className="font-normal text-[11px] text-(--color-muted)"> · 각주 {b.footnote}</span>
            </figcaption>
            <div className="flex flex-col gap-[3px]">
              {b.games.map((g) => (
                <div key={g.name} className="grid grid-cols-[11rem_minmax(0,1fr)] gap-2 items-center" onMouseMove={on([g.name, `${g.fps} fps (${b.by} 측정)`, `각주 ${b.footnote} 의 시험 조건`])}>
                  <span className="text-xs text-right truncate">{g.name}</span>
                  <span className="relative h-4">
                    <span className="absolute inset-y-0 left-0 rounded-r-[4px] bg-(--color-accent)" style={{ width: `${(g.fps / max) * 100}%` }} />
                    <span className="absolute inset-y-0 flex items-center pl-1 text-[11px] font-semibold tabular-nums" style={{ left: `${(g.fps / max) * 100}%` }}>
                      {g.fps}
                    </span>
                  </span>
                </div>
              ))}
            </div>
            <a href={b.source.url} target="_blank" rel="noreferrer" className="text-[11px] text-(--color-sky-400) hover:underline">
              출처: {b.source.title}
            </a>
          </div>
        )
      })}
      <p className="text-[11px] text-(--color-faint)">{data.bench.vendor_note}</p>
      <Tooltip tip={tip} />
    </figure>
  )
}

// ── 그래픽카드 실측 비율 그림 ─────────────────────────────────────────

export function CardDrawing({ specs, caseLimit = 400 }: { specs: Record<string, unknown>; caseLimit?: number }) {
  const L = Number(specs.length_mm)
  const H = Number(specs.width_mm) || 120
  const fans = Number(specs.fans) || 0
  if (!L) return null
  const scale = 300 / Math.max(caseLimit, L)
  const w = L * scale
  const h = H * scale
  const fanR = Math.min(h * 0.38, (w / Math.max(fans, 1)) * 0.42)
  return (
    <svg viewBox={`0 0 ${300 + 20} ${h + 48}`} className="w-full max-w-[340px] h-auto" role="img" aria-label={`그래픽카드 크기 그림 — 길이 ${L}mm, 높이 ${H}mm, 팬 ${fans}개`}>
      <line x1={10 + caseLimit * scale} x2={10 + caseLimit * scale} y1={16} y2={h + 20} stroke="var(--color-red-400)" strokeDasharray="3 3" />
      <text x={10 + caseLimit * scale} y={10} textAnchor="end" fontSize={9} fill="var(--color-red-400)">
        미들타워 흔한 한도 {caseLimit}mm ┐
      </text>
      <rect x={10} y={20} width={w} height={h} rx={6} fill="color-mix(in srgb, var(--color-muted) 18%, var(--color-panel))" stroke="var(--color-muted)" />
      {Array.from({ length: fans }).map((_, k) => (
        <circle key={k} cx={10 + (w / fans) * (k + 0.5)} cy={20 + h / 2} r={fanR} fill="var(--color-panel)" stroke="var(--color-muted)" />
      ))}
      <text x={10 + w / 2} y={h + 38} textAnchor="middle" fontSize={10} fill="var(--color-text)">
        {L}mm{specs.slots ? ` · ${specs.slots}슬롯` : ''}{specs.thickness_mm ? ` · 두께 ${specs.thickness_mm}mm` : ''}
      </text>
    </svg>
  )
}
