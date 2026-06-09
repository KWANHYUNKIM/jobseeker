import { useMemo, useState } from 'react'
import { useCompanies } from '../lib/useCompanies'
import {
  buildExpansionIndex,
  roadmapsForTech,
  CAT_ORDER,
  CAT_COLOR,
  type TechNode,
} from '../lib/expansion'

const SIZE_COLOR: Record<string, string> = {
  대기업: '#f472b6',
  중견기업: '#fbbf24',
  중소기업: '#60a5fa',
}

const COMPANY_LIMIT = 60
const COOC_LIMIT = 14

export function ExpansionView({ onOpenCompany }: { onOpenCompany?: (norm: string) => void }) {
  const { companies, loading, error } = useCompanies()
  const [query, setQuery] = useState('')
  const [selectedTech, setSelectedTech] = useState<string | null>(null)

  const index = useMemo(() => buildExpansionIndex(companies), [companies])

  const tech = useMemo(() => {
    if (selectedTech && index.categoryOf[selectedTech]) return selectedTech
    return index.techs[0]?.name ?? null
  }, [selectedTech, index])

  if (loading) return <div className="p-8 text-(--color-muted)">기술스택 데이터 로딩 중…</div>
  if (error)
    return (
      <div className="p-8 text-red-400">
        company_stacks.json 로드 실패: {error}
        <br />
        <span className="text-(--color-muted) text-sm">
          생성: <code>python3 jd-viewer/bin/build_company_stacks.py</code>
        </span>
      </div>
    )

  return (
    <div className="flex flex-1 min-h-0">
      <TechSidebar
        index={index}
        query={query}
        setQuery={setQuery}
        selected={tech}
        onSelect={setSelectedTech}
      />
      <main className="flex-1 min-w-0 overflow-auto">
        {tech ? (
          <TechPanel
            tech={tech}
            index={index}
            onSelectTech={setSelectedTech}
            onOpenCompany={onOpenCompany}
          />
        ) : (
          <div className="p-8 text-(--color-muted)">기술을 선택하세요.</div>
        )}
      </main>
    </div>
  )
}

