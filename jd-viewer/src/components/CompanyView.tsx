import { useMemo, useState } from 'react'
import { useCompanies } from '../lib/useCompanies'
import { ROLE_COLORS } from '../lib/classify'
import type { CompanyStack } from '../types'

const SIZE_COLOR: Record<string, string> = {
  대기업: '#f472b6',
  중견기업: '#fbbf24',
  중소기업: '#60a5fa',
}

const CAT_COLOR: Record<string, string> = {
  언어: '#c084fc',
  백엔드: '#60a5fa',
  프론트엔드: '#34d399',
  모바일: '#fbbf24',
  데이터베이스: '#22d3ee',
  '인프라/DevOps': '#fb923c',
  '펌웨어/임베디드': '#a78bfa',
  'AI/ML': '#f472b6',
  데이터: '#2dd4bf',
  '협업/도구': '#94a3b8',
  기타: '#6b7280',
}

const CAT_ORDER = [
  '언어', '백엔드', '프론트엔드', '모바일', '데이터베이스',
  '인프라/DevOps', '펌웨어/임베디드', 'AI/ML', '데이터', '협업/도구', '기타',
]

export function CompanyView() {
  const { companies, meta, loading, error } = useCompanies()
  const [query, setQuery] = useState('')
  const [selectedNorm, setSelectedNorm] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return companies
    return companies.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.domains.some((d) => d.name.toLowerCase().includes(q)) ||
        c.top_tech.some((t) => t.name.toLowerCase().includes(q)),
    )
  }, [companies, query])

  const selected = useMemo(
    () => companies.find((c) => c.norm === selectedNorm) ?? filtered[0] ?? null,
    [companies, selectedNorm, filtered],
  )

  if (loading) return <div className="p-8 text-(--color-muted)">회사 분석 데이터 로딩 중…</div>
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
      {/* 좌측: 회사 리스트 */}
      <aside className="w-72 shrink-0 border-r border-(--color-border) bg-(--color-panel) flex flex-col min-h-0">
        <div className="p-3 border-b border-(--color-border)">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="회사·기술·도메인 검색"
            className="w-full bg-(--color-bg) border border-(--color-border) rounded px-3 py-1.5 text-sm text-(--color-text) placeholder:text-(--color-muted) focus:border-(--color-accent) outline-none"
          />
          <div className="text-[11px] text-(--color-muted) mt-2">
            {filtered.length}개 회사 · 공고 {meta?.min_posting ?? 2}건 이상
          </div>
        </div>
        <div className="overflow-auto flex-1">
          {filtered.map((c) => {
            const active = selected?.norm === c.norm
            return (
              <button
                key={c.norm}
                onClick={() => setSelectedNorm(c.norm)}
                className={`w-full text-left px-3 py-2.5 border-b border-(--color-border)/50 transition ${
                  active ? 'bg-(--color-accent)/15' : 'hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm text-(--color-text) font-medium truncate">{c.name}</span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0"
                    style={{ background: (SIZE_COLOR[c.size] ?? '#60a5fa') + '22', color: SIZE_COLOR[c.size] ?? '#60a5fa' }}
                  >
                    {c.size}
                  </span>
                  <span className="ml-auto text-[11px] text-(--color-muted) shrink-0">{c.posting_count}건</span>
                </div>
                <div className="text-[11px] text-(--color-muted) mt-1 truncate">
                  {c.domains[0]?.name ?? '도메인 미상'}
                  {c.top_tech[0] ? ` · ${c.top_tech.slice(0, 3).map((t) => t.name).join(', ')}` : ''}
                </div>
              </button>
            )
          })}
        </div>
      </aside>

      {/* 우측: 회사 프로필 */}
      <main className="flex-1 min-w-0 overflow-auto">
        {selected ? <CompanyProfile c={selected} /> : (
          <div className="p-8 text-(--color-muted)">회사를 선택하세요.</div>
        )}
      </main>
    </div>
  )
}

function CompanyProfile({ c }: { c: CompanyStack }) {
  const maxRole = Math.max(1, ...Object.values(c.roles))
  return (
    <div className="p-6 max-w-4xl">
      {/* 헤더 */}
      <div className="flex items-center flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-white">{c.name}</h1>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: (SIZE_COLOR[c.size] ?? '#60a5fa') + '22', color: SIZE_COLOR[c.size] ?? '#60a5fa' }}
        >
          {c.size}
        </span>
        <span className="text-xs text-(--color-muted)">채용공고 {c.posting_count}건</span>
        <span className="text-xs text-(--color-muted)">· {c.sites.join(', ')}</span>
        {c.homepage && (
          <a
            href={c.homepage}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs px-3 py-1 rounded border border-(--color-border) text-(--color-accent) hover:bg-(--color-accent)/10"
          >
            홈페이지 ↗
          </a>
        )}
      </div>

      {/* 요약 */}
      <p className="mt-3 text-sm text-(--color-text) leading-relaxed bg-(--color-panel) border border-(--color-border) rounded-lg p-3">
        {c.summary}
      </p>

      {/* 도메인 */}
      <Section title="도메인 (사업 영역)">
        {c.domains.length ? (
          <div className="flex flex-wrap gap-2">
            {c.domains.map((d) => (
              <span
                key={d.name}
                title={d.evidence.length ? `근거 키워드: ${d.evidence.join(', ')}` : undefined}
                className="text-sm px-3 py-1.5 rounded-lg bg-(--color-accent)/12 text-(--color-accent) border border-(--color-accent)/30"
              >
                {d.name}
                {d.evidence.length > 0 && (
                  <span className="text-[11px] text-(--color-muted) ml-1.5">{d.evidence.slice(0, 3).join(' · ')}</span>
                )}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-sm text-(--color-muted)">추론된 도메인 없음</span>
        )}
      </Section>

      {/* 아키텍처 추론 */}
      <Section title="아키텍처 추론 (기술 조합 기반 예측)">
        {c.architecture.length ? (
          <div className="grid sm:grid-cols-2 gap-2">
            {c.architecture.map((a) => (
              <div key={a.label} className="bg-(--color-panel) border border-(--color-border) rounded-lg p-3">
                <div className="text-sm font-semibold text-white">{a.label}</div>
                <div className="text-[12px] text-(--color-muted) mt-1 leading-relaxed">{a.why}</div>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-sm text-(--color-muted)">추론된 아키텍처 없음</span>
        )}
      </Section>

      {/* 기술스택 (카테고리별) */}
      <Section title="기술스택 (채용공고 기반)">
        <div className="space-y-3">
          {CAT_ORDER.filter((cat) => c.tech_categories[cat]?.length).map((cat) => (
            <div key={cat}>
              <div className="text-[11px] uppercase tracking-wider font-semibold mb-1.5" style={{ color: CAT_COLOR[cat] }}>
                {cat}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {c.tech_categories[cat].map((t) => (
                  <span
                    key={t.name}
                    className="text-[13px] px-2.5 py-1 rounded-md border flex items-center gap-1.5"
                    style={{ borderColor: (CAT_COLOR[cat] ?? '#6b7280') + '55', background: (CAT_COLOR[cat] ?? '#6b7280') + '12' }}
                  >
                    <span className="text-(--color-text)">{t.name}</span>
                    <span className="text-[10px] text-(--color-muted)">{t.count}</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 직군 분포 */}
      <Section title="채용 직군 분포">
        <div className="space-y-1.5 max-w-md">
          {Object.entries(c.roles).map(([role, n]) => (
            <div key={role} className="flex items-center gap-2">
              <span className="text-xs text-(--color-muted) w-24 shrink-0 text-right">{role}</span>
              <div className="flex-1 h-4 bg-(--color-panel) rounded overflow-hidden">
                <div
                  className="h-full rounded"
                  style={{ width: `${(n / maxRole) * 100}%`, background: ROLE_COLORS[role] ?? '#6b7280' }}
                />
              </div>
              <span className="text-xs text-(--color-muted) w-8">{n}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* 홈페이지 조사 (2차 보강) */}
      {(c.homepage_desc || (c.homepage_tech && c.homepage_tech.length > 0)) && (
        <Section title="홈페이지 조사 (자동 수집)">
          {c.homepage_desc && (
            <p className="text-sm text-(--color-text) leading-relaxed mb-2">{c.homepage_desc}</p>
          )}
          {c.homepage_tech && c.homepage_tech.length > 0 && (
            <div>
              <span className="text-[11px] text-(--color-muted)">홈페이지에서 감지된 기술: </span>
              <span className="text-[12px] text-(--color-muted)">{c.homepage_tech.join(', ')}</span>
            </div>
          )}
        </Section>
      )}

      {/* 공고 목록 */}
      <Section title="채용공고">
        <ul className="space-y-1">
          {c.postings.map((p, i) => (
            <li key={i}>
              <a
                href={p.url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-(--color-accent) hover:underline"
              >
                {p.title || p.url}
              </a>
              <span className="text-[11px] text-(--color-muted) ml-2">{p.site}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h2 className="text-sm font-semibold text-white mb-2">{title}</h2>
      {children}
    </section>
  )
}
