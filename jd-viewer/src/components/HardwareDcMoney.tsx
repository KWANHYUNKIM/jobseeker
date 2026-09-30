import { Fragment, useState } from 'react'

// AI 데이터센터 — 금액. 회사별로 가진 데이터센터가 얼마짜리인가(추정)와, 실제로 공시한 설비투자·약정.
//
// 데이터센터 값은 세 방법 중 먼저 되는 것으로 센다(행마다 어느 것인지 적는다).
//   1. Epoch AI 가 그 데이터센터에 붙인 건설비 추정(칩 + 건물)
//   2. 전력(MW) × GW 당 비용(Epoch 1GW 모델)
//   3. 칩 수 × 칩 단가(보도·Epoch 추정) — 칩 값만이라 건물·전력 설비가 빠진 하한
// 공시 설비투자는 회사 전체 값이다(AI 만이 아니다). 약정은 앞으로 쓰겠다는 계약액이다.

interface Src {
  title: string
  url: string
}
interface MCluster {
  key: string
  company: string
  name: string
  chip: string | null
  chip_key?: string | null
  mix?: { chip_key: string; count: number }[]
  count: number | null
  h100eq?: number | null
  mw: number | null
  status: string
  in_total?: boolean
  cost_usd?: number
  cost_note?: string
  cost_src?: string
}
export interface Money {
  unit_prices: { chip_key: string; usd: number; basis: string; sources: Src[] }[]
  per_gw: { usd: number; basis: string; sources: Src[]; others: { who: string; claim: string; as_of: string; src: string }[] }
  capex: { company: string; rows: [string, number, string][]; note: string; sources: Src[] }[]
  commitments: { who: string; deal: string; usd: number | null; note: string; src: string }[]
  aggregate: { claim: string; src: string }
}

type How = 'epoch' | 'power' | 'chips' | 'eq'
const HOW: Record<How, string> = { epoch: 'Epoch 건설비 추정', power: '전력 × GW 당 비용', chips: '칩 수 × 단가(칩만)', eq: 'H100 환산 × H100 단가(칩만)' }

export interface Fx {
  krw_per_usd: number
  as_of: string
  basis: string
  sources: Src[]
}

/** 원화 — 1,353원/달러면 358억 달러 → 약 48조 원 */
function krw(n: number | null | undefined, fx?: Fx): string {
  if (n == null || !fx || !Number.isFinite(n)) return ''
  const w = n * fx.krw_per_usd
  if (w >= 1e12) return `약 ${(w / 1e12).toFixed(w >= 1e14 ? 0 : 1)}조 원`
  if (w >= 1e8) return `약 ${Math.round(w / 1e8).toLocaleString()}억 원`
  return `약 ${Math.round(w / 1e4).toLocaleString()}만 원`
}

/** 달러를 한국식 단위로 — 35,836,000,000 → 358억 달러 */
function usd(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const units: [number, string][] = [
    [1e12, '조'],
    [1e8, '억'],
    [1e4, '만'],
  ]
  for (const [v, u] of units) {
    if (Math.abs(n) >= v) {
      const x = n / v
      return `${x >= 100 ? Math.round(x).toLocaleString() : x.toFixed(x >= 10 ? 0 : 1)}${u} 달러`
    }
  }
  return `${Math.round(n)} 달러`
}

function valueOf(c: MCluster, m: Money): { v: number; how: How } | null {
  if (c.cost_usd != null) return { v: c.cost_usd, how: 'epoch' }
  if (c.mw != null) return { v: (c.mw / 1000) * m.per_gw.usd, how: 'power' }
  const price = (k?: string | null) => (k ? m.unit_prices.find((u) => u.chip_key === k)?.usd : undefined)
  if (c.mix?.length) {
    const xs = c.mix.map((x) => (price(x.chip_key) != null ? x.count * price(x.chip_key)! : null))
    if (xs.every((x) => x != null)) return { v: xs.reduce((a, b) => a! + b!, 0)!, how: 'chips' }
    return null
  }
  const p = price(c.chip_key)
  if (p != null && c.count != null) return { v: c.count * p, how: 'chips' }
  // 칩 구성은 모르고 H100 환산만 밝힌 곳(Tesla) — H100 단가로 친 칩 값
  const h = price('H100')
  return c.h100eq != null && h != null ? { v: c.h100eq * h, how: 'eq' } : null
}

