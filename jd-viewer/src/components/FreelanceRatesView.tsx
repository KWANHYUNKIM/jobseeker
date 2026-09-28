import { useState } from 'react'
import {
  GRADES,
  SITE_KO,
  useFreelance,
  type Analysis,
  type Grade,
  type MatrixRow,
  type Stat,
  type Trend,
} from '../lib/freelance'
import { FreelanceNav } from './FreelanceNav'
import { CurrentRateTable } from './FreelanceRateTable'
import { RateTrend } from './FreelanceRateTrend'
import { ErrorState, Loader } from './ui'

// 외주·프리 단가 분석 — 몸값은 중간값 하나로 말할 수 없다.
//
// SI/SM 시장은 등급(초급·중급·고급·특급)으로 단가를 부르고, 같은 등급이어도 어떤 프로젝트냐
// (금융 차세대인지 공공 유지보수인지, 백엔드인지 PM 인지)에 따라 값이 갈린다. 그래서 등급을
// 먼저 가르고 그 안을 유형·분야·직무로 다시 가른다. 숫자는 catch_capture/pipeline/freelance_rates.py
// 가 미리 세어 freelance.json 의 analysis 에 실어 둔다 — 이 화면은 그리기만 한다.

const MIN_N = 3 // 이보다 적은 칸은 흐리게 — 한두 건으로 '분야 단가'를 말하면 거짓말이 된다

function fmt(n: number | null | undefined): string {
  return n == null ? '—' : n.toLocaleString()
}

// ── 등급별 분포: 가운데 절반(띠) + 최저~최고(가는 선) + 중앙값(점) ─────────────
function GradeRanges({ a }: { a: Analysis }) {
  const rows = GRADES.map((g) => ({ g, s: a.grades[g], ex: a.grades_explicit[g] }))
  const hi = Math.max(1, ...rows.map((r) => r.s?.max ?? 0))
  const lo = Math.min(...rows.filter((r) => r.s).map((r) => r.s!.min), hi)
  const scaleLo = Math.max(0, Math.floor((lo - 50) / 100) * 100)
  const scaleHi = Math.ceil((hi + 50) / 100) * 100
  const x = (v: number) => ((v - scaleLo) / (scaleHi - scaleLo)) * 100
  const ticks: number[] = []
  for (let t = scaleLo; t <= scaleHi; t += scaleHi - scaleLo > 800 ? 200 : 100) ticks.push(t)

  return (
    <div className="flex flex-col gap-3">
      {rows.map(({ g, s, ex }) => (
        <div key={g} className="grid grid-cols-[3.5rem_minmax(0,1fr)_13rem] items-center gap-3">
          <div className="text-sm font-semibold text-(--color-text)">{g}</div>
          <div className="relative h-7" title={s ? `${g}: 가운데 절반 ${s.p25}~${s.p75}만원, 중앙값 ${s.median}만원` : ''}>
            {ticks.map((t) => (
              <div key={t} className="absolute top-0 bottom-0 w-px bg-(--color-border)" style={{ left: `${x(t)}%` }} />
            ))}
            {s && (
              <>
                <div
                  className="absolute top-1/2 h-px bg-(--color-muted)"
                  style={{ left: `${x(s.min)}%`, width: `${x(s.max) - x(s.min)}%` }}
                />
                <div
                  className="absolute top-1.5 bottom-1.5 rounded bg-(--color-accent)/35"
                  style={{ left: `${x(s.p25)}%`, width: `${Math.max(0.8, x(s.p75) - x(s.p25))}%` }}
                />
                <div
                  className="absolute top-1/2 w-3 h-3 -mt-1.5 -ml-1.5 rounded-full bg-(--color-accent) ring-2 ring-(--color-panel)"
                  style={{ left: `${x(s.median)}%` }}
                />
              </>
            )}
          </div>
          <div className="text-xs text-(--color-muted) tabular-nums">
            {s ? (
              <>
                <b className="text-(--color-text) text-sm">{fmt(s.median)}만원</b> · {fmt(s.p25)}~{fmt(s.p75)}
                <div>
                  {s.n}건 (표기 {ex?.n ?? 0} · 추정 {s.n - (ex?.n ?? 0)})
                  {s.n < MIN_N && ' · 표본 부족'}
                </div>
              </>
            ) : (
              '자료 없음'
            )}
          </div>
        </div>
      ))}
      <div className="grid grid-cols-[3.5rem_minmax(0,1fr)_13rem] gap-3">
        <div />
        <div className="relative h-4 text-[10px] text-(--color-muted)">
          {ticks.map((t) => (
            <span key={t} className="absolute -translate-x-1/2 tabular-nums" style={{ left: `${x(t)}%` }}>
              {t}
            </span>
          ))}
        </div>
        <div className="text-[10px] text-(--color-muted)">월 단가(만원)</div>
      </div>
      <p className="text-[11px] text-(--color-muted)">
        진한 점 = 중앙값 · 연한 띠 = 가운데 절반(하위 25%~상위 25%) · 가는 선 = 최저~최고
      </p>
    </div>
  )
}