function TechSidebar({
  index,
  query,
  setQuery,
  selected,
  onSelect,
}: {
  index: ReturnType<typeof buildExpansionIndex>
  query: string
  setQuery: (v: string) => void
  selected: string | null
  onSelect: (t: string) => void
}) {
  const q = query.trim().toLowerCase()
  const cats = CAT_ORDER.filter((c) => index.byCategory[c]?.length)

  return (
    <aside className="w-64 shrink-0 border-r border-(--color-border) bg-(--color-panel) flex flex-col min-h-0">
      <div className="p-3 border-b border-(--color-border)">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="기술 검색 (예: React)"
          className="w-full bg-(--color-bg) border border-(--color-border) rounded px-3 py-1.5 text-sm text-(--color-text) placeholder:text-(--color-muted) focus:border-(--color-accent) outline-none"
        />
        <div className="text-[11px] text-(--color-muted) mt-2">
          {index.techs.length}개 기술 · {index.totalCompanies}개 회사
        </div>
      </div>
      <div className="overflow-auto flex-1 py-1">
        {cats.map((cat) => {
          const items = index.byCategory[cat].filter((t) => !q || t.name.toLowerCase().includes(q))
          if (!items.length) return null
          return (
            <div key={cat} className="mb-1">
              <div
                className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider font-semibold"
                style={{ color: CAT_COLOR[cat] }}
              >
                {cat}
              </div>
              {items.map((t) => {
                const active = t.name === selected
                return (
                  <button
                    key={t.name}
                    onClick={() => onSelect(t.name)}
                    className={`w-full text-left px-3 py-1.5 flex items-center gap-2 transition ${
                      active ? 'bg-(--color-accent)/15' : 'hover:bg-white/5'
                    }`}
                  >
                    <span className="text-[13px] text-(--color-text) truncate">{t.name}</span>
                    <span className="ml-auto text-[11px] text-(--color-muted) shrink-0">{t.companyCount}</span>
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </aside>
  )
}

function TechPanel({
  tech,
  index,
  onSelectTech,
  onOpenCompany,
}: {
  tech: string
  index: ReturnType<typeof buildExpansionIndex>
  onSelectTech: (t: string) => void
  onOpenCompany?: (norm: string) => void
}) {
  const cat = index.categoryOf[tech] ?? '기타'
  const color = CAT_COLOR[cat] ?? '#6b7280'
  const node = index.techs.find((t) => t.name === tech) as TechNode | undefined
  const companies = index.companiesByTech[tech] ?? []
  const cooc = (index.coocByTech[tech] ?? []).slice(0, COOC_LIMIT)
  const roadmaps = roadmapsForTech(tech)
  const maxConf = Math.max(0.0001, ...cooc.map((c) => c.confidence))
  const shown = companies.slice(0, COMPANY_LIMIT)

  return (
    <div className="p-6 max-w-5xl">
      {/* 헤더 */}
      <div className="flex items-center flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-white">{tech}</h1>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: color + '22', color }}
        >
          {cat}
        </span>
        <span className="text-xs text-(--color-muted)">
          {node?.companyCount ?? 0}개 회사 · 공고 {node?.postingCount ?? 0}건
        </span>
      </div>

      {/* 확장 추천 */}
      <Section
        title="함께 자주 쓰는 기술 (확장 추천)"
        hint="이 기술을 쓰는 회사에서 유난히 자주 함께 등장하는 기술 — 다음 학습 후보"
      >
        {cooc.length ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {cooc.map((c) => {
              const cc = CAT_COLOR[c.category] ?? '#6b7280'
              return (
                <button
                  key={c.name}
                  onClick={() => onSelectTech(c.name)}
                  className="text-left bg-(--color-panel) border border-(--color-border) rounded-lg p-2.5 hover:border-(--color-accent)/60 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cc }} />
                    <span className="text-sm text-(--color-text) font-medium truncate">{c.name}</span>
                    <span className="ml-auto text-[11px] text-(--color-muted) shrink-0">{c.coCount}곳</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-(--color-bg) rounded overflow-hidden">
                    <div
                      className="h-full rounded"
                      style={{ width: `${(c.confidence / maxConf) * 100}%`, background: cc }}
                    />
                  </div>
                  <div className="text-[10px] text-(--color-muted) mt-1">
                    동반율 {(c.confidence * 100).toFixed(0)}% · 연관도 {c.lift.toFixed(1)}x
                  </div>
                </button>
              )
            })}
          </div>
        ) : (
          <span className="text-sm text-(--color-muted)">동시출현 데이터가 충분하지 않습니다.</span>
        )}
      </Section>

      {/* 학습 로드맵 */}
      {roadmaps.length > 0 && (
        <Section title="추천 학습 로드맵" hint="현재 기술이 속한 직군 경로 — 빛나는 칸이 지금 위치">
          <div className="space-y-4">
            {roadmaps.map((rm) => (
              <div key={rm.role} className="border border-(--color-border) rounded-lg p-3 bg-(--color-panel)">
                <div className="text-sm font-semibold mb-3" style={{ color: rm.color }}>
                  {rm.role} 로드맵
                </div>
                <div className="flex flex-wrap items-stretch gap-2">
                  {rm.steps.map((step, i) => (
                    <div key={step.tier} className="flex items-stretch gap-2">
                      <div className="min-w-[150px]">
                        <div className="text-[11px] font-semibold text-(--color-text) mb-1">{step.tier}</div>
                        <div className="flex flex-wrap gap-1 mb-1">
                          {step.techs.map((tn) => {
                            const exists = index.categoryOf[tn] != null
                            const here = tn === tech
                            const count = index.techs.find((t) => t.name === tn)?.companyCount
                            return (
                              <button
                                key={tn}
                                disabled={!exists}
                                onClick={() => exists && onSelectTech(tn)}
                                title={exists ? `${count}개 회사` : '데이터 없음'}
                                className={`text-[11px] px-1.5 py-0.5 rounded border transition ${
                                  here
                                    ? 'font-bold text-black'
                                    : exists
                                      ? 'text-(--color-text) hover:border-(--color-accent)'
                                      : 'text-(--color-muted) opacity-50 cursor-default'
                                }`}
                                style={
                                  here
                                    ? { background: rm.color, borderColor: rm.color }
                                    : { borderColor: 'var(--color-border)' }
                                }
                              >
                                {tn}
                                {exists && count != null && (
                                  <span className="ml-1 opacity-60">{count}</span>
                                )}
                              </button>
                            )
                          })}
                        </div>
                        <div className="text-[10px] text-(--color-muted) leading-snug">{step.note}</div>
                      </div>
                      {i < rm.steps.length - 1 && (
                        <div className="flex items-center text-(--color-muted) text-lg shrink-0">→</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* 이 기술을 쓰는 회사 */}
      <Section title={`이 기술을 쓰는 회사 (${companies.length}곳)`}>
        {shown.length ? (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
              {shown.map((c) => {
                const sc = SIZE_COLOR[c.size] ?? '#60a5fa'
                return (
                  <button
                    key={c.norm}
                    onClick={() => onOpenCompany?.(c.norm)}
                    className="text-left bg-(--color-panel) border border-(--color-border) rounded-md px-2.5 py-1.5 hover:border-(--color-accent)/60 transition"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-[13px] text-(--color-text) truncate">{c.name}</span>
                      <span
                        className="text-[9px] px-1 py-0.5 rounded-full shrink-0"
                        style={{ background: sc + '22', color: sc }}
                      >
                        {c.size}
                      </span>
                      <span className="ml-auto text-[10px] text-(--color-muted) shrink-0">{c.count}건</span>
                    </div>
                    {c.domains[0] && (
                      <div className="text-[10px] text-(--color-muted) truncate mt-0.5">{c.domains[0]}</div>
                    )}
                  </button>
                )
              })}
            </div>
            {companies.length > COMPANY_LIMIT && (
              <div className="text-[11px] text-(--color-muted) mt-2">
                외 {companies.length - COMPANY_LIMIT}개 회사 (공고 많은 순 상위 {COMPANY_LIMIT}개 표시)
              </div>
            )}
          </>
        ) : (
          <span className="text-sm text-(--color-muted)">해당 기술을 쓰는 회사가 없습니다.</span>
        )}
      </Section>
    </div>
  )
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      {hint && <p className="text-[11px] text-(--color-muted) mb-2 mt-0.5">{hint}</p>}
      {!hint && <div className="mb-2" />}
      {children}
    </section>
  )
}