export function MoneyView({ clusters, m, fx }: { clusters: MCluster[]; m: Money; fx?: Fx }) {
  const [open, setOpen] = useState<string | null>(null)
  const live = clusters.filter((c) => c.status === 'operational' && c.in_total !== false)
  const names = [...new Set(live.map((c) => c.company))]
  const rows = names
    .map((name) => {
      const cs = live.filter((c) => c.company === name).map((c) => ({ c, val: valueOf(c, m) }))
      const known = cs.filter((x) => x.val)
      return {
        name,
        cs,
        total: known.reduce((s, x) => s + x.val!.v, 0),
        hows: [...new Set(known.map((x) => x.val!.how))],
        missing: cs.length - known.length,
      }
    })
    .sort((a, b) => b.total - a.total)
  const skipped = rows.filter((r) => r.total <= 0).map((r) => r.name)
  rows.splice(rows.length - skipped.length)
  const max = Math.max(...rows.map((r) => r.total), 1)
  const grand = rows.reduce((s, r) => s + r.total, 0)

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
        <div className="p-4 pb-2">
          <h2 className="text-sm font-semibold">가동 중인 데이터센터는 얼마짜리인가 — 추정</h2>
          <p className="text-[11px] text-(--color-muted)">
            {rows.length}개 회사·기관 합계 약 <b>{usd(grand)}</b>({krw(grand, fx)}). 방법은 줄마다 다르다 — Epoch 건설비 추정 → 전력 × GW 당 {usd(m.per_gw.usd)} → 칩 수 × 단가(칩 값만이라 하한). 줄을 누르면 데이터센터별 내역.
          </p>
        </div>
        <table className="w-full text-sm min-w-[820px]">
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-y border-(--color-border)">
              <th className="font-normal px-4 py-2">회사</th>
              <th className="font-normal px-2 py-2 w-[45%]">추정 값</th>
              <th className="font-normal px-2 py-2">셈 방법</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const shown = open === r.name
              return (
                <Fragment key={r.name}>
                  <tr className={`border-t border-(--color-border-soft) cursor-pointer ${shown ? 'bg-(--color-accent)/6' : 'hover:bg-(--color-band)'}`} onClick={() => setOpen(shown ? null : r.name)}>
                    <td className="px-4 py-1.5 font-semibold">
                      <span className="text-(--color-muted) mr-1">{shown ? '▾' : '▸'}</span>
                      {r.name}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex items-center gap-2">
                        <div className="h-3 rounded-r bg-(--color-accent)" style={{ width: `${Math.max(0.5, (r.total / max) * 70)}%` }} />
                        <span className="tabular-nums font-semibold whitespace-nowrap">{usd(r.total)}</span>
                        <span className="text-[10px] text-(--color-faint) whitespace-nowrap">{krw(r.total, fx)}</span>
                      </div>
                    </td>
                    <td className="px-2 py-1.5 text-[11px] text-(--color-muted)">
                      {r.hows.map((h) => HOW[h]).join(' + ')}
                      {r.missing > 0 && <span className="text-(--color-faint)"> · 값 모름 {r.missing}곳 제외</span>}
                    </td>
                  </tr>
                  {shown &&
                    r.cs.map(({ c, val }) => (
                      <tr key={c.key} className="bg-(--color-accent)/4 text-xs">
                        <td className="pl-10 pr-2 py-1">{c.name}</td>
                        <td className="px-2 py-1 tabular-nums">
                          {val ? usd(val.v) : '—'}
                          <span className="text-(--color-faint)">
                            {' '}
                            · {c.chip ?? '—'}
                            {c.count ? ` ${c.count.toLocaleString()}장` : ''}
                            {c.mw ? ` · ${c.mw}MW` : ''}
                          </span>
                        </td>
                        <td className="px-2 py-1 text-[11px] text-(--color-muted)">
                          {val ? HOW[val.how] : '칩 단가·전력을 몰라 셀 수 없다'}
                          {c.cost_note && (
                            <div className="text-[10px]">
                              {c.cost_note}{' '}
                              {c.cost_src && (
                                <a href={c.cost_src} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                                  출처
                                </a>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                </Fragment>
              )
            })}
          </tbody>
        </table>
        {skipped.length > 0 && (
          <p className="px-4 py-2 text-[11px] text-(--color-muted) border-t border-(--color-border-soft)">
            <b>값을 셀 수 없어 뺀 곳 {skipped.length}</b> — 칩 단가도 전력도 공개되지 않았다(자체 칩·연산량만 공시·H100 환산만 공시): {skipped.join(' · ')}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
        <div>
          <h2 className="text-sm font-semibold">실제로 쓴 돈 — 공시한 설비투자</h2>
          <p className="text-[11px] text-(--color-muted)">
            회사 전체 설비투자다(AI 만이 아니다 — xAI 만 AI 부문 값). 회사마다 리스 포함 여부가 다르다. {m.aggregate.claim}{' '}
            <a href={m.aggregate.src} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
              출처
            </a>
          </p>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {m.capex.map((c) => {
            const top = Math.max(...c.rows.map((r) => r[1]))
            return (
              <div key={c.company} className="rounded-md border border-(--color-border-soft) p-3 text-xs flex flex-col gap-1">
                <b className="text-sm">{c.company}</b>
                {c.rows.map(([label, v, kind]) => (
                  <div key={label} className="grid grid-cols-[6.5rem_minmax(0,1fr)_5.5rem] items-center gap-2">
                    <span className="text-(--color-muted)">{label}</span>
                    <div className="h-2 rounded-r" style={{ width: `${(v / top) * 100}%`, background: kind === 'guidance' ? 'color-mix(in srgb, var(--color-accent) 40%, var(--color-panel))' : 'var(--color-accent)' }} />
                    <span className="tabular-nums text-right" title={krw(v, fx)}>
                      {usd(v)}
                      {kind === 'guidance' && <span className="text-[9px] text-(--color-faint)"> 전망</span>}
                    </span>
                  </div>
                ))}
                <p className="text-[10px] text-(--color-muted)">{c.note}</p>
                <div className="text-[10px] flex flex-wrap gap-x-2">
                  {c.sources.map((s) => (
                    <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                      {s.title}
                    </a>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold mb-2">앞으로 쓰겠다고 약속한 돈 — 컴퓨트 약정</h2>
          <table className="w-full text-xs">
            <tbody>
              {m.commitments.map((c) => (
                <tr key={c.who + c.deal} className="border-t border-(--color-border-soft) align-top">
                  <td className="py-1 pr-2 font-semibold whitespace-nowrap">{c.who}</td>
                  <td className="py-1 pr-2">
                    {c.deal}
                    <div className="text-[10px] text-(--color-muted)">
                      {c.note}{' '}
                      <a href={c.src} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                        출처
                      </a>
                    </div>
                  </td>
                  <td className="py-1 text-right tabular-nums font-semibold whitespace-nowrap">
                    {usd(c.usd)}
                    <div className="text-[10px] font-normal text-(--color-faint)">{krw(c.usd, fx)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-(--color-faint) mt-2">약정끼리 겹친다(Stargate 안에 Oracle 계약이 들어 있다) — 더하지 않는다.</p>
        </section>
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
          <h2 className="text-sm font-semibold">한 장·한 GW 는 얼마인가</h2>
          <p className="text-xs">
            <b>1GW 데이터센터 약 {usd(m.per_gw.usd)}</b> — {m.per_gw.basis}{' '}
            {m.per_gw.sources.map((s) => (
              <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-[10px] text-(--color-sky-400) hover:underline">
                {s.title}
              </a>
            ))}
          </p>
          <ul className="text-xs flex flex-col gap-1">
            {m.per_gw.others.map((o) => (
              <li key={o.who + o.claim}>
                <b>{o.who}</b> <span className="text-(--color-faint)">({o.as_of})</span> — {o.claim}{' '}
                <a href={o.src} target="_blank" rel="noreferrer" className="text-[10px] text-(--color-sky-400) hover:underline">
                  출처
                </a>
              </li>
            ))}
          </ul>
          <table className="w-full text-xs mt-1">
            <thead>
              <tr className="text-[10px] text-(--color-muted) text-left">
                <th className="font-normal">칩</th>
                <th className="font-normal text-right">한 장</th>
                <th className="font-normal pl-3">근거</th>
              </tr>
            </thead>
            <tbody>
              {m.unit_prices.map((u) => (
                <tr key={u.chip_key} className="border-t border-(--color-border-soft) align-top">
                  <td className="py-1 font-semibold whitespace-nowrap">{u.chip_key}</td>
                  <td className="py-1 text-right tabular-nums">${u.usd.toLocaleString()}</td>
                  <td className="py-1 pl-3 text-[10px] text-(--color-muted)">
                    {u.basis}{' '}
                    {u.sources.map((s) => (
                      <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline mr-1">
                        {s.title}
                      </a>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-(--color-faint)">NVIDIA 는 정가를 공개하지 않는다 — 모두 보도·애널리스트·Epoch 추정이고 계약마다 다르다.</p>
          {fx && (
            <p className="text-[10px] text-(--color-faint)">
              원화는 1달러 = {fx.krw_per_usd.toLocaleString()}원({fx.as_of}, {fx.basis}){' '}
              {fx.sources.map((s) => (
                <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                  {s.title}
                </a>
              ))}
              로 바꿨다.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
