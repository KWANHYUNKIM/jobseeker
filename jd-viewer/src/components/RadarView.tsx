import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useRadar } from '../lib/useRadar'
import { ArchitectureDiagram } from './ArchitectureDiagram'
import { Loader, ErrorState } from './ui'
import type {
  Debate,
  DeepDiveSection,
  DomainGroup,
  RadarCompany,
  RadarFile,
  RadarTechCount,
} from '../types'

const COUNTRY_LABEL: Record<string, string> = {
  US: '🇺🇸 미국',
  KR: '🇰🇷 한국',
  IN: '🇮🇳 인도',
  JP: '🇯🇵 일본',
  GB: '🇬🇧 영국',
  DE: '🇩🇪 독일',
  SG: '🇸🇬 싱가포르',
  CN: '🇨🇳 중국',
}

const STACK_LABEL: Record<string, string> = {
  backend: '백엔드',
  frontend: '프론트엔드',
  data: '데이터',
  infra: '인프라/DevOps',
}

export function RadarView() {
  const { data, loading, error } = useRadar()
  const [mode, setMode] = useState<'company' | 'domain'>('company')
  const [query, setQuery] = useState('')
  const [country, setCountry] = useState<string | null>(null)
  const [domain, setDomain] = useState<string | null>(null)
  const [langs, setLangs] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<RadarCompany | null>(null)

  const companies = data?.companies ?? []

  // 도메인 뷰에서 회사 이름을 클릭하면 상세를 연다
  const byName = useMemo(() => {
    const m = new Map<string, RadarCompany>()
    for (const c of companies) m.set(c.name, c)
    return m
  }, [companies])

  const langCount = useMemo(() => {
    const c = new Map<string, number>()
    for (const co of companies) for (const l of co.languages) c.set(l, (c.get(l) ?? 0) + 1)
    return [...c.entries()].sort((a, b) => b[1] - a[1])
  }, [companies])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return companies.filter((c) => {
      if (country && c.country !== country) return false
      if (domain && c.domain !== domain) return false
      if (langs.size && !c.languages.some((l) => langs.has(l))) return false
      if (q) {
        const hay = `${c.name} ${c.domain} ${c.summary} ${c.languages.join(' ')} ${[
          ...c.stack.backend,
          ...c.stack.frontend,
          ...c.stack.data,
          ...c.stack.infra,
        ].join(' ')} ${c.architecture.join(' ')}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [companies, query, country, domain, langs])

  const toggleLang = (name: string) => {
    const next = new Set(langs)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setLangs(next)
  }

  if (loading) return <Loader label="기술 스택 레이더 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="company_tech_radar.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python bin/build_company_tech_radar.py --init seed_*.json</code> (jd-viewer)</>}
      />
    )

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 보기 전환: 회사별 ↔ 도메인별 공통 스택 */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60">
        <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden">
          <ModeBtn active={mode === 'company'} onClick={() => setMode('company')}>
            회사별
          </ModeBtn>
          <ModeBtn active={mode === 'domain'} onClick={() => setMode('domain')}>
            도메인별
          </ModeBtn>
        </div>
        <span className="text-xs text-(--color-muted)">
          {mode === 'domain'
            ? `${data?.domain_groups?.length ?? 0}개 산업 도메인 · 도메인이 어떤 기술스택으로 이루어지는지 집계`
            : '회사별 기술 스택 · 아키텍처 다이어그램'}
        </span>
      </div>

      {mode === 'domain' ? (
        <DomainView
          data={data}
          onOpenCompany={(name) => {
            const c = byName.get(name)
            if (c) setSelected(c)
          }}
        />
      ) : (
        <div className="flex flex-1 min-h-0">
          {/* 사이드바: 검색 + 국가 + 도메인 + 언어 */}
          <aside className="w-80 shrink-0 overflow-auto border-r border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색 (회사·도메인·언어·아키텍처)"
          className="w-full px-3 py-2 text-sm rounded bg-(--color-bg) border border-(--color-border) text-(--color-text) placeholder:text-(--color-muted)"
        />

        <div>
          <div className="text-xs text-(--color-muted) mb-2">국가</div>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={country === null} onClick={() => setCountry(null)}>
              전체
            </Chip>
            {(data?.countries ?? []).map((c) => (
              <Chip
                key={c.code}
                active={country === c.code}
                onClick={() => setCountry(country === c.code ? null : c.code!)}
              >
                {COUNTRY_LABEL[c.code!] ?? c.code} {c.count}
              </Chip>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs text-(--color-muted) mb-2">도메인</div>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={domain === null} onClick={() => setDomain(null)}>
              전체
            </Chip>
            {(data?.domains ?? []).map((d) => (
              <Chip
                key={d.name}
                active={domain === d.name}
                onClick={() => setDomain(domain === d.name ? null : d.name!)}
              >
                {d.name} <span className="opacity-60">{d.count}</span>
              </Chip>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-(--color-muted)">
          <span>언어</span>
          {langs.size > 0 && (
            <button onClick={() => setLangs(new Set())} className="text-(--color-accent) hover:underline">
              초기화 ({langs.size})
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5 -mt-2">
          {langCount.map(([name, n]) => (
            <Chip key={name} active={langs.has(name)} onClick={() => toggleLang(name)}>
              {name} <span className="opacity-60">{n}</span>
            </Chip>
          ))}
        </div>
      </aside>

      {/* 본문: 회사 카드 목록 */}
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="px-5 py-3 border-b border-(--color-border) text-xs text-(--color-muted) flex items-center gap-3">
          <span>
            {data?.total ?? 0}개사 중 <b className="text-(--color-text)">{filtered.length}개사</b>
            {' · '}
            {data?.countries.length ?? 0}개국 · {data?.domains.length ?? 0}개 도메인
            {data && data.refined > 0 && <span> · AI 갱신 {data.refined}</span>}
          </span>
          {data?.generated_at && <span className="ml-auto">갱신 {data.generated_at.slice(0, 10)}</span>}
        </div>
        <ul className="divide-y divide-(--color-border)">
          {filtered.map((c) => (
            <CompanyRow key={c.key} company={c} onPickLang={toggleLang} onOpen={setSelected} />
          ))}
          {filtered.length === 0 && (
            <li className="p-8 text-(--color-muted)">조건에 맞는 회사가 없습니다.</li>
          )}
        </ul>
      </main>
        </div>
      )}

      {selected && <RadarDetail company={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ── 도메인별 보기: 산업 도메인 전체 + 도메인별 공통 기술스택 ──────────────
function DomainView({
  data,
  onOpenCompany,
}: {
  data: RadarFile | null
  onOpenCompany: (name: string) => void
}) {
  const groups = data?.domain_groups ?? []
  if (groups.length === 0) {
    return (
      <div className="flex-1 overflow-auto p-8 text-(--color-muted)">
        도메인 집계가 없습니다.{' '}
        <code className="text-(--color-text)">python bin/build_company_tech_radar.py</code> 로 재생성하세요.
      </div>
    )
  }
  return (
    <div className="flex-1 min-h-0 overflow-auto">
      {/* 도메인 빠른 이동 */}
      <div className="px-5 py-3 border-b border-(--color-border) flex flex-wrap gap-1.5">
        {groups.map((g) => (
          <a
            key={g.name}
            href={`#domain-${encodeURIComponent(g.name)}`}
            className="px-2 py-0.5 text-xs rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
          >
            {g.name} <span className="opacity-60">{g.count}</span>
          </a>
        ))}
      </div>

      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4 p-5">
        {groups.map((g) => (
          <DomainCard key={g.name} group={g} onOpenCompany={onOpenCompany} />
        ))}
      </div>
    </div>
  )
}

