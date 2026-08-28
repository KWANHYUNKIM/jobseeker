import { useEffect, useRef, useState } from 'react'
import {
  useJobGuide,
  sortStudy,
  PRIORITY_LABEL,
  PRIORITY_COLOR,
  FROM_LABEL,
  type CompanyGuide,
  type GuidePosting,
  type Source,
  type StudyItem,
} from '../lib/useGuide'

interface Props {
  company: string
  url: string
  /** 지금 본문에서 하이라이트 중인 문장. 학습 항목을 펼치면 그 항목의 quote 가 된다. */
  activeQuote: string | null
  onQuote: (q: string | null) => void
}

/**
 * 공고 오른쪽에 붙는 취업 브리핑 패널.
 *
 * 왼쪽 JD 가 "회사가 원하는 것"이라면 여기는 "그래서 내가 뭘 하나"다. 두 개를 같은
 * 화면에 놓는 것이 이 화면의 전부다 — 공고를 닫고 다른 탭에서 공부거리를 찾는 순간
 * 어느 문장 때문에 그걸 공부하는지가 끊긴다. 그래서 학습 항목마다 원문 문장을 들고
 * 있고, 항목을 펼치면 왼쪽 본문의 그 문장이 켜진다.
 */
export function JobGuide({ company, url, activeQuote, onQuote }: Props) {
  const { loading, guide, posting } = useJobGuide(company, url)

  if (loading) {
    return (
      <PanelShell>
        <p className="text-xs text-(--color-muted)">가이드 불러오는 중…</p>
      </PanelShell>
    )
  }

  if (!guide) return <NotYet company={company} kind="company" />
  if (!posting) return <NotYet company={company} kind="posting" guide={guide} />

  return (
    <PanelShell>
      <GuideHeader guide={guide} posting={posting} />
      <StudySection posting={posting} activeQuote={activeQuote} onQuote={onQuote} />
      <EdgeSection posting={posting} />
      <InterviewSection posting={posting} />
      <SalarySection guide={guide} />
      <PeopleSection guide={guide} />
      <CompanySection guide={guide} />
      {guide.open_questions && guide.open_questions.length > 0 && (
        <Block title="아직 모르는 것" icon="❓">
          <ul className="space-y-1">
            {guide.open_questions.map((q, i) => (
              <li key={i} className="text-xs text-(--color-muted) leading-relaxed">
                · {q}
              </li>
            ))}
          </ul>
        </Block>
      )}
      <p className="text-[11px] text-(--color-faint) leading-relaxed pt-1">
        공개 자료로 재구성한 브리핑입니다. <Badge>추정</Badge> 이 붙은 항목은 확인된 사실이
        아니라 공개 자료에서 추론한 것입니다. {guide.updated_at} 기준.
      </p>
    </PanelShell>
  )
}

function PanelShell({ children }: { children: React.ReactNode }) {
  return <div className="space-y-4">{children}</div>
}

// ── 브리핑이 아직 없을 때 ────────────────────────────────────────────────
// 빈 패널을 그냥 두지 않는 이유: 이 화면에서 "왜 비었는지"와 "어떻게 채우는지"를
// 안 알려주면, 며칠 뒤엔 이 자리가 원래 비어 있는 자리인 줄 알게 된다.
function NotYet({
  company,
  kind,
  guide,
}: {
  company: string
  kind: 'company' | 'posting'
  guide?: CompanyGuide
}) {
  return (
    <PanelShell>
      <div className="border border-dashed border-(--color-border) rounded-lg p-4">
        <h3 className="text-sm font-medium text-(--color-text) mb-1.5">
          {kind === 'company' ? '아직 조사하지 않은 회사입니다' : '이 공고는 아직입니다'}
        </h3>
        <p className="text-xs text-(--color-muted) leading-relaxed">
          {kind === 'company' ? (
            <>
              <span className="text-(--color-text)">{company}</span> 의 학습 로드맵·연봉·인물
              조사가 아직 없습니다. 취업 브리핑 엔진이 대기열 순서대로 한 사이클에 한 곳씩
              채웁니다.
            </>
          ) : (
            <>
              <span className="text-(--color-text)">{company}</span> 회사 브리핑은 있지만 이
              공고는 아직 안 채웠습니다. 아래 회사 정보는 지금도 볼 수 있습니다.
            </>
          )}
        </p>
        <pre className="mt-3 text-[11px] bg-(--color-bg) border border-(--color-border) rounded px-2.5 py-2 overflow-x-auto text-(--color-muted)">
          {kind === 'company'
            ? `# guide-engine/state/QUEUE.md 의 "## 대기" 에 추가한 뒤\n/loop 30m /hireguide`
            : `/loop 30m /hireguide`}
        </pre>
      </div>
      {guide && (
        <>
          <SalarySection guide={guide} />
          <PeopleSection guide={guide} />
          <CompanySection guide={guide} />
        </>
      )}
    </PanelShell>
  )
}

