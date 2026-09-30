import { useState } from 'react'

// AI 데이터센터 — 시장 조사. 회사가 무엇으로 돈을 벌고, 어떻게 투자금을 회수하나, GPU 는 얼마나 버티나.
// 숫자는 모두 public/hardware/datacenter.json 의 market 에 출처와 함께 있다(공시·공식 발표·보도 구분).
// 회수 계산기는 사용자가 값을 바꿔 보는 도구다 — 기본값은 출처 있는 숫자(Latent Space 의 H100 모델, Silicon Data 지수)이고
// 가동률·전기료 같은 가정은 화면에 '가정'으로 적는다.

interface Src {
  title: string
  url: string
}
export interface Market {
  business: { company: string; model: string; domains: string[]; numbers: [string, string, string][]; payback: string; sources: Src[] }[]
  rental: { gpu: string; d: string; usd: number; note: string; src: string }[]
  list_prices: { gpu: string; usd: number; who: string; src: string }[]
  payback: { who: string; claim: string; as_of: string; src: string }[]
  tokens: { claim: string; as_of: string; src: string }[]
  durability: {
    depreciation: { company: string; years: number | null; from: number | null; when: string; impact: string; sources: Src[] }[]
    critique: { who: string; claim: string; as_of: string; sources: Src[] }[]
    failures: { study: string; finding: string; as_of: string; sources: Src[] }[]
    lifespan: { claim: string; who: string; confidence: string; as_of: string; sources: Src[] }[]
    obsolescence: { claim: string; who: string; as_of: string; sources: Src[] }[]
  }
}

const KIND: Record<string, string> = { official: '공시', reported: '보도', estimate: '추정' }

function Links({ xs }: { xs: Src[] }) {
  return (
    <span className="inline-flex flex-wrap gap-x-2">
      {xs.map((s) => (
        <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
          {s.title}
        </a>
      ))}
    </span>
  )
}

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {sub && <p className="text-[11px] text-(--color-muted)">{sub}</p>}
      </div>
      {children}
    </section>
  )
}

// ── 임대가 추이 — 점 몇 개라 선과 점, 값은 점 옆에 ─────────────────────