const DOMAIN_STACK_LABEL: Record<keyof DomainGroup['stack'], string> = {
  backend: '백엔드',
  frontend: '프론트엔드',
  data: '데이터',
  infra: '인프라/DevOps',
}

function DomainCard({
  group,
  onOpenCompany,
}: {
  group: DomainGroup
  onOpenCompany: (name: string) => void
}) {
  const stackKeys = (['backend', 'frontend', 'data', 'infra'] as const).filter(
    (k) => group.stack[k]?.length > 0,
  )
  return (
    <section
      id={`domain-${encodeURIComponent(group.name)}`}
      className="scroll-mt-4 rounded-lg border border-(--color-border) bg-(--color-panel) p-5 flex flex-col gap-4"
    >
      <div>
        <div className="flex items-baseline gap-2">
          <h3 className="text-lg font-semibold text-(--color-text)">{group.name}</h3>
          <span className="text-xs text-(--color-accent)">{group.count}개사</span>
        </div>
        {group.subdomains.length > 0 && (
          <p className="mt-0.5 text-xs text-(--color-muted)">
            세부: {group.subdomains.join(' · ')}
          </p>
        )}
      </div>

      {group.languages.length > 0 && (
        <DomainRow label="주요 언어">
          {group.languages.map((t) => (
            <TechTag key={t.name} item={t} accent />
          ))}
        </DomainRow>
      )}

      {group.architecture.length > 0 && (
        <DomainRow label="아키텍처 패턴">
          {group.architecture.map((t) => (
            <TechTag key={t.name} item={t} />
          ))}
        </DomainRow>
      )}

      <div className="flex flex-col gap-2.5">
        <div className="text-xs font-medium text-(--color-muted)">공통 기술스택</div>
        {stackKeys.map((k) => (
          <div key={k} className="flex gap-3">
            <div className="w-24 shrink-0 text-xs text-(--color-muted) pt-1">
              {DOMAIN_STACK_LABEL[k]}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {group.stack[k].map((t) => (
                <TechTag key={t.name} item={t} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <DomainRow label={`회사 (${group.companies.length})`}>
        {group.companies.map((name) => (
          <button
            key={name}
            onClick={() => onOpenCompany(name)}
            className="px-2 py-0.5 text-xs rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
          >
            {name}
          </button>
        ))}
      </DomainRow>
    </section>
  )
}

function DomainRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-(--color-muted) mb-2">{label}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

// 기술 태그 — 빈도(몇 개사가 쓰는지)를 작은 숫자로 함께 표시
function TechTag({ item, accent }: { item: RadarTechCount; accent?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border ${
        accent
          ? 'bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40'
          : 'bg-(--color-bg) text-(--color-text) border-(--color-border)'
      }`}
    >
      {item.name}
      {item.count > 1 && <span className="opacity-50 tabular-nums">{item.count}</span>}
    </span>
  )
}

function ModeBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs font-medium transition ${
        active
          ? 'bg-(--color-accent) text-black'
          : 'bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {children}
    </button>
  )
}

function CompanyRow({
  company,
  onPickLang,
  onOpen,
}: {
  company: RadarCompany
  onPickLang: (s: string) => void
  onOpen: (c: RadarCompany) => void
}) {
  return (
    <li className="px-5 py-4 hover:bg-(--color-panel) transition">
      <div className="flex items-center gap-2 text-xs text-(--color-muted) mb-1">
        <span>{COUNTRY_LABEL[company.country] ?? company.country}</span>
        <span className="px-1.5 rounded bg-(--color-bg) border border-(--color-border)">
          {company.domain}
        </span>
        {company.research_status === 'llm-refined' && (
          <span className="px-1.5 rounded bg-(--color-accent)/15 text-(--color-accent) border border-(--color-accent)/40">
            AI 갱신
          </span>
        )}
        <span className="ml-auto">{company.architecture.join(' · ')}</span>
      </div>
      <button
        onClick={() => onOpen(company)}
        className="text-left text-(--color-text) font-medium hover:text-(--color-accent) hover:underline"
      >
        {company.name}
      </button>
      {company.summary && (
        <p className="mt-1 text-sm text-(--color-muted) line-clamp-2">{company.summary}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {company.languages.map((l) => (
          <button
            key={l}
            onClick={() => onPickLang(l)}
            className="px-2 py-0.5 text-xs rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
          >
            {l}
          </button>
        ))}
      </div>
    </li>
  )
}

function RadarDetail({ company, onClose }: { company: RadarCompany; onClose: () => void }) {
  const stackEntries = (['backend', 'frontend', 'data', 'infra'] as const)
    .map((k) => [k, company.stack[k]] as const)
    .filter(([, v]) => v && v.length > 0)

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="w-[min(1040px,96vw)] h-full overflow-auto bg-(--color-panel) border-l border-(--color-border) p-6 flex flex-col gap-5 jd-slide-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs text-(--color-muted) mb-1">
              <span>{COUNTRY_LABEL[company.country] ?? company.country}</span>
              <span className="px-1.5 rounded bg-(--color-bg) border border-(--color-border)">
                {company.domain}
              </span>
              {company.research_status === 'llm-refined' && (
                <span className="px-1.5 rounded bg-(--color-accent)/15 text-(--color-accent) border border-(--color-accent)/40">
                  AI 갱신 {company.updated_at}
                </span>
              )}
            </div>
            <h2 className="text-xl font-semibold text-(--color-text)">{company.name}</h2>
            {company.summary && <p className="mt-1 text-sm text-(--color-muted)">{company.summary}</p>}
          </div>
          <button
            onClick={onClose}
            className="ml-auto shrink-0 text-(--color-muted) hover:text-(--color-text) text-lg leading-none"
          >
            ✕
          </button>
        </div>

        <Section title="주요 언어">
          <div className="flex flex-wrap gap-1.5">
            {company.languages.map((l) => (
              <Tag key={l} accent>
                {l}
              </Tag>
            ))}
          </div>
        </Section>

        <Section title="아키텍처">
          <div className="flex flex-wrap gap-1.5">
            {company.architecture.map((a) => (
              <Tag key={a}>{a}</Tag>
            ))}
          </div>
        </Section>

        {company.diagram && (
          <Section title="아키텍처 다이어그램 (노드별 기술스택)">
            <ArchitectureDiagram code={company.diagram} idKey={company.key} />
          </Section>
        )}

        <Section title="기술 스택">
          <div className="flex flex-col gap-2.5">
            {stackEntries.map(([k, items]) => (
              <div key={k} className="flex gap-3">
                <div className="w-20 shrink-0 text-xs text-(--color-muted) pt-1">{STACK_LABEL[k]}</div>
                <div className="flex flex-wrap gap-1.5">
                  {items.map((t) => (
                    <Tag key={t}>{t}</Tag>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="왜 이 언어인가">
          <p className="text-sm text-(--color-text) leading-relaxed">{company.why_language}</p>
        </Section>

        <Section title="왜 이 아키텍처인가">
          <p className="text-sm text-(--color-text) leading-relaxed">{company.why_architecture}</p>
        </Section>

        {company.deep_dive && company.deep_dive.length > 0 && (
          <Section title={`기술 심화 — 어떻게 작동하는가 (${company.deep_dive.length})`}>
            <div className="flex flex-col gap-2">
              {company.deep_dive.map((s, i) => (
                <DeepDive key={s.topic + i} section={s} defaultOpen={i < 2} />
              ))}
            </div>
          </Section>
        )}

        {company.debate && (
          <Section title="아키텍처 토론 — 설계자 ↔ 검토자 + 정리자">
            <DebateView debate={company.debate} idKey={company.key} />
          </Section>
        )}

        {company.github && (company.github.repos?.length || company.github.org) && (
          <Section title="공개 GitHub 코드">
            {company.github.org && (
              <a
                href={company.github.org}
                target="_blank"
                rel="noreferrer"
                className="inline-block mb-2 text-sm text-(--color-accent) hover:underline break-all"
              >
                {company.github.org.replace('https://github.com/', '@')} ↗
              </a>
            )}
            <ul className="flex flex-col gap-2">
              {(company.github.repos ?? []).map((r) => (
                <li
                  key={r.url}
                  className="rounded border border-(--color-border) bg-(--color-bg) px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-(--color-text) hover:text-(--color-accent) hover:underline break-all"
                    >
                      {r.name}
                    </a>
                    {r.lang && (
                      <span className="text-xs text-(--color-muted) shrink-0">{r.lang}</span>
                    )}
                    {typeof r.stars === 'number' && (
                      <span className="ml-auto text-xs text-(--color-muted) shrink-0">
                        ★ {r.stars >= 1000 ? `${(r.stars / 1000).toFixed(1)}k` : r.stars}
                      </span>
                    )}
                  </div>
                  {r.desc && <p className="mt-0.5 text-xs text-(--color-muted)">{r.desc}</p>}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {company.sources.length > 0 && (
          <Section title="출처">
            <ul className="flex flex-col gap-1">
              {company.sources.map((s) => (
                <li key={s}>
                  <a
                    href={s}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-(--color-accent) hover:underline break-all"
                  >
                    {s} ↗
                  </a>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </div>
  )
}

const ROLE_META: Record<string, { label: string; align: string; color: string }> = {
  architect: { label: '설계자', align: 'items-start', color: 'border-(--color-accent)/40 bg-(--color-accent)/10' },
  critic: { label: '검토자', align: 'items-end', color: 'border-amber-500/40 bg-amber-500/10' },
  synthesizer: { label: '정리자', align: 'items-center', color: 'border-(--color-border) bg-(--color-bg)' },
}

function DebateView({ debate, idKey }: { debate: Debate; idKey: string }) {
  const [tab, setTab] = useState(0)
  const archs = debate.architectures ?? []
  return (
    <div className="flex flex-col gap-4">
      {/* 1) 아키텍처 후보 (탭) */}
      {archs.length > 0 && (
        <div className="rounded border border-(--color-border) bg-(--color-bg) p-3">
          <div className="flex flex-wrap gap-1.5 mb-3">
            {archs.map((a, i) => (
              <button
                key={i}
                onClick={() => setTab(i)}
                className={`px-2.5 py-1 text-xs rounded border transition ${
                  tab === i
                    ? 'bg-(--color-accent) text-black border-(--color-accent) font-medium'
                    : 'bg-(--color-panel) text-(--color-text) border-(--color-border) hover:border-(--color-accent)'
                }`}
              >
                {a.name}
              </button>
            ))}
          </div>
          {archs[tab] && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-(--color-text) leading-relaxed">{archs[tab].summary}</p>
              {archs[tab].diagram && (
                <ArchitectureDiagram code={archs[tab].diagram!} idKey={`${idKey}-arch${tab}`} />
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs font-medium text-(--color-accent) mb-1">장점</div>
                  <ul className="flex flex-col gap-1">
                    {archs[tab].pros.map((p, i) => (
                      <li key={i} className="text-xs text-(--color-muted) flex gap-1">
                        <span className="text-(--color-accent)">+</span> {p}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-xs font-medium text-amber-400 mb-1">단점·리스크</div>
                  <ul className="flex flex-col gap-1">
                    {archs[tab].cons.map((c, i) => (
                      <li key={i} className="text-xs text-(--color-muted) flex gap-1">
                        <span className="text-amber-400">−</span> {c}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2) 토론 전사 (대화) */}
      {debate.transcript?.length > 0 && (
        <div>
          <div className="text-xs font-medium text-(--color-muted) mb-2">
            토론 전사 ({debate.rounds}라운드 · {debate.transcript.length}턴)
          </div>
          <div className="flex flex-col gap-2.5">
            {debate.transcript.map((t, i) => {
              const meta = ROLE_META[t.role] ?? ROLE_META.synthesizer
              return (
                <div key={i} className={`flex flex-col ${meta.align}`}>
                  <div className={`max-w-[88%] rounded-lg border px-3 py-2 ${meta.color}`}>
                    <div className="text-[11px] font-medium text-(--color-muted) mb-1">
                      {meta.label} · R{t.round}
                    </div>
                    <div className="blog-md text-sm text-(--color-text)">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.text}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 3) 합의 결론 */}
      {debate.verdict && (
        <div className="rounded border border-(--color-accent)/40 bg-(--color-accent)/5 p-3 flex flex-col gap-2">
          <div className="text-xs font-medium text-(--color-accent)">
            합의 결론 — {debate.verdict.chosen}
          </div>
          {debate.verdict.rationale && (
            <div className="blog-md text-sm text-(--color-text)">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{debate.verdict.rationale}</ReactMarkdown>
            </div>
          )}
          {debate.verdict.key_insights?.length > 0 && (
            <div>
              <div className="text-xs font-medium text-(--color-muted) mb-1">핵심 인사이트</div>
              <ul className="flex flex-col gap-1">
                {debate.verdict.key_insights.map((k, i) => (
                  <li key={i} className="text-xs text-(--color-text) flex gap-1">
                    <span className="text-(--color-accent)">›</span> {k}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {debate.verdict.open_questions?.length > 0 && (
            <div>
              <div className="text-xs font-medium text-(--color-muted) mb-1">열린 질문</div>
              <ul className="flex flex-col gap-1">
                {debate.verdict.open_questions.map((q, i) => (
                  <li key={i} className="text-xs text-(--color-muted) flex gap-1">
                    <span className="text-amber-400">?</span> {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DeepDive({ section, defaultOpen }: { section: DeepDiveSection; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded border border-(--color-border) bg-(--color-bg)">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm font-medium text-(--color-text) hover:text-(--color-accent)"
      >
        <span className="text-(--color-muted)">{open ? '▾' : '▸'}</span>
        {section.topic}
      </button>
      {open && (
        <div className="blog-md px-4 pb-4 pt-1 text-(--color-text)">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.body}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-(--color-muted) mb-2">{title}</div>
      {children}
    </div>
  )
}

function Tag({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <span
      className={`px-2 py-0.5 text-xs rounded border ${
        accent
          ? 'bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40'
          : 'bg-(--color-bg) text-(--color-text) border-(--color-border)'
      }`}
    >
      {children}
    </span>
  )
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-1 text-xs rounded transition border ${
        active
          ? 'bg-(--color-accent) text-black border-(--color-accent) font-medium'
          : 'bg-(--color-bg) text-(--color-text) border-(--color-border) hover:border-(--color-accent)'
      }`}
    >
      {children}
    </button>
  )
}
