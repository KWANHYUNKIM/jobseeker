import { useMemo, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useTrends } from '../lib/useTrends'
import { Loader, ErrorState } from './ui'
import type { TrendDay } from '../types'

const PALETTE = ['#6ee7b7', '#93c5fd', '#fca5a5', '#fcd34d', '#c4b5fd', '#f9a8d4', '#5eead4', '#fdba74']

function pct(d: TrendDay, t: string): number {
  return d.total ? Math.round((1000 * (d.tech[t] ?? 0)) / d.total) / 10 : 0
}

export function TrendView() {
  const { data, loading, error } = useTrends()
  const [picked, setPicked] = useState<string[]>([])

  const latest = data?.days[data.days.length - 1]
  // 현재 수요 순위(최신일, 비중 내림차순)
  const ranking = useMemo(() => {
    if (!latest) return []
    return (data?.tracked ?? [])
      .map((t) => ({ tech: t, count: latest.tech[t] ?? 0, pct: pct(latest, t) }))
      .sort((a, b) => b.count - a.count)
  }, [data, latest])

  // 기본 선택: 상위 5개
  const selected = picked.length ? picked : ranking.slice(0, 5).map((r) => r.tech)

  const chartData = useMemo(() => {
    return (data?.days ?? []).map((d) => {
      const row: Record<string, number | string> = { date: d.date.slice(5) }
      for (const t of selected) row[t] = pct(d, t)
      return row
    })
  }, [data, selected])

  if (loading) return <Loader label="개발 트렌드 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="trends.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python bin/build_trends.py</code> (jd-viewer)</>}
      />
    )
  if (!data || !latest) return <div className="p-8 text-(--color-muted)">트렌드 데이터가 없습니다.</div>

  const toggle = (t: string) => {
    const base = selected
    setPicked(base.includes(t) ? base.filter((x) => x !== t) : [...base, t])
  }
  const maxPct = Math.max(...ranking.map((r) => r.pct), 1)

  return (
    <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-y-auto md:overflow-hidden">
      {/* 좌: 현재 수요 순위 */}
      <aside className="w-full md:w-80 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-4">
        <h3 className="text-sm font-semibold text-(--color-text)">현재 기술 수요</h3>
        <p className="text-xs text-(--color-muted) mb-3">
          {latest.date} 기준 · 공고 {latest.total.toLocaleString()}건 중 언급 비중. 클릭하면 추이 그래프에 추가/제거.
        </p>
        <ul className="flex flex-col gap-1">
          {ranking.slice(0, 24).map((r, i) => {
            const on = selected.includes(r.tech)
            return (
              <li key={r.tech}>
                <button
                  onClick={() => toggle(r.tech)}
                  className={`w-full flex items-center gap-2 px-2 py-1 rounded text-left ${on ? 'bg-(--color-accent)/15' : 'hover:bg-(--color-bg)'}`}
                >
                  <span className="w-5 text-xs text-(--color-muted) tabular-nums">{i + 1}</span>
                  <span className="w-28 text-sm text-(--color-text) truncate">{r.tech}</span>
                  <span className="flex-1 h-1.5 rounded bg-(--color-bg) overflow-hidden">
                    <span className="block h-full bg-(--color-accent)" style={{ width: `${(r.pct / maxPct) * 100}%` }} />
                  </span>
                  <span className="w-10 text-right text-xs text-(--color-muted) tabular-nums">{r.pct}%</span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      {/* 우: 추이 + 급변동 */}
      <main className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5 flex flex-col gap-4">
        <div>
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-lg font-semibold text-(--color-text)">기술 수요 추이</h2>
            <span className="text-xs text-(--color-muted)">
              {data.span.from} ~ {data.span.to} · {data.span.days}일 · 공고 중 언급 비중(%)
            </span>
          </div>
          <div className="mt-2 rounded border border-(--color-border) bg-(--color-bg) p-3" style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--color-muted)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-muted)' }} unit="%" width={42} />
                <Tooltip
                  contentStyle={{ background: 'var(--color-panel)', border: '1px solid var(--color-border)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: 'var(--color-text)' }}
                />
                {selected.map((t, i) => (
                  <Line key={t} type="monotone" dataKey={t} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {selected.map((t, i) => (
              <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border border-(--color-border)">
                <span className="w-2 h-2 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
                {t}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <MoverCard title="📈 비중 상승" movers={data.movers.up} up />
          <MoverCard title="📉 비중 하락" movers={data.movers.down} />
        </div>

        <p className="text-[11px] text-(--color-muted) leading-relaxed">
          ※ 채용 사이트 크롤 스냅샷을 날짜별로 집계한 결과입니다. 트렌드는 크롤 규모 변화의 영향을 줄이기 위해
          '전체 공고 중 해당 기술 언급 비중(%)'으로 봅니다. 현재는 {data.span.days}일치라 신호가 약하며,
          데이터가 매일 자동으로 쌓일수록(크롤 오케스트레이션에 연결됨) 추세가 또렷해집니다.
        </p>
      </main>
    </div>
  )
}

function MoverCard({ title, movers, up }: { title: string; movers: { tech: string; from_pct: number; to_pct: number; delta: number }[]; up?: boolean }) {
  return (
    <div className="rounded border border-(--color-border) bg-(--color-bg) p-3">
      <div className="text-xs font-medium text-(--color-muted) mb-2">{title}</div>
      {movers.length === 0 ? (
        <div className="text-xs text-(--color-muted)">변동 없음</div>
      ) : (
        <ul className="flex flex-col gap-1">
          {movers.map((m) => (
            <li key={m.tech} className="flex items-center gap-2 text-sm">
              <span className="flex-1 text-(--color-text) truncate">{m.tech}</span>
              <span className="text-xs text-(--color-muted) tabular-nums">{m.from_pct}% → {m.to_pct}%</span>
              <span className={`w-14 text-right text-xs font-medium tabular-nums ${up ? 'text-(--color-accent)' : 'text-amber-400'}`}>
                {m.delta > 0 ? '+' : ''}{m.delta}%p
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
