import { useState } from 'react'
import { GRADES, type Analysis, type CohortRow, type Grade, type RateSnapshot } from '../utils/freelance'

// 단가 추이 — 몸값이 어떻게 움직이나.
//
// '전체 중앙값' 하나로 보면 등급 구성이 바뀐 것(이번 주엔 고급 자리가 많았다)과 단가가 바뀐
// 것을 가를 수 없다. 그래서 늘 등급별로 긋고, 분야·유형을 골라 그 안에서 본다.
//   · 주별/월별: 그 기간에 새로 올라온 자리의 '올라올 때 단가'(등급별 중앙값). 다시 셀 수 있다.
//   · 일별 기록: 크롤이 돌 때마다 남긴 그날의 현재 단가표. 지난 시장은 다시 셀 수 없어서 쌓는다.
// 등급은 순서가 있는 범주라 한 색의 명도로 가른다(초급 연함 → 특급 진함). 선 끝 이름과 범례를
// 함께 둔다 — 색만으로 구분하지 않는다.

const SHADE: Record<Grade, number> = { 초급: 35, 중급: 55, 고급: 78, 특급: 100 }
const color = (g: Grade) => `color-mix(in srgb, var(--color-accent) ${SHADE[g]}%, var(--color-panel))`
const MIN_N = 3 // 이보다 적은 점은 선에 올리지 않는다 — 1건짜리를 이으면 없는 추세가 생긴다

function label(unit: 'week' | 'month', period: string) {
  return unit === 'week' ? `${period.slice(5)} 주` : period
}