function RentalChart({ m }: { m: Market }) {
  const pts = m.rental.filter((r) => r.gpu === 'H100')
  const other = m.rental.filter((r) => r.gpu !== 'H100')
  const t = (d: string) => {
    const [y, mo] = d.split('-').map(Number)
    return y + (mo - 1) / 12
  }
  const all = [...pts, ...other]
  const x0 = Math.min(...all.map((r) => t(r.d))) - 0.1
  const x1 = Math.max(...all.map((r) => t(r.d))) + 0.3
  const yMax = Math.ceil(Math.max(...all.map((r) => r.usd)) + 1)
  const W = 640, H = 220, L = 40, B = 28, T = 12, R = 16
  const X = (d: string) => L + ((t(d) - x0) / (x1 - x0)) * (W - L - R)
  const Y = (v: number) => T + (1 - v / yMax) * (H - T - B)
  const years = [2023, 2024, 2025, 2026].filter((y) => y >= x0 && y <= x1)
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="H100 시간당 임대가 추이">
        {[0, 2, 4, 6, 8].filter((v) => v <= yMax).map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="var(--color-border-soft)" />
            <text x={L - 6} y={Y(v) + 3} textAnchor="end" fontSize="10" fill="var(--color-muted)">
              ${v}
            </text>
          </g>
        ))}
        {years.map((y) => (
          <text key={y} x={L + ((y - x0) / (x1 - x0)) * (W - L - R)} y={H - 8} fontSize="10" fill="var(--color-muted)" textAnchor="middle">
            {y}
          </text>
        ))}
        <polyline fill="none" stroke="var(--color-accent)" strokeWidth="2" points={pts.map((p) => `${X(p.d)},${Y(p.usd)}`).join(' ')} />
        {pts.map((p) => (
          <g key={p.d}>
            <circle cx={X(p.d)} cy={Y(p.usd)} r="3.5" fill="var(--color-accent)">
              <title>{`H100 ${p.d} · $${p.usd} — ${p.note}`}</title>
            </circle>
            <text x={X(p.d)} y={Y(p.usd) - 8} fontSize="10" textAnchor="middle" fill="var(--color-text)">
              ${p.usd}
            </text>
          </g>
        ))}
        {other.map((p) => (
          <g key={p.gpu + p.d}>
            <circle cx={X(p.d)} cy={Y(p.usd)} r="3.5" fill="none" stroke="var(--color-text)" strokeWidth="1.5">
              <title>{`${p.gpu} ${p.d} · $${p.usd} — ${p.note}`}</title>
            </circle>
            <text x={X(p.d) + 6} y={Y(p.usd) + 3} fontSize="10" fill="var(--color-text)">
              {p.gpu} ${p.usd}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="text-[10px] text-(--color-muted) flex flex-col gap-0.5">
        <span>
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-(--color-accent) align-middle mr-1" />
          H100 시간당 임대가(지수 중앙값) · <span className="inline-block w-2.5 h-2.5 rounded-full border border-(--color-text) align-middle mr-1" />
          B200. 점에 마우스를 올리면 출처 설명.
        </span>
        <span>
          {[...new Set(m.rental.map((r) => r.src))].map((u, i) => (
            <a key={u} href={u} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline mr-2">
              출처 {i + 1}
            </a>
          ))}
        </span>
      </figcaption>
    </figure>
  )
}

// ── 회수 계산기 ────────────────────────────────────────────────────

function Num({ label, value, set, step, unit, note }: { label: string; value: number; set: (v: number) => void; step: number; unit: string; note: string }) {
  return (
    <label className="flex flex-col gap-0.5 text-xs">
      <span className="text-(--color-muted)">{label}</span>
      <span className="flex items-center gap-1">
        <input
          type="number"
          value={value}
          step={step}
          onChange={(e) => set(Number(e.target.value))}
          className="w-24 border border-(--color-border) rounded px-1.5 py-0.5 bg-(--color-panel) tabular-nums"
        />
        <span>{unit}</span>
      </span>
      <span className="text-[10px] text-(--color-faint)">{note}</span>
    </label>
  )
}

function PaybackCalc({ m }: { m: Market }) {
  const index = m.rental.find((r) => r.gpu === 'H100' && r.d.startsWith('2026'))?.usd ?? 2.73
  const [price, setPrice] = useState(50000)
  const [rate, setRate] = useState(index)
  const [util, setUtil] = useState(100)
  const [opex, setOpex] = useState(0)
  const [decay, setDecay] = useState(0)
  const hours = 24 * 365 * (util / 100)
  // 해마다 임대가가 decay% 떨어진다고 치고 누적 순수입이 GPU 값을 넘는 시점
  let cum = 0
  let year: number | null = null
  const rows: { y: number; rate: number; net: number; cum: number }[] = []
  for (let y = 1; y <= 8; y++) {
    const r = rate * Math.pow(1 - decay / 100, y - 1)
    const net = Math.max(0, (r - opex) * hours)
    const before = cum
    cum += net
    rows.push({ y, rate: r, net, cum })
    if (year == null && cum >= price) year = y - 1 + (price - before) / (net || 1)
  }
  const deps = m.durability.depreciation.map((d) => d.years).filter((x): x is number => x != null)
  const depMin = Math.min(...deps), depMax = Math.max(...deps)
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-5">
        <Num label="GPU 한 장 값(서버·설치 포함)" value={price} set={setPrice} step={1000} unit="달러" note="Latent Space 의 H100 약 5만 달러" />
        <Num label="시간당 임대가" value={rate} set={setRate} step={0.1} unit="달러" note={`Silicon Data H100 지수 ${index}`} />
        <Num label="가동률" value={util} set={setUtil} step={5} unit="%" note="가정 — 쉬는 시간은 돈이 안 된다" />
        <Num label="시간당 전기·운영비" value={opex} set={setOpex} step={0.1} unit="달러" note="가정 — 0 이면 빼지 않는다" />
        <Num label="해마다 임대가 하락" value={decay} set={setDecay} step={5} unit="%" note="Latent Space '연 40% 넘게'(2024)" />
      </div>
      <div className="rounded-md bg-(--color-band) p-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-sm">투자금 회수</span>
        <span className={`text-2xl font-bold tabular-nums ${year == null ? 'text-(--color-red-400)' : year <= depMin ? 'text-(--color-accent)' : 'text-(--color-amber-400)'}`}>
          {year == null ? '8년 안에 못 한다' : `약 ${year.toFixed(1)}년`}
        </span>
        <span className="text-xs text-(--color-muted)">
          회사들이 잡은 감가상각 {depMin}~{depMax}년 ·{' '}
          {year == null ? '임대가가 운영비보다 낮거나 너무 빨리 떨어진다' : year <= depMin ? '장부상 수명 안에 회수한다' : year <= depMax ? '장부상 수명 끝자락에 회수한다' : '장부상 수명보다 오래 걸린다'}
        </span>
        {opex === 0 && decay === 0 && (
          <span className="basis-full text-[11px] text-(--color-amber-400)">
            운영비 0 · 임대가 하락 0 은 가장 낙관적인 경우다 — 전기·인건비·이자를 넣고 해마다 떨어지는 임대가를 넣으면 길어진다.
          </span>
        )}
        <span className="basis-full text-[11px] text-(--color-muted)">
          Latent Space 기준선(5만 달러·5년·가동률 100%): 시간당 <b>2.85달러</b> 넘게 받아야 주식시장 수익률을 이기고 <b>1.65달러</b> 아래면 손해 — 지금 {rate}달러는{' '}
          {rate >= 2.85 ? '기준선 위' : rate >= 1.65 ? '본전과 기준선 사이' : '손해 구간'}다.
        </span>
      </div>
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="text-[10px] text-(--color-muted) text-right">
            <th className="font-normal text-left">해</th>
            <th className="font-normal">임대가</th>
            <th className="font-normal">한 해 순수입</th>
            <th className="font-normal">누적</th>
            <th className="font-normal">GPU 값 대비</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.y} className="border-t border-(--color-border-soft) text-right">
              <td className="text-left py-0.5">{r.y}년째</td>
              <td>${r.rate.toFixed(2)}</td>
              <td>${Math.round(r.net).toLocaleString()}</td>
              <td>${Math.round(r.cum).toLocaleString()}</td>
              <td className={r.cum >= price ? 'text-(--color-accent) font-semibold' : ''}>{Math.round((r.cum / price) * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-(--color-faint)">
        순수입 = (임대가 − 운영비) × 24시간 × 365일 × 가동률. 이자·세금·중고 판매값은 넣지 않았다. 비교: Latent Space 는 가동률 100%·5년에서 시간당 2.85달러 넘게 받아야 주식시장 수익률을 이기고
        1.65달러 아래면 손해라고 셈했다.
      </p>
    </div>
  )
}

// ── 화면 ───────────────────────────────────────────────────────────

export function MarketView({ m }: { m: Market }) {
  const [open, setOpen] = useState<string | null>(null)
  const d = m.durability
  return (
    <div className="flex flex-col gap-4">
      <Card title="누가 무엇으로 돈을 버나" sub="회사가 파는 것(도메인)과 최근 숫자, 투자금을 되찾는 방식. 줄을 누르면 출처.">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {m.business.map((b) => (
            <div key={b.company} className="rounded-md border border-(--color-border-soft) p-3 text-xs flex flex-col gap-1.5 cursor-pointer" onClick={() => setOpen(open === b.company ? null : b.company)}>
              <div className="flex items-baseline gap-2">
                <b className="text-sm">{b.company}</b>
                <span className="text-(--color-muted)">{b.model}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {b.domains.map((x) => (
                  <span key={x} className="px-1.5 py-0.5 rounded bg-(--color-band) text-[10px]">
                    {x}
                  </span>
                ))}
              </div>
              <ul className="flex flex-col gap-0.5">
                {b.numbers.map(([k, v, kind]) => (
                  <li key={k} className="flex gap-2">
                    <span className="text-(--color-muted) shrink-0">{k}</span>
                    <span className="font-semibold">{v}</span>
                    <span className="text-[9px] text-(--color-faint) shrink-0">{KIND[kind] ?? kind}</span>
                  </li>
                ))}
              </ul>
              <p className="text-(--color-text)">
                <span className="text-(--color-muted)">회수: </span>
                {b.payback}
              </p>
              {open === b.company && (
                <div className="text-[10px]">
                  <Links xs={b.sources} />
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="GPU 한 시간 빌리는 값" sub="H100 은 2023년 품귀 때 시간당 8달러 가까이에서 2~3달러로 내려왔다. 2026년에는 공급이 다시 빠듯해졌다.">
          <RentalChart m={m} />
          <div className="text-[11px]">
            <div className="text-(--color-muted) mb-1">지금 정가(2026-09)</div>
            <div className="flex flex-wrap gap-x-4 gap-y-0.5">
              {m.list_prices.map((p) => (
                <a key={p.gpu + p.who} href={p.src} target="_blank" rel="noreferrer" className="hover:underline">
                  <b>{p.gpu}</b> ${p.usd} <span className="text-(--color-faint)">{p.who}</span>
                </a>
              ))}
            </div>
          </div>
        </Card>
        <Card title="GPU 한 장, 몇 년이면 본전을 뽑나" sub="값을 바꿔 보면 회수 기간이 바뀐다. 기본값은 출처 있는 숫자다.">
          <PaybackCalc m={m} />
        </Card>
      </div>

      <Card title="산업 전체는 얼마를 벌어야 하나" sub="설비투자를 회수하려면 필요한 매출에 대한 분석들">
        <ul className="text-xs flex flex-col gap-1.5">
          {m.payback.map((p) => (
            <li key={p.who + p.as_of}>
              <b>{p.who}</b> <span className="text-(--color-faint)">({p.as_of})</span> — {p.claim}{' '}
              <a href={p.src} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                출처
              </a>
            </li>
          ))}
          {m.tokens.map((p) => (
            <li key={p.src}>
              <b>토큰 값</b> <span className="text-(--color-faint)">({p.as_of})</span> — {p.claim}{' '}
              <a href={p.src} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                출처
              </a>
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="GPU 는 장부상 몇 년 쓰나 — 감가상각" sub="회사가 서버·GPU 를 몇 년에 나눠 비용으로 잡나. 길게 잡을수록 당장 이익이 커 보인다.">
          <table className="w-full text-xs">
            <tbody>
              {d.depreciation.map((x) => (
                <tr key={x.company + x.when} className="border-t border-(--color-border-soft) align-top">
                  <td className="py-1 pr-2 font-semibold whitespace-nowrap">{x.company}</td>
                  <td className="py-1 pr-2 tabular-nums whitespace-nowrap">
                    {x.years != null ? (
                      <>
                        {x.from}→<b>{x.years}년</b>
                      </>
                    ) : (
                      '—'
                    )}
                    <div className="text-[10px] text-(--color-faint)">{x.when}</div>
                  </td>
                  <td className="py-1 text-(--color-muted)">
                    {x.impact}{' '}
                    <span className="text-[10px]">
                      <Links xs={x.sources} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="text-xs flex flex-col gap-1 mt-1">
            {d.critique.map((c) => (
              <li key={c.who}>
                <b>{c.who}</b> — {c.claim} <span className="text-[10px]"><Links xs={c.sources} /></span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="실제로는 얼마나 고장 나나" sub="큰 학습 클러스터를 운영한 회사들이 논문으로 밝힌 값">
          <ul className="text-xs flex flex-col gap-2">
            {d.failures.map((f) => (
              <li key={f.study}>
                <b>{f.study}</b> <span className="text-(--color-faint)">({f.as_of})</span>
                <div className="text-(--color-muted)">{f.finding}</div>
                <div className="text-[10px]">
                  <Links xs={f.sources} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="수명에 대한 주장" sub="확인된 것과 아닌 것을 가른다">
          <ul className="text-xs flex flex-col gap-2">
            {d.lifespan.map((l) => (
              <li key={l.claim}>
                {l.claim}
                <div className="text-[10px] text-(--color-muted)">
                  {l.who} · 신뢰도 {l.confidence} · {l.as_of} · <Links xs={l.sources} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="새 세대가 옛 세대 값을 얼마나 깎나" sub="경제적 수명 — 부서지기 전에 값어치가 먼저 떨어진다">
          <ul className="text-xs flex flex-col gap-2">
            {d.obsolescence.map((o) => (
              <li key={o.claim}>
                {o.claim}
                <div className="text-[10px] text-(--color-muted)">
                  {o.who} · {o.as_of} · <Links xs={o.sources} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
