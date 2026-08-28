import { useMemo, useState } from 'react'
import { useCompany, type Diagram, type Feature, type Source } from '../lib/useReveng'
import { ArchitectureDiagram } from './ArchitectureDiagram'
import { CompanyLogo } from './RevengView'
import { UiSketch } from './UiSketch'
import { ConfBadge, SourceLinks } from './RevengBits'
import { Md, MdBlock } from './Md'
import { Loader, ErrorState } from './ui'

// 접힌 줄의 한 줄 미리보기처럼 마크업이 방해가 되는 자리에서만 기호를 걷어낸다.
const strip = (s: string) => s.replace(/\*\*|`|\*/g, '')

// 엔티티는 스키마상 {name, what} 이지만 초기 사이클들이 "이름 — 설명" 한 문자열로
// 적어 둔 것이 남아 있다. 객체만 읽으면 그쪽이 통째로 빈 줄이 되므로 둘 다 받는다.
function normEntity(e: { name: string; what: string } | string): { name: string; what: string } {
  if (typeof e !== 'string') return e
  const cut = e.indexOf(' — ')
  return cut < 0 ? { name: e, what: '' } : { name: e.slice(0, cut), what: e.slice(cut + 3) }
}

// 회사 하나의 역설계 상세.
//
// 화면 순서가 곧 이해 순서다: 무엇으로 돈을 버는가 → 그 돈이 어떤 도메인으로 쪼개지는가
// → 각 기능이 어떻게 구현됐는가 → 기능끼리 어떻게 이어지는가. 기술 스택을 맨 위에 두면
// 또 하나의 '기술 나열'이 되므로 일부러 맨 아래에 둔다.


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
          <span className="self-center">
            <CompanyLogo domain={c.domain} name={c.name} size={32} />
          </span>
          <h2 className="text-lg font-semibold text-(--color-text)"><span className="jd-head jd-head-lg">{c.name}</span></h2>
          <span className="text-sm text-(--color-muted)">{c.name_en}</span>
          <span className="text-xs px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-muted)">
            {c.category}
          </span>
          <span className="ml-auto text-xs text-(--color-muted)">갱신 {c.updated_at}</span>
        </div>
        <p className="text-xs text-(--color-muted) mt-1">{c.one_liner}</p>
      </header>

      {/* 본문 줄길이는 .reveng-prose(74ch)가 잡는다. 바깥 폭까지 좁히면 그림이
          화면 절반만 쓰게 되므로, 컨테이너는 넓게 두고 글만 좁힌다. */}
      <div className="p-4 flex flex-col gap-7 max-w-[1400px]">
        <Section title="비즈니스 모델" sub="이 회사는 무엇을 팔아 돈을 버는가">
          <MdBlock className="reveng-prose text-sm text-(--color-text)">{c.business_model}</MdBlock>
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
                  <span className="text-(--color-text) font-medium"><Md>{r.name}</Md></span>
                  <ConfBadge c={r.confidence} />
                  <span className="text-(--color-muted)"> — <Md>{r.how}</Md></span>
                  <SourceLinks sources={r.sources} />
                </li>
              ))}
            </ul>
          )}
        </Section>

        {/* 화면 도해가 있으면 그쪽이 입구다 — 사용자가 실제로 누르는 것에서 시작하는 편이
            추상적인 네모에서 시작하는 것보다 붙들기 쉽다. 그때 mermaid 도메인 지도는
            같은 일을 두 번 하게 되므로 접어 둔다(지우지는 않는다 — 관계는 저쪽이 정확하다). */}
        {c.ui_map && (
          <Section title="화면에서 시작하기" sub={c.ui_map.question ?? '사용자가 보는 이 부분이 어느 도메인인가'}>
            <UiSketch ui={c.ui_map} idKey={`reveng-${c.slug}-uimap`} onPickDomain={setDomain} />
          </Section>
        )}

        {c.domain_map?.code &&
          (c.ui_map ? (
            <details className="rounded border border-(--color-border) px-3 py-2">
              <summary className="cursor-pointer text-sm text-(--color-muted) hover:text-(--color-accent)">
                도메인 지도(추상) 펼치기 —{' '}
                {c.domain_map.question ?? '도메인들이 어떻게 맞물리는가'}
              </summary>
              <div className="mt-3">
                <DiagramBlock d={c.domain_map} idKey={`reveng-${c.slug}-map`} />
              </div>
            </details>
          ) : (
            <Section title="도메인 지도" sub={c.domain_map.question ?? '도메인들이 어떻게 맞물리는가'}>
              <DiagramBlock d={c.domain_map} idKey={`reveng-${c.slug}-map`} />
            </Section>
          ))}

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
                      <span className="ml-auto text-xs text-(--color-muted) tabular-nums">
                        기능 {n}
                      </span>
                    </div>
                    <p className="text-xs text-(--color-muted) mt-1 leading-relaxed reveng-prose"><Md>{d.why}</Md></p>
                    {d.tech && d.tech.length > 0 && (
                      <ul className="mt-2 flex flex-col gap-1.5 border-t border-(--color-border) pt-2">
                        {d.tech.map((t) => (
                          <li key={t.tech} className="text-xs leading-relaxed">
                            <span className="text-(--color-accent)"><Md>{t.tech}</Md></span>
                            <ConfBadge c={t.confidence} />
                            <span className="text-(--color-muted)"> — <Md>{t.solves}</Md></span>
                            <div className="text-(--color-muted) opacity-80">
                              <span className="opacity-70">못 하는 것 </span>
                              <Md>{t.limits}</Md>
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
                <li key={q}><Md>{q}</Md></li>
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
        <span className="shrink-0 whitespace-nowrap text-xs px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-muted)">
          {f.domain}
        </span>
        {!open && (
          <span className="hidden sm:block text-xs text-(--color-muted) truncate ml-1">
            {strip(f.business.why)}
          </span>
        )}
        <span className="ml-auto text-xs text-(--color-muted) tabular-nums shrink-0">
          결정 {impl.decisions?.length ?? 0}
        </span>
      </button>

      {open && (
        <div className="px-3 pb-4 pt-1 flex flex-col gap-4 border-t border-(--color-border)">
          {/* 글보다 화면이 먼저다. '이 기능' 이 앱의 어느 자리인지를 붙들고 나서
              왜 그렇게 만들었는지를 읽는 편이 순서가 맞다. */}
          {f.ui && (
            <Sub title="사용자가 보는 자리">
              <UiSketch ui={f.ui} idKey={`reveng-ui-${f.key}`} />
            </Sub>
          )}

          <Sub title="왜 존재하나">
            <MdBlock className="reveng-prose text-sm text-(--color-text)">{f.business.why}</MdBlock>
            {f.business.metrics && f.business.metrics.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {f.business.metrics.map((m) => (
                  <span
                    key={m.label}
                    className="px-2 py-1 rounded bg-(--color-bg) border border-(--color-border) text-xs"
                  >
                    <span className="text-(--color-muted)"><Md>{m.label}</Md> </span>
                    <span className="text-(--color-text) font-medium tabular-nums"><Md>{m.value}</Md></span>
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
                    <span className="text-xs text-(--color-muted)">{t.at}</span>
                    <ConfBadge c={t.confidence} />
                    <div className="text-(--color-text) leading-relaxed reveng-prose"><Md>{t.thought}</Md></div>
                  </li>
                ))}
              </ul>
            </Sub>
          )}

          {f.domain_model && (
            <Sub title="도메인 모델">
              {f.domain_model.entities && f.domain_model.entities.length > 0 && (
                <ul className="text-sm flex flex-col gap-1">
                  {f.domain_model.entities.map((raw, i) => {
                    const e = normEntity(raw)
                    return (
                      <li key={i}>
                        <span className="text-(--color-accent)"><Md>{e.name}</Md></span>
                        {e.what && (
                          <span className="text-(--color-muted)">
                            {' — '}
                            <Md>{e.what}</Md>
                          </span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
              {f.domain_model.invariants && f.domain_model.invariants.length > 0 && (
                <>
                  <p className="text-xs text-(--color-muted) mt-2 mb-1">
                    불변식 — 코드보다 오래 사는 규칙
                  </p>
                  <ul className="list-disc pl-5 text-sm text-(--color-text) flex flex-col gap-1">
                    {f.domain_model.invariants.map((i) => (
                      <li key={i}><Md>{i}</Md></li>
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
                    <span className="shrink-0 w-5 h-5 rounded-full bg-(--color-bg) border border-(--color-border) text-xs flex items-center justify-center text-(--color-muted) tabular-nums">
                      {i + 1}
                    </span>
                    <span>
                      <span className="text-(--color-text)"><Md>{s.step}</Md></span>
                      {s.why && <span className="text-(--color-muted)"> — <Md>{s.why}</Md></span>}
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
                    <div className="text-xs text-(--color-muted) mt-0.5 reveng-prose"><Md>{d.question}</Md></div>
                    <div className="text-sm mt-1">
                      <span className="text-(--color-accent) font-medium">
                        <Md>{d.chosen}</Md>
                      </span>
                      <ConfBadge c={d.confidence} />
                      {d.alternatives && d.alternatives.length > 0 && (
                        <span className="text-(--color-muted)">
                          {' · 버린 대안: '}
                          {d.alternatives.map((a, k) => (
                            <span key={k}>
                              {k > 0 && ', '}
                              <Md>{a}</Md>
                            </span>
                          ))}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-(--color-text) mt-1.5">
                      <span className="text-(--color-muted) text-xs">대가 </span>
                      <Md>{d.tradeoff}</Md>
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
                    <span className="text-(--color-muted)"> · <Md>{c.via}</Md></span>
                    <ConfBadge c={c.confidence} />
                    {c.contract && (
                      <div className="text-xs text-(--color-muted) pl-4"><Md>{c.contract}</Md></div>
                    )}
                  </li>
                ))}
              </ul>
            </Sub>
          )}

          {(f.research?.papers?.length || f.research?.hard_problems?.length) ? (
            <Sub title="회사 밖의 근거">
              {f.research.papers && f.research.papers.length > 0 && (
                <ul className="flex flex-col gap-2">
                  {f.research.papers.map((p) => (
                    <li key={p.url} className="text-sm">
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-(--color-accent) hover:underline"
                      >
                        {p.title}
                      </a>
                      <ConfBadge c={p.confidence} />
                      <span className="text-xs text-(--color-muted)">
                        {p.venue ? ` · ${p.venue}` : ''}
                        {p.year ? ` · ${p.year}` : ''}
                        {p.authors ? ` · ${p.authors}` : ''}
                      </span>
                      {/* 논문 요약이 아니라 '이 회사가 무엇을 가져다 썼는가' */}
                      <div className="text-xs text-(--color-muted) reveng-prose">
                        <Md>{p.takeaway}</Md>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {f.research.hard_problems && f.research.hard_problems.length > 0 && (
                <>
                  <p className="text-xs text-(--color-muted) mt-3 mb-1">
                    아직 아무도 못 푼 것 — 내가 못 찾은 것(확인 못 한 것)과는 다르다
                  </p>
                  <div className="flex flex-col gap-2">
                    {f.research.hard_problems.map((h, i) => (
                      <div
                        key={i}
                        className="rounded border border-amber-500/25 bg-(--color-bg) p-2.5"
                      >
                        <div className="text-sm text-(--color-text)">
                          <Md>{h.problem}</Md>
                          <ConfBadge c={h.confidence} />
                        </div>
                        <div className="text-xs text-(--color-muted) mt-1 reveng-prose">
                          <span className="opacity-70">왜 어려운가 </span>
                          <Md>{h.why_hard}</Md>
                        </div>
                        {h.current_best && (
                          <div className="text-xs text-(--color-muted) mt-1 reveng-prose">
                            <span className="opacity-70">지금의 차선 </span>
                            <Md>{h.current_best}</Md>
                          </div>
                        )}
                        <SourceLinks sources={h.sources} />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </Sub>
          ) : null}

          {impl.stack && impl.stack.length > 0 && (
            <Sub title="스택">
              <ul className="flex flex-col gap-1">
                {impl.stack.map((s) => (
                  <li key={s.tech} className="text-sm">
                    <span className="text-(--color-text) font-medium"><Md>{s.tech}</Md></span>
                    <ConfBadge c={s.confidence} />
                    <span className="text-(--color-muted)"> — <Md>{s.role}</Md></span>
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
        <span className="text-sm font-medium text-(--color-text)"><Md>{d.title}</Md></span>
        {d.kind && (
          <span className="ml-1.5 text-xs px-1 py-px rounded border border-(--color-border) text-(--color-muted)">
            {KIND_LABEL[d.kind] ?? d.kind}
          </span>
        )}
        {d.question && (
          <div className="text-xs text-(--color-muted) mt-0.5 reveng-prose"><Md>{d.question}</Md></div>
        )}
      </figcaption>
      <ArchitectureDiagram code={d.code} idKey={idKey} />
    </figure>
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
          <span className="text-xs text-(--color-muted)">
            {s.publisher ? ` · ${s.publisher}` : ''}
            {s.date ? ` · ${s.date}` : ''}
          </span>
          {s.summary && <div className="text-xs text-(--color-muted)"><Md>{s.summary}</Md></div>}
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
        <span className="jd-head">{title}</span>
        {sub && <span className="ml-2 text-xs font-normal text-(--color-muted)">{sub}</span>}
      </h3>
      <div className="mt-2">{children}</div>
    </section>
  )
}

function Sub({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-(--color-muted) mb-1.5">{title}</div>
      {children}
    </div>
  )
}
