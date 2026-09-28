import { useState } from 'react'
import { GRADES, type Analysis, type Grade, type RateSnapshot } from '../lib/freelance'

// 단가 추이 — 몸값이 어떻게 움직이나.
//
// 두 가지를 따로 본다.
//   · 월별: 그 달에 새로 올라온 자리의 '올라올 때 단가'(등급별 중앙값). 언제든 다시 셀 수 있다.
//   · 일별 기록: 크롤이 돌 때마다 남긴 그날의 현재 단가표. 지난 시장은 다시 셀 수 없어서 쌓는다.
// 등급은 순서가 있는 범주라 한 색의 명도로 가른다(초급 연함 → 특급 진함). 선 끝에 이름을 달고
// 범례도 둔다 — 색만으로 구분하지 않는다.

const SHADE: Record<Grade, number> = { 초급: 35, 중급: 55, 고급: 78, 특급: 100 }
const color = (g: Grade) => `color-mix(in srgb, var(--color-accent) ${SHADE[g]}%, var(--color-panel))`

type Month = NonNullable<Analysis['monthly']>[number]

function MonthlyChart({ months }: { months: Month[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 720
  const H = 220
  const pad = { l: 40, r: 56, t: 12, b: 26 }
  const vals = months.flatMap((m) => GRADES.map((g) => m.grades[g]?.median).filter((v): v is number => v != null))
  const lo = Math.max(0, Math.floor((Math.min(...vals) - 50) / 100) * 100)
  const hi = Math.ceil((Math.max(...vals) + 50) / 100) * 100
  const x = (i: number) => (months.length === 1 ? (pad.l + W - pad.r) / 2 : pad.l + (i * (W - pad.l - pad.r)) / (months.length - 1))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (v - lo) / (hi - lo || 1))
  const ticks = [lo, Math.round((lo + hi) / 2 / 50) * 50, hi]
  const hm = hover != null ? months[hover] : null

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
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="월별 등급 월 단가 중앙값">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--color-border)" />
            <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="var(--color-muted)">
              {t}
            </text>
          </g>
        ))}
        {months.map((m, i) => (
          <text key={m.month} x={x(i)} y={H - 8} textAnchor="middle" fontSize={10} fill="var(--color-muted)">
            {m.month}
          </text>
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} stroke="var(--color-muted)" strokeDasharray="3 3" />}
        {GRADES.map((g) => {
          const pts = months.map((m, i) => [i, m.grades[g]?.median] as const).filter((p): p is readonly [number, number] => p[1] != null)
          if (!pts.length) return null
          const last = pts[pts.length - 1]
          return (
            <g key={g}>
              <polyline
                points={pts.map(([i, v]) => `${x(i)},${y(v)}`).join(' ')}
                fill="none"
                stroke={color(g)}
                strokeWidth={2}
                strokeLinejoin="round"
              />
              {pts.map(([i, v]) => (
                <circle key={i} cx={x(i)} cy={y(v)} r={4} fill={color(g)} stroke="var(--color-panel)" strokeWidth={2} />
              ))}
              <text x={x(last[0]) + 8} y={y(last[1]) + 3} fontSize={10} fill="var(--color-text)">
                {g}
              </text>
            </g>
          )
        })}
        {months.map((m, i) => (
          <rect
            key={m.month}
            x={x(i) - (W - pad.l - pad.r) / Math.max(1, months.length) / 2}
            y={pad.t}
            width={(W - pad.l - pad.r) / Math.max(1, months.length)}
            height={H - pad.t - pad.b}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      {hm && (
        <div className="absolute top-6 right-0 text-[11px] rounded border border-(--color-border) bg-(--color-panel) px-2 py-1 shadow-sm">
          <b className="text-(--color-text)">{hm.month}</b> · {hm.n}건
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

const MIN_N = 3

export function RateTrend({ months, history }: { months: Month[]; history: RateSnapshot[] }) {
  const recent = [...history].reverse().slice(0, 30)
  // 그래프에는 표본 3건 이상인 점만 올린다. 1건짜리 달을 이으면 '초급이 575→425 로 떨어졌다'
  // 같은 없는 추세가 생긴다. 표에는 모든 달을 건수와 함께 그대로 둔다.
  const plotted = months
    .map((m) => ({
      ...m,
      grades: Object.fromEntries(
        Object.entries(m.grades).filter(([, s]) => s && s.n >= MIN_N),
      ) as Month['grades'],
    }))
    .filter((m) => Object.keys(m.grades).length > 0)
  return (
    <div className="flex flex-col gap-5">
      <section>
        <h3 className="text-sm font-semibold text-(--color-text)">월별 — 그 달에 올라온 자리의 등급별 월 단가 중앙값</h3>
        {plotted.length < 2 ? (
          <p className="text-xs text-(--color-muted) mt-1">
            표본 {MIN_N}건 이상인 달이 아직 {plotted.length}개월뿐이라 선을 긋지 않았습니다. 달이 쌓이면 이어집니다 — 아래
            표(모든 달, 괄호는 건수)와 일별 기록은 매 크롤마다 쌓입니다.
          </p>
        ) : (
          <MonthlyChart months={plotted} />
        )}
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-xs">
            <thead className="text-(--color-muted)">
              <tr>
                <th className="text-left font-normal px-2 py-1">월</th>
                {GRADES.map((g) => (
                  <th key={g} className="text-right font-normal px-2">
                    {g}
                  </th>
                ))}
                <th className="text-right font-normal px-2">표본</th>
              </tr>
            </thead>
            <tbody>
              {[...months].reverse().map((m) => (
                <tr key={m.month} className="border-t border-(--color-border)">
                  <td className="px-2 py-1 tabular-nums text-(--color-text)">{m.month}</td>
                  {GRADES.map((g) => {
                    const s = m.grades[g]
                    return (
                      <td key={g} className={`px-2 text-right tabular-nums ${s && s.n >= 3 ? 'text-(--color-text)' : 'text-(--color-muted)'}`}>
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
        <h3 className="text-sm font-semibold text-(--color-text)">일별 기록 — 그날의 현재 단가표(전체 열)</h3>
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