// ── 헤더 ────────────────────────────────────────────────────────────────
function GuideHeader({ guide, posting }: { guide: CompanyGuide; posting: GuidePosting }) {
  const study = posting.study || []
  const hours = study.reduce((s, x) => s + (x.hours || 0), 0)
  const core = study.filter((s) => s.priority === 'core').length

  return (
    <div className="rounded-lg border border-(--color-accent)/30 bg-(--color-accent)/8 p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-xs font-medium tracking-wider text-(--color-accent)">
          이 회사 가려면
        </span>
        {guide.status === 'in_progress' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-faint)">
            작성 중
          </span>
        )}
      </div>
      <p className="text-sm text-(--color-text) leading-relaxed">{posting.verdict}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2.5 text-xs text-(--color-muted) tabular-nums">
        <span>
          학습 <span className="text-(--color-text) font-medium">{study.length}</span>개
        </span>
        {core > 0 && (
          <span>
            필수 <span className="text-(--color-text) font-medium">{core}</span>개
          </span>
        )}
        {hours > 0 && (
          <span>
            대략 <span className="text-(--color-text) font-medium">{hours}</span>시간
          </span>
        )}
      </div>
      {posting.fit && (posting.fit.must_have?.length || posting.fit.can_learn?.length) ? (
        <div className="mt-3 pt-3 border-t border-(--color-accent)/20 grid gap-2">
          {posting.fit.must_have && posting.fit.must_have.length > 0 && (
            <FitRow label="없으면 걸린다" items={posting.fit.must_have} tone="core" />
          )}
          {posting.fit.can_learn && posting.fit.can_learn.length > 0 && (
            <FitRow label="지금 없어도 된다" items={posting.fit.can_learn} tone="nice" />
          )}
        </div>
      ) : null}
    </div>
  )
}

function FitRow({ label, items, tone }: { label: string; items: string[]; tone: 'core' | 'nice' }) {
  return (
    <div className="flex gap-2 items-baseline">
      <span
        className="text-[10px] shrink-0 px-1.5 py-0.5 rounded border"
        style={{ borderColor: PRIORITY_COLOR[tone], color: PRIORITY_COLOR[tone] }}
      >
        {label}
      </span>
      <span className="text-xs text-(--color-muted) leading-relaxed">{items.join(' · ')}</span>
    </div>
  )
}

