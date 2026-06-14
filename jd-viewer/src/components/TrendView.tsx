import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useTrends } from '../lib/useTrends'
import { useTechRelations } from '../lib/useTechRelations'
import { Loader, ErrorState } from './ui'
import type { TechRelation, TrendDay } from '../types'

const PALETTE = ['#6ee7b7', '#93c5fd', '#fca5a5', '#fcd34d', '#c4b5fd', '#f9a8d4', '#5eead4', '#fdba74']

function pct(d: TrendDay, t: string): number {
  return d.total ? Math.round((1000 * (d.tech[t] ?? 0)) / d.total) / 10 : 0
}

export function TrendView() {
  const { data, loading, error } = useTrends()
  const { data: rel } = useTechRelations()
  const [mode, setMode] = useState<'trend' | 'relations'>('trend')
  const [picked, setPicked] = useState<string[]>([])
  const [relTech, setRelTech] = useState<string | null>(null)

  const latest = data?.days[data.days.length - 1]
  const ranking = useMemo(() => {
    if (!latest) return []
    return (data?.tracked ?? [])
      .map((t) => ({ tech: t, count: latest.tech[t] ?? 0, pct: pct(latest, t) }))
      .sort((a, b) => b.count - a.count)
  }, [data, latest])

  const relByName = useMemo(() => {
    const m = new Map<string, TechRelation>()
    for (const t of rel?.techs ?? []) m.set(t.name, t)
    return m
  }, [rel])

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
    if (mode === 'relations') { setRelTech(t); return }
    const base = selected
    setPicked(base.includes(t) ? base.filter((x) => x !== t) : [...base, t])
  }
  const maxPct = Math.max(...ranking.map((r) => r.pct), 1)
  const activeTech = relTech ?? ranking[0]?.tech
  const detail = activeTech ? relByName.get(activeTech) : undefined

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      {/* 모드 전환 */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60">
        <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden">
          <ModeBtn active={mode === 'trend'} onClick={() => setMode('trend')}>수요 추이</ModeBtn>
          <ModeBtn active={mode === 'relations'} onClick={() => setMode('relations')}>기술 관계·맥락</ModeBtn>
        </div>
        <span className="text-xs text-(--color-muted)">
          {mode === 'trend' ? '시간에 따른 기술 수요 변화(비중%)' : '함께 쓰이는 기술(스택 레이어)과 어디서·왜 쓰이는지'}
        </span>
      </div>

      <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-y-auto md:overflow-hidden">
        {/* 좌: 현재 수요 순위 (공유) */}
        <aside className="w-full md:w-80 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-4">
          <h3 className="text-sm font-semibold text-(--color-text)">현재 기술 수요</h3>
          <p className="text-xs text-(--color-muted) mb-3">
            {latest.date} · 공고 {latest.total.toLocaleString()}건 중 언급 비중.{' '}
            {mode === 'trend' ? '클릭=그래프 추가/제거' : '클릭=관계·맥락 보기'}
          </p>
          <ul className="flex flex-col gap-1">
            {ranking.slice(0, 28).map((r, i) => {
              const on = mode === 'trend' ? selected.includes(r.tech) : r.tech === activeTech
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

        {/* 우: 모드별 본문 */}
        {mode === 'trend' ? (
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
                    <Tooltip contentStyle={{ background: 'var(--color-panel)', border: '1px solid var(--color-border)', borderRadius: 8, fontSize: 12 }} labelStyle={{ color: 'var(--color-text)' }} />
                    {selected.map((t, i) => (
                      <Line key={t} type="monotone" dataKey={t} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {selected.map((t, i) => (
                  <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border border-(--color-border)">
                    <span className="w-2 h-2 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />{t}
                  </span>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <MoverCard title="📈 비중 상승" movers={data.movers.up} up />
              <MoverCard title="📉 비중 하락" movers={data.movers.down} />
            </div>
            <p className="text-[11px] text-(--color-muted) leading-relaxed">
              ※ 크롤 스냅샷을 날짜별 집계. 트렌드는 크롤 규모 영향을 줄이려 '비중(%)'으로 봅니다. 현재 {data.span.days}일치라
              신호가 약하며, 데이터가 매일 자동으로 쌓일수록 추세가 또렷해집니다.
            </p>
          </main>
        ) : (
          <main className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5 flex flex-col gap-5">
            {detail ? <RelationDetail t={detail} /> : <p className="text-(--color-muted)">관계 데이터를 불러오는 중…</p>}
            {rel?.domains && rel.domains.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-(--color-text) mb-1">도메인별 인사이트</h2>
                <p className="text-xs text-(--color-muted) mb-3">어떤 산업·도메인에서 어떤 기술을 왜 쓰는지</p>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {rel.domains.map((d) => (
                    <div key={d.domain} className="rounded border border-(--color-border) bg-(--color-bg) p-3">
                      <div className="text-sm font-semibold text-(--color-text) mb-1">{d.domain}</div>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {d.techs.map((t) => (
                          <span key={t} className="px-1.5 py-0.5 text-[11px] rounded bg-(--color-accent)/15 text-(--color-accent)">{t}</span>
                        ))}
                      </div>
                      <div className="blog-md text-sm text-(--color-text)">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.why}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </main>
        )}
      </div>
    </div>
  )
}

function RelationDetail({ t }: { t: TechRelation }) {
  // 함께 쓰는 기술을 레이어별로 묶기
  const byLayer = useMemo(() => {
    const m = new Map<string, typeof t.related>()
    for (const r of t.related) {
      if (!m.has(r.layer)) m.set(r.layer, [])
      m.get(r.layer)!.push(r)
    }
    return [...m.entries()]
  }, [t])

  return (
    <div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="text-xl font-semibold text-(--color-text)">{t.name}</h2>
        <span className="text-xs px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)">{t.layer}</span>
        <span className="text-xs text-(--color-muted)">전체 공고의 {t.pct_jobs}% · {t.count.toLocaleString()}건</span>
      </div>

      {t.context && (
        <div className="blog-md mt-2 text-sm text-(--color-text)">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.context}</ReactMarkdown>
        </div>
      )}

      <div className="mt-4">
        <div className="text-xs font-medium text-(--color-muted) mb-2">함께 쓰이는 기술 (스택 레이어별 · {t.name} 공고 중 비율)</div>
        <div className="flex flex-col gap-2">
          {byLayer.map(([layer, items]) => (
            <div key={layer} className="flex gap-3">
              <div className="w-24 shrink-0 text-xs text-(--color-muted) pt-1">{layer}</div>
              <div className="flex flex-wrap gap-1.5">
                {items.map((r) => (
                  <span key={r.name} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border border-(--color-border) bg-(--color-bg) text-(--color-text)">
                    {r.name}<span className="text-(--color-muted)">{r.pct}%</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ModeBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`px-3 py-1 text-xs font-medium transition ${active ? 'bg-(--color-accent) text-black' : 'bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'}`}>
      {children}
    </button>
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
