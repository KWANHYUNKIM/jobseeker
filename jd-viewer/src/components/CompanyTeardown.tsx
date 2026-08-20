import { useMemo, useState } from 'react'
import {
  useCompany,
  type Confidence,
  type Diagram,
  type Feature,
  type Source,
} from '../lib/useReveng'
import { ArchitectureDiagram } from './ArchitectureDiagram'
import { Loader, ErrorState } from './ui'

// 회사 하나의 역설계 상세.
//
// 화면 순서가 곧 이해 순서다: 무엇으로 돈을 버는가 → 그 돈이 어떤 도메인으로 쪼개지는가
// → 각 기능이 어떻게 구현됐는가 → 기능끼리 어떻게 이어지는가. 기술 스택을 맨 위에 두면
// 또 하나의 '기술 나열'이 되므로 일부러 맨 아래에 둔다.

const CONF_LABEL: Record<Confidence, string> = {
  confirmed: '확인',
  inferred: '추정',
  unknown: '미확인',
}

export function CompanyTeardown({ slug, onBack }: { slug: string; onBack: () => void }) {
  const { data: c, loading, error } = useCompany(slug)
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [domain, setDomain] = useState<string | null>(null)

  const features = useMemo(
    () => (c?.features ?? []).filter((f) => !domain || f.domain === domain),
    [c, domain],
  )

  if (loading) return <Loader label="회사 데이터 불러오는 중…" />
  if (error || !c)
    return (
      <ErrorState
        title={`reveng/companies/${slug}.json 로드 실패`}
        detail={error ?? '데이터 없음'}
        hint={<button onClick={onBack} className="underline">목록으로 돌아가기</button>}
      />
    )

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0 overflow-y-auto">
      <header className="px-4 py-3 border-b border-(--color-border) bg-(--color-panel) sticky top-0 z-10">
        <button
          onClick={onBack}
          className="text-xs text-(--color-muted) hover:text-(--color-accent) mb-1"
        >
          ← 회사 목록
        </button>
        <div className="flex items-baseline gap-2 flex-wrap">
          <h2 className="text-lg font-semibold text-(--color-text)">{c.name}</h2>
          <span className="text-sm text-(--color-muted)">{c.name_en}</span>
          <span className="text-[11px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-muted)">
            {c.category}
          </span>
          <span className="ml-auto text-[11px] text-(--color-muted)">갱신 {c.updated_at}</span>
        </div>
        <p className="text-xs text-(--color-muted) mt-1">{c.one_liner}</p>
      </header>

      <div className="p-4 flex flex-col gap-6 max-w-4xl">
        <Section title="비즈니스 모델" sub="이 회사는 무엇을 팔아 돈을 버는가">
          <p className="text-sm text-(--color-text) leading-relaxed">{c.business_model}</p>
          {c.products?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {c.products.map((p) => (
                <span key={p} className="px-2 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-xs text-(--color-muted)">
                  {p}
                </span>
              ))}
            </div>
          )}
          {c.revenue_streams && c.revenue_streams.length > 0 && (
            <ul className="mt-3 flex flex-col gap-2">
              {c.revenue_streams.map((r) => (
                <li key={r.name} className="text-sm">
                  <span className="text-(--color-text) font-medium">{r.name}</span>
                  <ConfBadge c={r.confidence} />
                  <span className="text-(--color-muted)"> — {r.how}</span>
                  <SourceLinks sources={r.sources} />
                </li>
              ))}
            </ul>
          )}
        </Section>

        {c.domain_map?.code && (
          <Section title="도메인 지도" sub={c.domain_map.question ?? '도메인들이 어떻게 맞물리는가'}>
            <DiagramBlock d={c.domain_map} idKey={`reveng-${c.slug}-map`} />
          </Section>
        )}

        {c.domains && c.domains.length > 0 && (
          <Section title="도메인" sub="조직도가 아니라 문제의 경계로 나눈 단위">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {c.domains.map((d) => {
                const n = (c.features ?? []).filter((f) => f.domain === d.name).length
                const on = domain === d.name
                return (
                  <button
                    key={d.name}
                    onClick={() => setDomain(on ? null : d.name)}
                    className={
                      'text-left rounded border p-2.5 transition-colors ' +
                      (on
                        ? 'border-(--color-accent) bg-(--color-accent)/5'
                        : 'border-(--color-border) hover:border-(--color-accent)/50')
                    }
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-(--color-text)">{d.name}</span>
                      <span className="ml-auto text-[11px] text-(--color-muted) tabular-nums">
                        기능 {n}
                      </span>
                    </div>
                    <p className="text-xs text-(--color-muted) mt-1 leading-relaxed">{d.why}</p>
                    {d.tech && d.tech.length > 0 && (
                      <ul className="mt-2 flex flex-col gap-1.5 border-t border-(--color-border) pt-2">
                        {d.tech.map((t) => (
                          <li key={t.tech} className="text-xs leading-relaxed">
                            <span className="text-(--color-accent)">{t.tech}</span>
                            <ConfBadge c={t.confidence} />
                            <span className="text-(--color-muted)"> — {t.solves}</span>
                            <div className="text-(--color-muted) opacity-80">
                              <span className="opacity-70">못 하는 것 </span>
                              {t.limits}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </button>
                )
              })}
            </div>
          </Section>
        )}

        <Section
          title={domain ? `기능 — ${domain}` : '기능'}
          sub="왜 존재하는가 → 도메인 규칙 → 구현과 트레이드오프 → 다른 시스템과의 연결"
        >
          {features.length === 0 ? (
            <p className="text-sm text-(--color-muted)">
              아직 채워진 기능이 없습니다. 엔진이 사이클을 돌면 하나씩 쌓입니다.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {features.map((f) => (
                <FeatureBlock
                  key={f.key}
                  f={f}
                  open={openKey === f.key}
                  onToggle={() => setOpenKey(openKey === f.key ? null : f.key)}
                />
              ))}
            </div>
          )}
        </Section>

        {c.open_questions && c.open_questions.length > 0 && (
          <Section title="확인 못 한 것" sub="공개 자료로 닿지 못한 부분 — 그럴듯하게 채우지 않는다">
            <ul className="list-disc pl-5 text-sm text-(--color-muted) flex flex-col gap-1">
              {c.open_questions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </Section>
        )}

        {c.sources && c.sources.length > 0 && (
          <Section title="근거" sub="회사가 공개한 자료. 요약은 한 줄까지만 옮긴다">
            <SourceList sources={c.sources} />
          </Section>
        )}
      </div>
    </div>
  )
}

function FeatureBlock({ f, open, onToggle }: { f: Feature; open: boolean; onToggle: () => void }) {
  const impl = f.implementation ?? {}
  return (
    <div className="rounded border border-(--color-border) bg-(--color-panel)">
      <button onClick={onToggle} className="w-full text-left px-3 py-2.5 flex items-center gap-2">
        <span className="text-(--color-muted) text-xs">{open ? '▾' : '▸'}</span>
        <span className="text-sm font-medium text-(--color-text) shrink-0 whitespace-nowrap">{f.name}</span>
        <span className="shrink-0 whitespace-nowrap text-[11px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-muted)">
          {f.domain}
        </span>
        {!open && (
          <span className="hidden sm:block text-xs text-(--color-muted) truncate ml-1">
            {f.business.why}
          </span>
        )}
        <span className="ml-auto text-[11px] text-(--color-muted) tabular-nums shrink-0">
          결정 {impl.decisions?.length ?? 0}
        </span>
      </button>

      {open && (
        <div className="px-3 pb-4 pt-1 flex flex-col gap-4 border-t border-(--color-border)">
          <Sub title="왜 존재하나">
            <p className="text-sm text-(--color-text) leading-relaxed">{f.business.why}</p>
            {f.business.metrics && f.business.metrics.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {f.business.metrics.map((m) => (
                  <span
                    key={m.label}
                    className="px-2 py-1 rounded bg-(--color-bg) border border-(--color-border) text-xs"
                  >
                    <span className="text-(--color-muted)">{m.label} </span>
                    <span className="text-(--color-text) font-medium tabular-nums">{m.value}</span>
                    <ConfBadge c={m.confidence} />
                  </span>
                ))}
              </div>
            )}
          </Sub>

          {f.thinking && f.thinking.length > 0 && (
            <Sub title="그때 무슨 생각을 했나">
              <ul className="flex flex-col gap-2">
                {f.thinking.map((t, i) => (
                  <li key={i} className="text-sm border-l-2 border-(--color-border) pl-2.5">
                    <span className="text-[11px] text-(--color-muted)">{t.at}</span>
                    <ConfBadge c={t.confidence} />
                    <div className="text-(--color-text) leading-relaxed">{t.thought}</div>
                  </li>
                ))}
              </ul>
            </Sub>
          )}

          {f.domain_model && (
            <Sub title="도메인 모델">
              {f.domain_model.entities && f.domain_model.entities.length > 0 && (
                <ul className="text-sm flex flex-col gap-1">
                  {f.domain_model.entities.map((e) => (
                    <li key={e.name}>
                      <span className="text-(--color-accent)">{e.name}</span>
                      <span className="text-(--color-muted)"> — {e.what}</span>
                    </li>
                  ))}
                </ul>
              )}
              {f.domain_model.invariants && f.domain_model.invariants.length > 0 && (
                <>
                  <p className="text-[11px] text-(--color-muted) mt-2 mb-1">
                    불변식 — 코드보다 오래 사는 규칙
                  </p>
                  <ul className="list-disc pl-5 text-sm text-(--color-text) flex flex-col gap-1">
                    {f.domain_model.invariants.map((i) => (
                      <li key={i}>{i}</li>
                    ))}
                  </ul>
                </>
              )}
            </Sub>
          )}

          {impl.flow && impl.flow.length > 0 && (
            <Sub title="흐름">
              <ol className="flex flex-col gap-1.5">
                {impl.flow.map((s, i) => (
                  <li key={i} className="text-sm flex gap-2">
                    <span className="shrink-0 w-5 h-5 rounded-full bg-(--color-bg) border border-(--color-border) text-[11px] flex items-center justify-center text-(--color-muted) tabular-nums">
                      {i + 1}
                    </span>
                    <span>
                      <span className="text-(--color-text)">{s.step}</span>
                      {s.why && <span className="text-(--color-muted)"> — {s.why}</span>}
                    </span>
                  </li>
                ))}
              </ol>
            </Sub>
          )}

          {f.diagrams && f.diagrams.length > 0 ? (
            <Sub title="그림">
              <div className="flex flex-col gap-4">
                {f.diagrams.map((d, i) => (
                  <DiagramBlock key={i} d={d} idKey={`reveng-${f.key}-${i}`} />
                ))}
              </div>
            </Sub>
          ) : f.diagram ? (
            <Sub title="구조">
              <ArchitectureDiagram code={f.diagram} idKey={`reveng-${f.key}`} />
            </Sub>
          ) : null}

          {impl.decisions && impl.decisions.length > 0 && (
            <Sub title="의사결정과 대가">
              <div className="flex flex-col gap-2.5">
                {impl.decisions.map((d, i) => (
                  <div key={i} className="rounded border border-(--color-border) p-2.5 bg-(--color-bg)">
                    <div className="text-xs text-(--color-muted)">{d.question}</div>
                    <div className="text-sm mt-1">
                      <span className="text-(--color-accent) font-medium">{d.chosen}</span>
                      <ConfBadge c={d.confidence} />
                      {d.alternatives && d.alternatives.length > 0 && (
                        <span className="text-(--color-muted)">
                          {' '}
                          · 버린 대안: {d.alternatives.join(', ')}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-(--color-text) mt-1.5">
                      <span className="text-(--color-muted) text-xs">대가 </span>
                      {d.tradeoff}
                    </div>
                    <SourceLinks sources={d.sources} />
                  </div>
                ))}
              </div>
            </Sub>
          )}

          {f.connections && f.connections.length > 0 && (
            <Sub title="연결">
              <ul className="flex flex-col gap-1.5">
                {f.connections.map((c, i) => (
                  <li key={i} className="text-sm">
                    <span className="text-(--color-muted)">→ </span>
                    <span className="text-(--color-text)">{c.to}</span>
                    <span className="text-(--color-muted)"> · {c.via}</span>
                    <ConfBadge c={c.confidence} />
                    {c.contract && (
                      <div className="text-xs text-(--color-muted) pl-4">{c.contract}</div>
                    )}
                  </li>
                ))}
              </ul>
            </Sub>
          )}

          {impl.stack && impl.stack.length > 0 && (
            <Sub title="스택">
              <ul className="flex flex-col gap-1">
                {impl.stack.map((s) => (
                  <li key={s.tech} className="text-sm">
                    <span className="text-(--color-text) font-medium">{s.tech}</span>
                    <ConfBadge c={s.confidence} />
                    <span className="text-(--color-muted)"> — {s.role}</span>
                  </li>
                ))}
              </ul>
            </Sub>
          )}

          {f.sources && f.sources.length > 0 && (
            <Sub title="근거">
              <SourceList sources={f.sources} />
            </Sub>
          )}
        </div>
      )}
    </div>
  )
}

const KIND_LABEL: Record<string, string> = {
  flow: '흐름',
  sequence: '흐름',
  state: '상태 전이',
  failure: '실패 경로',
}

function DiagramBlock({ d, idKey }: { d: Diagram; idKey: string }) {
  return (
    <figure className="m-0">
      <figcaption className="mb-1.5">
        <span className="text-sm font-medium text-(--color-text)">{d.title}</span>
        {d.kind && (
          <span className="ml-1.5 text-[10px] px-1 py-px rounded border border-(--color-border) text-(--color-muted)">
            {KIND_LABEL[d.kind] ?? d.kind}
          </span>
        )}
        {d.question && (
          <div className="text-xs text-(--color-muted)">{d.question}</div>
        )}
      </figcaption>
      <ArchitectureDiagram code={d.code} idKey={idKey} />
    </figure>
  )
}

function ConfBadge({ c }: { c?: Confidence }) {
  if (!c || c === 'confirmed') return null // '확인'은 기본값 — 뱃지로 화면을 채우지 않는다
  return (
    <span
      className={
        'ml-1.5 align-middle px-1 py-px rounded text-[10px] border ' +
        (c === 'inferred'
          ? 'border-amber-500/40 text-amber-500'
          : 'border-(--color-border) text-(--color-muted)')
      }
      title={c === 'inferred' ? '공개 자료에서 추론한 내용' : '공개 자료로 확인하지 못함'}
    >
      {CONF_LABEL[c]}
    </span>
  )
}

function SourceLinks({ sources }: { sources?: Source[] }) {
  if (!sources || sources.length === 0) return null
  return (
    <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1">
      {sources.map((s) => (
        <a
          key={s.url}
          href={s.url}
          target="_blank"
          rel="noreferrer noopener"
          className="text-[11px] text-(--color-accent) hover:underline"
          title={s.title}
        >
          {s.publisher || new URL(s.url).hostname}
        </a>
      ))}
    </div>
  )
}

function SourceList({ sources }: { sources: Source[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {sources.map((s) => (
        <li key={s.url} className="text-sm">
          <a
            href={s.url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-(--color-accent) hover:underline"
          >
            {s.title}
          </a>
          <span className="text-[11px] text-(--color-muted)">
            {s.publisher ? ` · ${s.publisher}` : ''}
            {s.date ? ` · ${s.date}` : ''}
          </span>
          {s.summary && <div className="text-xs text-(--color-muted)">{s.summary}</div>}
        </li>
      ))}
    </ul>
  )
}

function Section({
  title,
  sub,
  children,
}: {
  title: string
  sub?: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h3 className="text-base font-semibold text-(--color-text)">
        {title}
        {sub && <span className="ml-2 text-xs font-normal text-(--color-muted)">{sub}</span>}
      </h3>
      <div className="mt-2">{children}</div>
    </section>
  )
}

function Sub({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-(--color-muted) mb-1.5">{title}</div>
      {children}
    </div>
  )
}