// ── 행 × 등급 표 — 칸의 진하기는 중앙값(한 가지 색, 연함→진함) ──────────────────
function Matrix({ rows, label }: { rows: MatrixRow[]; label: string }) {
  const vals = rows.flatMap((r) => GRADES.map((g) => r.grades[g]).filter((s): s is Stat => !!s && s.n >= MIN_N))
  const lo = Math.min(...vals.map((s) => s.median))
  const hi = Math.max(...vals.map((s) => s.median))
  const tint = (s: Stat) => (hi > lo ? 0.08 + ((s.median - lo) / (hi - lo)) * 0.42 : 0.2)

  if (!rows.length) return <p className="text-xs text-(--color-muted)">자료가 아직 없습니다.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-separate border-spacing-0.5">
        <thead>
          <tr className="text-(--color-muted)">
            <th className="text-left font-normal px-2">{label}</th>
            {GRADES.map((g) => (
              <th key={g} className="font-normal px-2 text-center">
                {g}
              </th>
            ))}
            <th className="font-normal px-2 text-center">전체</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="px-2 py-1 text-(--color-text) whitespace-nowrap">{r.key}</td>
              {GRADES.map((g: Grade) => {
                const s = r.grades[g]
                if (!s) return <td key={g} className="text-center text-(--color-muted)/50">·</td>
                const weak = s.n < MIN_N
                return (
                  <td
                    key={g}
                    className="text-center rounded px-2 py-1 tabular-nums"
                    style={weak ? undefined : { background: `color-mix(in srgb, var(--color-accent) ${Math.round(tint(s) * 100)}%, transparent)` }}
                    title={`${r.key} · ${g}: 중앙값 ${s.median}만원, ${s.p25}~${s.p75}, ${s.n}건`}
                  >
                    <div className={weak ? 'text-(--color-muted)' : 'text-(--color-text) font-semibold'}>{fmt(s.median)}</div>
                    <div className="text-[10px] text-(--color-muted)">{s.n}건</div>
                  </td>
                )
              })}
              <td className="text-center px-2 py-1 tabular-nums border-l border-(--color-border)">
                <div className="text-(--color-text)">{fmt(r.total.median)}</div>
                <div className="text-[10px] text-(--color-muted)">{r.total.n}건</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── 단가 추이 — 주별 상주 월 단가 중앙값(막대) + 기술별 단가 표 + 단가를 바꾼 프로젝트 ──
function TrendPanel({ trend }: { trend: Trend }) {
  const [hover, setHover] = useState<number | null>(null)
  const weeks = trend.weekly.filter((w) => w.onsite != null)
  const max = Math.max(1, ...weeks.map((w) => w.onsite ?? 0))
  const W = 560
  const H = 150
  const pad = { l: 36, r: 8, t: 10, b: 22 }
  const bw = weeks.length ? (W - pad.l - pad.r) / weeks.length : 0
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max)
  const ticks = [0, Math.round(max / 2), Math.round(max)]
  const hv = hover != null ? weeks[hover] : null

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <section>
        <h3 className="text-sm font-semibold text-(--color-text)">상주 프로젝트 월 단가 중앙값 (주별, 만원)</h3>
        <p className="text-[11px] text-(--color-muted) mb-1">
          그 주에 새로 올라온 자리의 <b>올라올 때 단가</b>로 셉니다. 나중에 내린 값은 오른쪽 목록에서 따로 봅니다.
        </p>
        {weeks.length === 0 ? (
          <p className="text-xs text-(--color-muted)">아직 주별로 셀 만큼 쌓이지 않았습니다. 사이클이 돌수록 채워집니다.</p>
        ) : (
          <div className="relative">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="주별 상주 월 단가 중앙값">
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--color-border)" strokeWidth={1} />
                  <text x={pad.l - 4} y={y(t) + 3} textAnchor="end" fontSize={9} fill="var(--color-muted)">
                    {t}
                  </text>
                </g>
              ))}
              {weeks.map((w, i) => {
                const v = w.onsite ?? 0
                const x = pad.l + i * bw + 1
                const top = y(v)
                const h = H - pad.b - top
                const r = Math.min(4, (bw - 2) / 2, h)
                return (
                  <g key={w.week} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                    {/* 막대보다 넓은 히트 영역 */}
                    <rect x={pad.l + i * bw} y={pad.t} width={bw} height={H - pad.t - pad.b} fill="transparent" />
                    <path
                      d={`M${x},${H - pad.b} V${top + r} Q${x},${top} ${x + r},${top} H${x + bw - 2 - r} Q${x + bw - 2},${top} ${x + bw - 2},${top + r} V${H - pad.b} Z`}
                      fill="var(--color-accent)"
                      opacity={hover == null || hover === i ? 1 : 0.45}
                    />
                    {(i === 0 || i === weeks.length - 1 || i % 4 === 0) && (
                      <text x={x + (bw - 2) / 2} y={H - 8} textAnchor="middle" fontSize={9} fill="var(--color-muted)">
                        {w.week.slice(5)}
                      </text>
                    )}
                  </g>
                )
              })}
            </svg>
            {hv && (
              <div className="absolute top-0 right-0 text-[11px] rounded border border-(--color-border) bg-(--color-panel) px-2 py-1 shadow-sm">
                <b className="text-(--color-text)">{hv.week} 주</b>
                <div className="text-(--color-muted)">
                  상주 {hv.onsite?.toLocaleString()}만원 · 전체 {hv.median?.toLocaleString()}만원 · {hv.n}건
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 min-w-0">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-(--color-text) mb-1">기술별 월 단가 (모집중)</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-(--color-muted)">
                <th className="text-left font-normal">기술</th>
                <th className="text-right font-normal">중앙값</th>
                <th className="text-right font-normal">범위</th>
                <th className="text-right font-normal">건</th>
              </tr>
            </thead>
            <tbody>
              {trend.by_skill.slice(0, 10).map((s) => (
                <tr key={s.skill} className="border-t border-(--color-border)">
                  <td className="py-0.5 text-(--color-text)">{s.skill}</td>
                  <td className="text-right tabular-nums text-(--color-text)">{Math.round(s.median).toLocaleString()}</td>
                  <td className="text-right tabular-nums text-(--color-muted)">
                    {Math.round(s.min)}~{Math.round(s.max)}
                  </td>
                  <td className="text-right tabular-nums text-(--color-muted)">{s.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-(--color-text) mb-1">올라온 뒤 단가를 바꾼 프로젝트</h3>
          {trend.budget_moves.length === 0 ? (
            <p className="text-xs text-(--color-muted)">
              아직 없습니다. 같은 프로젝트의 단가가 사이클 사이에 바뀌면 여기에 쌓입니다.
            </p>
          ) : (
            <ul className="text-xs flex flex-col gap-1">
              {trend.budget_moves.slice(0, 8).map((m) => (
                <li key={m.id} className="flex gap-2">
                  <span className="truncate flex-1 text-(--color-text)">{m.title}</span>
                  <span className="tabular-nums text-(--color-muted) shrink-0">
                    {m.from}→{m.to}
                  </span>
                  <span className={`tabular-nums shrink-0 ${m.pct < 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {m.pct > 0 ? '+' : ''}
                    {m.pct}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function Card({ title, sub, children, className = '' }: { title: string; sub?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-(--color-border) bg-(--color-panel) p-4 ${className}`}>
      <h2 className="text-sm font-semibold text-(--color-text)">{title}</h2>
      {sub && <p className="text-[11px] text-(--color-muted) mt-0.5 mb-3">{sub}</p>}
      {!sub && <div className="mb-3" />}
      {children}
    </section>
  )
}

export function FreelanceRatesView() {
  const { data, loading, error } = useFreelance()
  if (loading) return <Loader label="단가 분석 불러오는 중…" />
  if (error || !data)
    return <ErrorState title="freelance.json 로드 실패" detail={error ?? ''} />
  const a = data.analysis
  if (!a)
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <FreelanceNav current="rates" />
        <div className="p-8 text-sm text-(--color-muted)">
          아직 분석이 없습니다. 크롤러가 한 번 더 돌면 채워집니다(<code>python -m crawlers.crawl_freelance</code>).
        </div>
      </div>
    )
  const m = a.meta

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      <FreelanceNav current="rates" />
      <main data-scroll className="flex-1 min-h-0 overflow-auto jd-panel">
        <div className="max-w-[1600px] mx-auto p-4 flex flex-col gap-4">
          <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h1 className="text-lg font-bold text-(--color-text)">외주·프리 단가 분석</h1>
            <span className="text-xs text-(--color-muted)">
              월 단가 있는 프로젝트 {m.monthly.toLocaleString()}건 · 등급 확인 {m.graded.toLocaleString()}건 ·{' '}
              {Object.entries(m.sites)
                .map(([s, n]) => `${SITE_KO[s] ?? s} ${n}`)
                .join(' · ')}
            </span>
            <span className="text-xs text-(--color-muted) ml-auto">갱신 {data.updated_at.slice(0, 16).replace('T', ' ')}</span>
          </header>

          {a.current && (
            <Card
              title="현재 단가표 (월 단가, 만원)"
              sub="칸을 누르면 그 숫자를 만든 프로젝트가 아래에 나옵니다 — 원문 링크와 등급을 어떻게 정했는지까지. CSV 로 내려받아 직접 다시 셀 수 있습니다."
            >
              <CurrentRateTable cur={a.current} projects={data.projects} />
            </Card>
          )}

          <Card title="요약" sub="아래 표에서 읽어 낸 것. 표본이 3건 미만인 칸은 문장에 쓰지 않았습니다.">
            <ul className="flex flex-col gap-1.5 text-sm text-(--color-text) list-disc pl-5">
              {a.insights.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </Card>

          <Card title="추이" sub="몸값이 어떻게 움직이는지 — 월별(그 달에 올라온 자리)과 일별 기록(그날의 단가표).">
            <RateTrend months={a.monthly ?? []} history={data.rate_history ?? []} />
          </Card>

          <Card
            title="등급별 월 단가"
            sub="SI/SM 시장은 등급으로 단가를 부릅니다. 등급마다 값이 어디에 몰려 있고 얼마나 퍼져 있는지 봅니다."
          >
            <GradeRanges a={a} />
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="프로젝트 유형 × 등급" sub="SI = 구축·차세대·고도화, SM = 운영·유지보수. 제목에 적힌 말로 가릅니다.">
              <Matrix rows={a.by_type} label="유형" />
            </Card>
            <Card title="근무 형태 × 등급" sub="월 단가는 대부분 상주 프로젝트에서 나옵니다.">
              <Matrix rows={a.by_mode} label="근무" />
            </Card>
          </div>

          <Card title="분야 × 등급" sub="제목·본문의 고객사 표현(은행·카드·공단·MES…)으로 가릅니다. 칸이 진할수록 비쌉니다.">
            <Matrix rows={a.by_domain} label="분야" />
          </Card>

          <Card title="직무 × 등급" sub="제목 → 원본 직무 분류 → 기술 순으로 가릅니다.">
            <Matrix rows={a.by_role} label="직무" />
          </Card>

          {data.trend && (
            <Card title="흐름" sub="주별 추이와 기술별 단가, 그리고 올라온 뒤 단가를 바꾼 프로젝트.">
              <TrendPanel trend={data.trend} />
            </Card>
          )}

          <Card title="읽는 법">
            <ul className="text-xs text-(--color-muted) flex flex-col gap-1 list-disc pl-5">
              <li>
                <b>월 단가만</b> 비교합니다. 도급 총액은 기간이 제각각이라 같은 줄에 놓지 않습니다.
              </li>
              <li>
                <b>올라올 때 단가</b>로 셉니다. 나중에 내린 값은 '흐름'의 단가 변경 목록에서 따로 봅니다.
              </li>
              <li>
                등급은 원본에 적힌 표기가 우선이고, 없으면 경력으로 추정합니다 — 초급 3년 미만, 중급 3~6년, 고급
                7~9년, 특급 10년 이상. 시장에서 흔히 쓰는 구분이며 공식 기준(KOSA)은 학력·자격에 따라 다릅니다.
                지금 표기 {m.explicit}건 · 추정 {m.inferred}건입니다.
              </li>
              <li>
                '중급고급'처럼 여러 등급이 함께 적힌 {m.mixed}건과 등급을 알 수 없는 {m.ungraded}건은 등급 표에서
                뺐습니다.
              </li>
              <li>표본이 {MIN_N}건 미만인 칸은 흐리게 두었습니다 — 참고만 하세요.</li>
            </ul>
          </Card>
        </div>
      </main>
    </div>
  )
}
