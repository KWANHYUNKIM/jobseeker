import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { TechIcon } from '../../../components/ui'
import type { TechRelation, TechRelationsFile, TrendsFile } from '../../../types'

/** 스택 레이어 색 — 캐치형 20 보드의 값. 모르는 레이어는 회색. */
const LAYER_COLOR: Record<string, string> = {
  백엔드: '#f45757',
  '인프라/클라우드': '#4f7cf0',
  언어: '#8b5cf6',
  '협업/도구': '#64748b',
  데이터베이스: '#f2a93b',
  프론트엔드: '#2bb673',
  모바일: '#0ea5e9',
  데이터: '#14b8a6',
  'AI/ML': '#e05fb4',
}
const colorOf = (layer: string) => LAYER_COLOR[layer] ?? '#94a3b8'

/**
 * 기술 관계·맥락(캐치형 20) — 왼쪽 현재 기술 수요 순위(공고 중 언급 비중), 오른쪽 고른 기술의 검은 띠,
 * 함께 쓰이는 기술(스택 레이어별 카드), 그 기술을 가운데 둔 스택 지도, 맥락·도메인 인사이트.
 */
export function RelationsView({ data, rel }: { data: TrendsFile; rel: TechRelationsFile | null }) {
  const [pick, setPick] = useState<string | null>(null)
  const latest = data.days[data.days.length - 1]
  const ranking = useMemo(() => {
    if (!latest) return []
    const pct = (t: string) => (latest.total ? Math.round((1000 * (latest.tech[t] ?? 0)) / latest.total) / 10 : 0)
    return data.tracked
      .map((t) => ({ tech: t, count: latest.tech[t] ?? 0, pct: pct(t) }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20)
  }, [data, latest])
  const byName = useMemo(() => new Map((rel?.techs ?? []).map((t) => [t.name, t])), [rel])
  const active = pick ?? ranking[0]?.tech
  const t = active ? byName.get(active) : undefined
  const maxPct = Math.max(...ranking.map((r) => r.pct), 1)

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)] items-start">
      <aside className="rounded-[30px] border border-[#e2e8ec] bg-white px-[21px] pt-[23px] pb-5">
        <h3 className="text-[17px] font-bold text-[#272727]">현재 기술 수요</h3>
        <p className="text-xs text-[#999]">
          {latest?.date} · 공고 {latest?.total.toLocaleString()}건 중 언급 비중
        </p>
        <ol className="mt-3 flex flex-col">
          {ranking.map((r, i) => {
            const on = r.tech === active
            return (
              <li key={r.tech}>
                <button
                  type="button"
                  onClick={() => setPick(r.tech)}
                  aria-pressed={on}
                  className={'w-full flex items-center gap-2 h-[38px] rounded-xl px-4 text-left ' + (on ? 'bg-(--color-accent-weak) shadow-[inset_0_0_0_1.5px_#f45757]' : 'hover:bg-[#f7f9fa]')}
                >
                  <span className={'w-4 text-sm font-bold tabular-nums ' + (i < 3 ? 'text-(--color-accent)' : 'text-[#999]')}>{i + 1}</span>
                  <span className="w-[100px] truncate text-sm font-medium text-[#272727]">{r.tech}</span>
                  <span className="flex-1 h-2.5 rounded-[5px] bg-[#f1f3f5] overflow-hidden">
                    <span className="block h-full rounded-[5px] bg-[#f67979]" style={{ width: `${(r.pct / maxPct) * 100}%` }} />
                  </span>
                  <span className="w-12 text-right text-[13px] font-bold text-[#272727] tabular-nums">{r.pct}%</span>
                </button>
              </li>
            )
          })}
        </ol>
      </aside>

      <main className="min-w-0 flex flex-col gap-6">
        {t ? <Detail t={t} /> : <p className="text-[#999]">관계 데이터를 불러오는 중…</p>}
        {rel?.domains && rel.domains.length > 0 && (
          <details className="rounded-[22px] bg-[#f7f9fa] px-6 py-5">
            <summary className="cursor-pointer text-[17px] font-bold text-[#272727]">도메인별 인사이트 — 어떤 산업에서 어떤 기술을 왜 쓰는지</summary>
            <div className="mt-4 grid lg:grid-cols-2 gap-3">
              {rel.domains.map((d) => (
                <div key={d.domain} className="rounded-2xl border border-[#e2e8ec] bg-white p-4">
                  <div className="text-[15px] font-bold text-[#272727]">{d.domain}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {d.techs.map((x) => (
                      <span key={x} className="inline-flex items-center gap-1 rounded bg-[#f4f4f4] px-1.5 text-xs leading-[22px] text-[#474747]">
                        <TechIcon tech={x} size={12} />
                        {x}
                      </span>
                    ))}
                  </div>
                  <div className="blog-md mt-2 text-sm text-[#474747]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.why}</ReactMarkdown>
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </main>
    </div>
  )
}

function Detail({ t }: { t: TechRelation }) {
  const byLayer = useMemo(() => {
    const m = new Map<string, TechRelation['related']>()
    for (const r of t.related) m.set(r.layer, [...(m.get(r.layer) ?? []), r])
    return [...m.entries()]
  }, [t])
  const ring = t.related.slice(0, 12)

  return (
    <>
      <section className="rounded-[26px] bg-[#272727] px-[30px] pt-[26px] pb-6 text-white">
        <div className="text-[13px] text-[#bbb]">선택한 기술 · {t.layer}</div>
        <h2 className="mt-0.5 text-[32px] font-bold leading-[47px]">{t.name}</h2>
        <p className="mt-1 text-[15px] text-[#ddd]">
          전체 공고의 <b className="font-bold text-[#ff9a9a]">{t.pct_jobs}%</b> · {t.count.toLocaleString()}건이 {t.name}를 요구해요
        </p>
        {t.context && (
          <div className="blog-md mt-3 text-sm text-[#ccc] [&_a]:text-[#ff9a9a]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.context}</ReactMarkdown>
          </div>
        )}
      </section>

      <section>
        <h3 className="flex flex-wrap items-baseline gap-x-[15px]">
          <span className="text-[19px] font-bold text-[#272727]">함께 쓰이는 기술</span>
          <span className="text-[13px] text-[#999]">스택 레이어별 · {t.name} 공고 중 비율</span>
        </h3>
        <div className="mt-[22px] grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {byLayer.map(([layer, items]) => {
            const c = colorOf(layer)
            return (
              <div key={layer} className="border-b border-[#e2e8ec] px-[21px] pb-5">
                <div className="text-[15px] font-bold" style={{ color: c }}>
                  {layer}
                </div>
                <ul className="mt-2 flex flex-col gap-2">
                  {items.map((r) => (
                    <li key={r.name}>
                      <div className="flex items-baseline justify-between text-sm">
                        <span className="text-[#272727]">{r.name}</span>
                        <b className="font-bold text-[#272727] tabular-nums">{r.pct}%</b>
                      </div>
                      <div className="mt-1 h-1.5 rounded-[3px] bg-[#f1f3f5] overflow-hidden">
                        <div className="h-full rounded-[3px]" style={{ width: `${Math.min(100, r.pct)}%`, background: c }} />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </section>

      {/* 스택 지도 — 고른 기술을 가운데, 함께 쓰는 기술을 둘레에(테두리 = 레이어 색) */}
      {ring.length > 0 && (
        <section className="rounded-[30px] border border-[#e2e8ec] bg-white px-6 pt-6 pb-8">
          <h3 className="text-[19px] font-bold text-[#272727]">{t.name} 스택 지도</h3>
          <div className="relative mx-auto mt-4 h-[380px] max-w-[760px]">
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-[28px] bg-[#272727] px-8 py-3.5 text-xl font-bold text-white">{t.name}</span>
            {ring.map((r, i) => {
              const a = (i / ring.length) * Math.PI * 2 - Math.PI / 2
              const c = colorOf(r.layer)
              return (
                <span
                  key={r.name}
                  className="absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-[18px] border-2 bg-white px-3.5 py-1.5 text-sm font-bold"
                  style={{ left: `${50 + 40 * Math.cos(a)}%`, top: `${50 + 42 * Math.sin(a)}%`, borderColor: c, color: c }}
                >
                  {r.name} <span className="text-xs font-normal text-[#999]">{r.pct}%</span>
                </span>
              )
            })}
          </div>
        </section>
      )}
    </>
  )
}