// ── 학습 로드맵 ──────────────────────────────────────────────────────────
function StudySection({
  posting,
  activeQuote,
  onQuote,
}: {
  posting: GuidePosting
  activeQuote: string | null
  onQuote: (q: string | null) => void
}) {
  const items = sortStudy(posting.study || [])
  const [open, setOpen] = useState(0)

  // 왼쪽 본문의 문장을 눌러서 들어온 경우 — 그 항목이 펼쳐져야 한다. 펼침 상태를 여기서만
  // 들고 있으면 본문 → 패널 방향이 끊겨서, 문장을 눌렀는데 패널은 딴 항목을 펼친 채로 남는다.
  const activeIdx = items.findIndex((i) => i.quote === activeQuote)
  const openIdx = activeIdx >= 0 ? activeIdx : open
  const openRef = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (activeIdx >= 0) openRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [activeIdx])

  if (items.length === 0) return null

  // 한 번에 하나만 펼친다. 아홉 개를 다 펼쳐 두면 패널이 본문보다 길어져서 "지금 뭘
  // 보고 있는지"가 사라지고, 왼쪽 하이라이트도 어느 항목의 것인지 알 수 없게 된다.
  const toggle = (i: number, it: StudyItem) => {
    if (openIdx === i) {
      setOpen(-1)
      onQuote(null)
    } else {
      setOpen(i)
      onQuote(it.quote)
    }
  }

  return (
    <Block title="학습 로드맵" icon="★" hint="펼치면 왼쪽 본문의 해당 문장이 켜집니다">
      <ol className="space-y-1.5">
        {items.map((it, i) => {
          const isOpen = openIdx === i
          const isActive = activeQuote === it.quote
          return (
            <li key={`${it.topic}-${i}`} ref={isActive ? openRef : undefined}>
              <div
                className={
                  'rounded-md border transition ' +
                  (isActive
                    ? 'border-(--color-accent) bg-(--color-accent)/8'
                    : 'border-(--color-border) hover:border-(--color-accent)/40')
                }
              >
                <button
                  onClick={() => toggle(i, it)}
                  className="w-full text-left px-3 py-2.5 flex items-start gap-2.5"
                >
                  <span className="text-xs text-(--color-faint) tabular-nums mt-0.5 w-4 shrink-0">
                    {i + 1}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-[13px] text-(--color-text) leading-snug">
                      {it.topic}
                    </span>
                    <span className="flex flex-wrap items-center gap-1.5 mt-1">
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded border"
                        style={{
                          borderColor: PRIORITY_COLOR[it.priority],
                          color: PRIORITY_COLOR[it.priority],
                        }}
                      >
                        {PRIORITY_LABEL[it.priority]}
                      </span>
                      <span className="text-[10px] text-(--color-faint)">
                        {FROM_LABEL[it.from]}
                      </span>
                      {it.hours ? (
                        <span className="text-[10px] text-(--color-faint) tabular-nums">
                          · {it.hours}h
                        </span>
                      ) : null}
                    </span>
                  </span>
                  <span className="text-(--color-faint) text-xs mt-0.5 shrink-0">
                    {isOpen ? '−' : '+'}
                  </span>
                </button>

                {isOpen && (
                  <div className="px-3 pb-3 pt-0 space-y-2.5 border-t border-(--color-border) mt-0.5">
                    <Quote text={it.quote} from={FROM_LABEL[it.from]} />
                    <Field label="왜 필요한가">{it.why}</Field>
                    <Field label="스스로 확인">{it.gap_check}</Field>
                    <Field label="만들어 볼 것" strong>
                      {it.drill}
                    </Field>
                    {it.resources && it.resources.length > 0 && (
                      <div>
                        <FieldLabel>자료</FieldLabel>
                        <ul className="space-y-1">
                          {it.resources.map((r, k) => (
                            <li key={k}>
                              <a
                                href={r.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-(--color-sky-400) hover:underline break-words"
                              >
                                {r.title} ↗
                              </a>
                              {r.note && (
                                <span className="text-[11px] text-(--color-faint)"> — {r.note}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </Block>
  )
}

function Quote({ text, from }: { text: string; from: string }) {
  return (
    <blockquote className="border-l-2 border-(--color-accent)/50 pl-2.5 py-0.5">
      <span className="text-[10px] text-(--color-faint) block mb-0.5">{from} 원문</span>
      <span className="text-xs text-(--color-muted) leading-relaxed">{text}</span>
    </blockquote>
  )
}

// ── 한 걸음 더 ───────────────────────────────────────────────────────────
function EdgeSection({ posting }: { posting: GuidePosting }) {
  const edge = posting.edge || []
  if (edge.length === 0) return null
  return (
    <Block title="한 걸음 더" icon="↗" hint="위를 다 한 사람이 그다음에 하는 것">
      <ul className="space-y-2">
        {edge.map((e, i) => (
          <li key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
            <p className="text-[13px] text-(--color-text) leading-snug">{e.idea}</p>
            <p className="text-xs text-(--color-muted) leading-relaxed mt-1">{e.why}</p>
            {e.effort && <p className="text-[11px] text-(--color-faint) mt-1">{e.effort}</p>}
          </li>
        ))}
      </ul>
    </Block>
  )
}

// ── 전형 ────────────────────────────────────────────────────────────────
function InterviewSection({ posting }: { posting: GuidePosting }) {
  const iv = posting.interview
  if (!iv || (!iv.process && !(iv.expect || []).length)) return null
  return (
    <Block title="전형" icon="◎">
      {iv.process && <p className="text-[13px] text-(--color-text) mb-2">{iv.process}</p>}
      {iv.expect && iv.expect.length > 0 && (
        <>
          <FieldLabel>예상되는 것</FieldLabel>
          <ul className="space-y-1">
            {iv.expect.map((q, i) => (
              <li key={i} className="text-xs text-(--color-muted) leading-relaxed">
                · {q}
              </li>
            ))}
          </ul>
        </>
      )}
      <Sources sources={iv.sources} />
    </Block>
  )
}

// ── 연봉 ────────────────────────────────────────────────────────────────
const BASIS_LABEL: Record<string, string> = {
  posting: '공고 명시',
  public_data: '공개 데이터',
  market: '시장 밴드',
}

function SalarySection({ guide }: { guide: CompanyGuide }) {
  const sal = guide.salary
  const bands = sal?.bands || []
  if (!sal || bands.length === 0) return null
  const unit = sal.unit || '만원'
  return (
    <Block title="연봉" icon="₩" hint={sal.as_of ? `${sal.as_of} 기준` : undefined}>
      <ul className="space-y-2">
        {bands.map((b, i) => (
          <li key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-[13px] text-(--color-text)">{b.role}</span>
              <span className="text-[11px] text-(--color-faint)">{b.level}</span>
              <span className="ml-auto text-sm text-(--color-text) tabular-nums font-medium">
                {b.low.toLocaleString()}–{b.high.toLocaleString()}
                <span className="text-[11px] text-(--color-muted) font-normal"> {unit}</span>
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-1.5">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)">
                {BASIS_LABEL[b.basis] || b.basis}
              </span>
              {b.confidence === 'inferred' && <Badge>추정</Badge>}
              <Sources sources={b.sources} inline />
            </div>
          </li>
        ))}
      </ul>
      {sal.equity && <p className="text-xs text-(--color-muted) mt-2">{sal.equity}</p>}
      {sal.note && (
        <p className="text-[11px] text-(--color-faint) leading-relaxed mt-2">{sal.note}</p>
      )}
    </Block>
  )
}

// ── 사람 ────────────────────────────────────────────────────────────────
function PeopleSection({ guide }: { guide: CompanyGuide }) {
  const people = guide.people || []
  if (people.length === 0) return null
  return (
    <Block title="공개된 사람들" icon="◍" hint="공개 발표·글에서 읽히는 관점">
      <ul className="space-y-2.5">
        {people.map((p, i) => (
          <li key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
            <div className="flex items-baseline gap-2">
              <span className="text-[13px] text-(--color-text)">{p.name}</span>
              <span className="text-[11px] text-(--color-muted)">{p.role}</span>
              {p.confidence === 'inferred' && <Badge>추정</Badge>}
            </div>
            {p.why_public && (
              <p className="text-[11px] text-(--color-faint) mt-0.5">{p.why_public}</p>
            )}
            {p.leanings && p.leanings.length > 0 && (
              <ul className="mt-2 space-y-1">
                {p.leanings.map((t, k) => (
                  <li key={k} className="text-xs text-(--color-muted) leading-relaxed">
                    · {t}
                  </li>
                ))}
              </ul>
            )}
            {p.what_it_means && (
              <p className="text-xs text-(--color-text) leading-relaxed mt-2 pt-2 border-t border-(--color-border)">
                {p.what_it_means}
              </p>
            )}
            {p.public_work && p.public_work.length > 0 && (
              <ul className="mt-2 space-y-1">
                {p.public_work.map((w, k) => (
                  <li key={k}>
                    <a
                      href={w.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-(--color-sky-400) hover:underline break-words"
                    >
                      {w.title} ↗
                    </a>
                    {w.date && <span className="text-[10px] text-(--color-faint)"> {w.date}</span>}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </Block>
  )
}

// ── 회사·도메인 ─────────────────────────────────────────────────────────
function CompanySection({ guide }: { guide: CompanyGuide }) {
  const co = guide.company
  if (!co || (!co.business && !(co.domains || []).length && !(co.signals || []).length)) return null
  return (
    <Block title="회사와 도메인" icon="◆">
      {co.business && (
        <>
          <p className="text-[13px] text-(--color-text) leading-relaxed">{co.business}</p>
          <div className="flex items-center gap-1.5 mt-1.5">
            {co.business_confidence === 'inferred' && <Badge>추정</Badge>}
            <Sources sources={co.business_sources} inline />
          </div>
        </>
      )}

      {co.scale && co.scale.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 pt-3 border-t border-(--color-border)">
          {co.scale.map((s, i) => (
            <span key={i} className="text-xs">
              <span className="text-(--color-faint)">{s.label} </span>
              <span className="text-(--color-text) tabular-nums">{s.value}</span>
            </span>
          ))}
        </div>
      )}

      {co.domains && co.domains.length > 0 && (
        <div className="mt-3 pt-3 border-t border-(--color-border) space-y-2.5">
          <FieldLabel>이 회사가 푸는 문제</FieldLabel>
          {co.domains.map((d, i) => (
            <div key={i}>
              <p className="text-[13px] text-(--color-text)">
                {d.name}
                {d.confidence === 'inferred' && <Badge className="ml-1.5">추정</Badge>}
              </p>
              <p className="text-xs text-(--color-muted) leading-relaxed mt-0.5">{d.why}</p>
              {d.what_to_know && d.what_to_know.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {d.what_to_know.map((k, m) => (
                    <li key={m} className="text-xs text-(--color-muted) leading-relaxed">
                      · {k}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {co.signals && co.signals.length > 0 && (
        <div className="mt-3 pt-3 border-t border-(--color-border) space-y-2.5">
          <FieldLabel>공고에서 읽히는 것 (전부 추정)</FieldLabel>
          {co.signals.map((s, i) => (
            <div key={i}>
              <p className="text-[13px] text-(--color-text) leading-snug">{s.reading}</p>
              <p className="text-[11px] text-(--color-faint) leading-relaxed mt-0.5 italic">
                근거: {s.evidence}
              </p>
              {s.so_what && (
                <p className="text-xs text-(--color-muted) leading-relaxed mt-1">→ {s.so_what}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </Block>
  )
}

// ── 조각 ────────────────────────────────────────────────────────────────
function Block({
  title,
  icon,
  hint,
  children,
}: {
  title: string
  icon?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-3.5">
      <h3 className="flex items-baseline gap-1.5 mb-2.5">
        {icon && <span className="text-(--color-accent) text-xs">{icon}</span>}
        <span className="text-xs font-medium tracking-wider text-(--color-text)">{title}</span>
        {hint && <span className="text-[10px] text-(--color-faint) ml-auto">{hint}</span>}
      </h3>
      {children}
    </section>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="block text-[10px] tracking-wider text-(--color-faint) mb-0.5">{children}</span>
  )
}

function Field({
  label,
  children,
  strong = false,
}: {
  label: string
  children: React.ReactNode
  strong?: boolean
}) {
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      <p
        className={
          'text-xs leading-relaxed ' + (strong ? 'text-(--color-text)' : 'text-(--color-muted)')
        }
      >
        {children}
      </p>
    </div>
  )
}

function Badge({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={
        'inline-block text-[10px] px-1.5 py-0.5 rounded border border-(--color-amber-400)/40 text-(--color-amber-400) ' +
        className
      }
    >
      {children}
    </span>
  )
}

function Sources({ sources, inline = false }: { sources?: Source[]; inline?: boolean }) {
  if (!sources || sources.length === 0) return null
  return (
    <span className={inline ? 'inline-flex flex-wrap gap-1.5' : 'flex flex-wrap gap-1.5 mt-2'}>
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          title={s.title}
          className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-faint) hover:text-(--color-sky-400) hover:border-(--color-sky-400)"
        >
          {s.publisher || s.title.slice(0, 18)} ↗
        </a>
      ))}
    </span>
  )
}