function CohortChart({ rows, unit }: { rows: CohortRow[]; unit: 'week' | 'month' }) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 760
  const H = 230
  const pad = { l: 40, r: 56, t: 12, b: 26 }
  const vals = rows.flatMap((m) => GRADES.map((g) => m.grades[g]?.median).filter((v): v is number => v != null))
  const lo = Math.max(0, Math.floor((Math.min(...vals) - 50) / 100) * 100)
  const hi = Math.ceil((Math.max(...vals) + 50) / 100) * 100
  const step = (W - pad.l - pad.r) / Math.max(1, rows.length - 1)
  const x = (i: number) => (rows.length === 1 ? (pad.l + W - pad.r) / 2 : pad.l + i * step)
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (v - lo) / (hi - lo || 1))
  const ticks = [lo, Math.round((lo + hi) / 2 / 50) * 50, hi]
  const every = Math.max(1, Math.ceil(rows.length / 8))
  const hm = hover != null ? rows[hover] : null

  return (
    <div className="relative">
      <div className="flex flex-wrap gap-3 text-[11px] text-(--color-muted) mb-1">
        {GRADES.map((g) => (
          <span key={g} className="inline-flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 rounded" style={{ background: color(g) }} />
            {g}
          </span>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="등급별 월 단가 중앙값 추이">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--color-border)" />
            <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="var(--color-muted)">
              {t}
            </text>
          </g>
        ))}
        {rows.map((m, i) =>
          i % every === 0 || i === rows.length - 1 ? (
            <text key={m.period} x={x(i)} y={H - 8} textAnchor="middle" fontSize={10} fill="var(--color-muted)">
              {label(unit, m.period)}
            </text>
          ) : null,
        )}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} stroke="var(--color-muted)" strokeDasharray="3 3" />}
        {GRADES.map((g) => {
          const pts = rows.map((m, i) => [i, m.grades[g]?.median] as const).filter((p): p is readonly [number, number] => p[1] != null)
          if (!pts.length) return null
          const last = pts[pts.length - 1]
          return (
            <g key={g}>
              {pts.length > 1 && (
                <polyline
                  points={pts.map(([i, v]) => `${x(i)},${y(v)}`).join(' ')}
                  fill="none"
                  stroke={color(g)}
                  strokeWidth={2}
                  strokeLinejoin="round"
                />
              )}
              {pts.map(([i, v]) => (
                <circle key={i} cx={x(i)} cy={y(v)} r={4} fill={color(g)} stroke="var(--color-panel)" strokeWidth={2} />
              ))}
              <text x={x(last[0]) + 8} y={y(last[1]) + 3} fontSize={10} fill="var(--color-text)">
                {g}
              </text>
            </g>
          )
        })}
        {rows.map((m, i) => (
          <rect
            key={m.period}
            x={x(i) - step / 2}
            y={pad.t}
            width={step}
            height={H - pad.t - pad.b}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      {hm && (
        <div className="absolute top-6 right-0 text-[11px] rounded border border-(--color-border) bg-(--color-panel) px-2 py-1 shadow-sm">
          <b className="text-(--color-text)">{label(unit, hm.period)}</b>
          {GRADES.map((g) =>
            hm.grades[g] ? (
              <div key={g} className="text-(--color-muted)">
                {g} {hm.grades[g]!.median.toLocaleString()}만원 ({hm.grades[g]!.n}건)
              </div>
            ) : null,
          )}
        </div>
      )}
    </div>
  )
}

export function RateTrend({ analysis, history }: { analysis: Analysis; history: RateSnapshot[] }) {
  const [unit, setUnit] = useState<'week' | 'month'>('week')
  const [domain, setDomain] = useState('전체')
  const [type, setType] = useState('전체')
  const table = analysis.cohorts?.[unit] ?? {}
  const rows = table[`${domain}|${type}`] ?? []
  // 선에는 표본 MIN_N 건 이상인 점만. 표에는 모든 기간을 건수와 함께 그대로 둔다.
  const plotted = rows
    .map((m) => ({
      ...m,
      grades: Object.fromEntries(Object.entries(m.grades).filter(([, s]) => s && s.n >= MIN_N)) as CohortRow['grades'],
    }))
    .filter((m) => Object.keys(m.grades).length > 0)
  const recent = [...history].reverse().slice(0, 30)
  const has = (d: string, t: string) => (table[`${d}|${t}`] ?? []).length > 0
  const sel = 'text-xs rounded border border-(--color-border) bg-(--color-bg) text-(--color-text) px-2 py-1'

  return (
    <div className="flex flex-col gap-5">
      <section>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <h3 className="text-sm font-semibold text-(--color-text) mr-2">등급별 월 단가 중앙값 — 그 기간에 올라온 자리</h3>
          <div className="inline-flex rounded border border-(--color-border) overflow-hidden text-xs">
            {(['week', 'month'] as const).map((u) => (
              <button
                key={u}
                onClick={() => setUnit(u)}
                className={`px-2.5 py-1 ${unit === u ? 'bg-(--color-accent) text-white' : 'text-(--color-muted)'}`}
              >
                {u === 'week' ? '주별' : '월별'}
              </button>
            ))}
          </div>
          <label className="text-xs text-(--color-muted)">
            분야{' '}
            <select className={sel} value={domain} onChange={(e) => setDomain(e.target.value)}>
              {['전체', ...(analysis.domains ?? [])].map((d) => (
                <option key={d} value={d} disabled={!has(d, type)}>
                  {d}
                  {!has(d, type) ? ' (자료 없음)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-(--color-muted)">
            유형{' '}
            <select className={sel} value={type} onChange={(e) => setType(e.target.value)}>
              {['전체', 'SI', 'SM'].map((t) => (
                <option key={t} value={t} disabled={!has(domain, t)}>
                  {t === '전체' ? '전체' : t === 'SI' ? 'SI (구축)' : 'SM (운영)'}
                  {!has(domain, t) ? ' (자료 없음)' : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        {plotted.length === 0 ? (
          <p className="text-xs text-(--color-muted)">
            이 조합에는 표본 {MIN_N}건 이상인 {unit === 'week' ? '주' : '달'}이 아직 없습니다. 아래 표(괄호는 건수)를 보세요.
          </p>
        ) : (
          <>
            <CohortChart rows={plotted} unit={unit} />
            {plotted.length < 2 && (
              <p className="text-[11px] text-(--color-muted)">
                표본 {MIN_N}건 이상인 {unit === 'week' ? '주' : '달'}이 하나뿐이라 점만 찍었습니다. 쌓이면 선으로 이어집니다.
              </p>
            )}
          </>
        )}

        <div className="overflow-x-auto mt-2 max-h-72">
          <table className="w-full text-xs">
            <thead className="text-(--color-muted) sticky top-0 bg-(--color-panel)">
              <tr>
                <th className="text-left font-normal px-2 py-1">{unit === 'week' ? '주(월요일)' : '월'}</th>
                {GRADES.map((g) => (
                  <th key={g} className="text-right font-normal px-2">
                    {g}
                  </th>
                ))}
                <th className="text-right font-normal px-2">표본</th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((m) => (
                <tr key={m.period} className="border-t border-(--color-border)">
                  <td className="px-2 py-1 tabular-nums text-(--color-text)">{m.period}</td>
                  {GRADES.map((g) => {
                    const s = m.grades[g]
                    return (
                      <td key={g} className={`px-2 text-right tabular-nums ${s && s.n >= MIN_N ? 'text-(--color-text)' : 'text-(--color-muted)'}`}>
                        {s ? `${s.median.toLocaleString()} (${s.n})` : '—'}
                      </td>
                    )
                  })}
                  <td className="px-2 text-right tabular-nums text-(--color-muted)">{m.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-(--color-text)">일별 기록 — 그날의 현재 단가표</h3>
        <p className="text-[11px] text-(--color-muted) mb-1">
          크롤이 돌 때마다 한 줄씩 남깁니다(같은 날은 마지막 값). 지난날의 시장은 다시 계산할 수 없어서 저장합니다 · 기록{' '}
          {history.length}일치
        </p>
        <div className="overflow-x-auto max-h-72">
          <table className="w-full text-xs">
            <thead className="text-(--color-muted) sticky top-0 bg-(--color-panel)">
              <tr>
                <th className="text-left font-normal px-2 py-1">날짜</th>
                {GRADES.map((g) => (
                  <th key={g} className="text-right font-normal px-2">
                    {g}
                  </th>
                ))}
                <th className="text-right font-normal px-2">SI 고급</th>
                <th className="text-right font-normal px-2">SM 고급</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((h) => (
                <tr key={h.date} className="border-t border-(--color-border)">
                  <td className="px-2 py-1 tabular-nums text-(--color-text)">{h.date}</td>
                  {GRADES.map((g) => {
                    const s = h.cells[g]?.['전체']
                    return (
                      <td key={g} className="px-2 text-right tabular-nums text-(--color-text)">
                        {s ? `${s.median.toLocaleString()} (${s.n})` : '—'}
                      </td>
                    )
                  })}
                  {(['SI', 'SM'] as const).map((c) => {
                    const s = h.cells['고급']?.[c]
                    return (
                      <td key={c} className="px-2 text-right tabular-nums text-(--color-muted)">
                        {s ? `${s.median.toLocaleString()} (${s.n})` : '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
