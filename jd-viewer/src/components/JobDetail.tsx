import { useEffect, useMemo, useRef, useState } from 'react'
import type { Job } from '../types'
import { classifyRoles, roleColor } from '../lib/classify'
import { useSimilarJobs } from '../lib/useSimilar'
import { useJobGuide, PRIORITY_COLOR, type StudyFrom, type StudyItem } from '../lib/useGuide'
import { goBack } from '../lib/router'
import { paths } from '../lib/urls'
import { TechTag, CompanyMark } from './ui'
import { JobGuide } from './JobGuide'

interface Props {
  job: Job
  /** 비슷한 공고를 눌렀을 때 그 공고로 갈아끼운다. 없으면 추천 섹션을 감춘다. */
  onOpenUrl?: (url: string) => void
}

// 닫기는 곧 뒤로가기다 — 상세가 주소를 가지므로, 목록으로 돌아가는 일은 히스토리를
// 한 칸 되감는 것과 같다. 외부에서 상세로 바로 들어온 사람은 되감을 칸이 없으므로
// 목록 주소로 보낸다.
const onClose = () => goBack(paths.jobs())

/**
 * 공고 상세 — 팝업이 아니라 화면 하나.
 *
 * 원래는 모달이었는데, 오른쪽에 학습 로드맵을 붙이는 순간 4xl 폭 안에서 JD 와 가이드가
 * 서로를 밀어냈다. 둘 다 "끝까지 읽는" 글이라 좁은 칸에 겹쳐 두면 어느 쪽도 안 읽힌다.
 * 그래서 목록을 통째로 갈아끼우는 전체 화면으로 바꾸고 폭을 둘로 나눴다.
 */
export function JobDetail({ job, onOpenUrl }: Props) {
  const [activeQuote, setActiveQuote] = useState<string | null>(null)
  const [pane, setPane] = useState<'jd' | 'guide'>('jd')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // 추천을 눌러 다른 공고로 갈아끼면 스크롤·하이라이트·펼친 항목이 앞 공고의 것으로
  // 남는다. App 이 key={job.url} 로 이 컴포넌트를 통째로 다시 마운트해서 그걸 막는다 —
  // 상태 하나하나를 useEffect 로 되돌리는 것보다 지워야 할 것을 빠뜨릴 일이 없다.
  const roles = classifyRoles(job.title, job.tech_stack, job.qualifications || '')
  const { lookup } = useSimilarJobs()
  const similar = onOpenUrl ? lookup(job.url) : []

  // 본문 하이라이트는 가이드의 study[] 에서 나온다. 패널과 본문이 같은 데이터를 보되
  // 훅은 각자 부르는데, useJobGuide 는 fetch 를 캐시하므로 요청은 한 번이다.
  const { posting } = useJobGuide(job.company, job.url)
  const marksBySection = useMemo(() => {
    const by: Record<StudyFrom, StudyItem[]> = { qualification: [], preference: [], task: [] }
    for (const s of posting?.study || []) if (by[s.from]) by[s.from].push(s)
    return by
  }, [posting])

  // 좁은 화면에서는 두 단이 안 들어간다. 가이드를 본문 아래로 흘리면 스크롤 두 화면
  // 아래로 밀려나 아무도 안 보므로, 탭으로 갈아끼운다.
  const jumpToGuide = (q: string | null) => {
    setActiveQuote(q)
    if (q && window.innerWidth < 1024) setPane('guide')
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 헤더 */}
      <div className="border-b border-(--color-border) bg-(--color-panel) px-4 sm:px-6 py-3 shrink-0">
        <div className="flex items-start gap-3">
          <a
            href={paths.jobs()}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
              e.preventDefault()
              onClose()
            }}
            className="shrink-0 mt-0.5 px-2.5 py-1.5 rounded border border-(--color-border) text-xs text-(--color-muted) hover:text-(--color-text) hover:bg-(--hover)"
            title="목록으로 (ESC)"
          >
            ← 목록
          </a>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="text-xs px-2 py-0.5 rounded bg-(--color-bg) text-(--color-muted) border border-(--color-border)">
                {job.site}
              </span>
              {job.status === 'closed' && (
                <span className="text-xs px-2 py-0.5 rounded border border-(--color-red-400)/40 text-(--color-red-400)">
                  마감
                </span>
              )}
              {roles.map((r) => (
                <span
                  key={r}
                  className="text-xs px-2 py-0.5 rounded border"
                  style={{ borderColor: roleColor(r), color: roleColor(r) }}
                >
                  {r}
                </span>
              ))}
              {job.career && <span className="text-xs text-(--color-muted)">· {job.career}</span>}
              {job.location && <span className="text-xs text-(--color-muted)">· {job.location}</span>}
            </div>
            <h2 className="text-(--color-text) text-lg sm:text-xl leading-snug">{job.title}</h2>
            <p className="text-(--color-muted) text-sm mt-0.5 flex items-center gap-1.5">
              <CompanyMark name={job.company} size={16} />
              {job.company}
            </p>
          </div>
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex shrink-0 items-center gap-1.5 px-3 py-1.5 rounded bg-(--color-accent) text-(--color-on-accent) text-sm font-medium hover:opacity-90"
            >
              원본 공고 ↗
            </a>
          )}
        </div>

        {/* 좁은 화면 전용 단 전환 */}
        <div className="lg:hidden mt-3 inline-flex rounded-md border border-(--color-border) overflow-hidden">
          <PaneBtn active={pane === 'jd'} onClick={() => setPane('jd')}>
            공고
          </PaneBtn>
          <PaneBtn active={pane === 'guide'} onClick={() => setPane('guide')}>
            취업 가이드
          </PaneBtn>
        </div>
      </div>

      {/* 두 단 */}
      <div className="flex flex-1 min-h-0">
        <div
          data-scroll
          className={
            'flex-1 min-w-0 overflow-auto px-4 sm:px-6 py-5 space-y-5 text-sm ' +
            (pane === 'jd' ? '' : 'hidden lg:block')
          }
        >
          {job.tech_stack && job.tech_stack.length > 0 && (
            <Section title="기술 스택">
              <div className="flex flex-wrap gap-1.5">
                {job.tech_stack.map((t) => (
                  <TechTag
                    key={t}
                    tech={t}
                    size={14}
                    className="text-xs px-2 py-1 rounded bg-(--color-accent)/15 text-(--color-accent) border border-(--color-accent)/30"
                  />
                ))}
              </div>
            </Section>
          )}

          <Section title="주요 업무" marks={marksBySection.task.length}>
            <FieldOrPlaceholder
              text={job.main_tasks}
              url={job.url}
              marks={marksBySection.task}
              activeQuote={activeQuote}
              onQuote={jumpToGuide}
            />
          </Section>

          <Section title="자격 요건" marks={marksBySection.qualification.length}>
            <FieldOrPlaceholder
              text={job.qualifications}
              url={job.url}
              marks={marksBySection.qualification}
              activeQuote={activeQuote}
              onQuote={jumpToGuide}
            />
          </Section>

          <Section title="우대 사항" marks={marksBySection.preference.length}>
            <FieldOrPlaceholder
              text={job.preferences}
              url={job.url}
              marks={marksBySection.preference}
              activeQuote={activeQuote}
              onQuote={jumpToGuide}
            />
          </Section>

          {job.benefits && (
            <Section title="복지 / 혜택">
              <Pre text={job.benefits} />
            </Section>
          )}

          {job.full_jd && (
            <details className="border-t border-(--color-border) pt-4">
              <summary className="cursor-pointer text-(--color-muted) hover:text-(--color-text) text-xs tracking-wider">
                전체 JD 원문 보기
              </summary>
              <Pre text={job.full_jd} muted />
            </details>
          )}

          {similar.length > 0 && onOpenUrl && (
            <section className="border-t border-(--color-border) pt-4">
              <h3 className="text-xs tracking-wider text-(--color-muted) mb-2.5 font-medium">
                비슷한 공고
              </h3>
              <ul className="space-y-1.5">
                {similar.map((s) => (
                  <li key={s.url}>
                    <button
                      onClick={() => onOpenUrl(s.url)}
                      className="w-full text-left px-3 py-2.5 rounded border border-(--color-border) hover:bg-(--hover) hover:border-(--color-accent)/40 flex items-center gap-3"
                    >
                      <span className="flex-1 min-w-0">
                        <span className="block text-(--color-text) text-[13px] leading-snug truncate">
                          {s.title || s.url}
                        </span>
                        {s.company && (
                          <span className="block text-(--color-muted) text-xs mt-0.5 truncate">
                            {s.company}
                          </span>
                        )}
                      </span>
                      <span
                        className="text-xs text-(--color-muted) shrink-0 tabular-nums"
                        title={`코사인 유사도 ${s.score.toFixed(3)}`}
                      >
                        {Math.round(s.score * 100)}%
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="border-t border-(--color-border) pt-4 flex flex-wrap items-center gap-3">
            {job.url ? (
              <>
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-(--color-accent) text-(--color-on-accent) font-medium hover:opacity-90"
                >
                  원본 공고 열기 ↗
                </a>
                <span className="text-xs text-(--color-muted) truncate flex-1 min-w-0" title={job.url}>
                  {job.url}
                </span>
              </>
            ) : (
              <span className="text-xs text-(--color-muted)">원본 URL 없음</span>
            )}
          </div>
        </div>

        <aside
          data-scroll
          className={
            'overflow-auto bg-(--color-bg)/40 px-4 sm:px-5 py-5 ' +
            'lg:w-[420px] xl:w-[460px] lg:shrink-0 lg:border-l lg:border-(--color-border) ' +
            (pane === 'guide' ? 'flex-1 min-w-0' : 'hidden lg:block')
          }
        >
          <JobGuide
            company={job.company}
            url={job.url}
            activeQuote={activeQuote}
            onQuote={setActiveQuote}
          />
        </aside>
      </div>
    </div>
  )
}

function PaneBtn({
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
      className={`px-3 py-1 text-xs font-medium transition whitespace-nowrap ${
        active
          ? 'bg-(--color-accent) text-(--color-on-accent)'
          : 'bg-(--color-panel) text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {children}
    </button>
  )
}

function Section({
  title,
  marks = 0,
  children,
}: {
  title: string
  marks?: number
  children: React.ReactNode
}) {
  return (
    <section>
      <h3 className="flex items-center gap-2 text-xs tracking-wider text-(--color-muted) mb-2 font-medium">
        {title}
        {marks > 0 && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded border font-normal"
            style={{ borderColor: PRIORITY_COLOR.core, color: PRIORITY_COLOR.core }}
            title="이 절에서 뽑은 학습 항목"
          >
            학습 {marks}
          </span>
        )}
      </h3>
      {children}
    </section>
  )
}

function FieldOrPlaceholder({
  text,
  url,
  marks,
  activeQuote,
  onQuote,
}: {
  text: string | undefined
  url: string
  marks?: StudyItem[]
  activeQuote?: string | null
  onQuote?: (q: string | null) => void
}) {
  const trimmed = (text || '').trim()
  if (trimmed.length < 10) {
    return (
      <div className="text-(--color-muted) text-xs italic border border-dashed border-(--color-border) rounded px-3 py-2.5">
        이 공고는 해당 정보가 비어있습니다.{' '}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-(--color-accent) hover:underline not-italic"
          >
            원본 공고에서 확인 ↗
          </a>
        )}
      </div>
    )
  }
  return <Pre text={trimmed} marks={marks} activeQuote={activeQuote} onQuote={onQuote} />
}

function Pre({
  text,
  muted = false,
  marks,
  activeQuote,
  onQuote,
}: {
  text: string
  muted?: boolean
  marks?: StudyItem[]
  activeQuote?: string | null
  onQuote?: (q: string | null) => void
}) {
  return (
    <pre
      className={
        'whitespace-pre-wrap font-sans text-[13px] leading-relaxed ' +
        (muted ? 'text-(--color-muted)' : 'text-(--color-text)')
      }
    >
      {marks && marks.length > 0 ? (
        <Highlighted text={text} marks={marks} activeQuote={activeQuote} onQuote={onQuote} />
      ) : (
        text
      )}
    </pre>
  )
}

// ── 하이라이트 ──────────────────────────────────────────────────────────
// 가이드가 뽑은 문장을 본문에서 되찾아 밑줄을 친다. quote 는 원문 그대로 쓰기로 돼
// 있지만(guide-engine/validate.py 가 검사한다), 크롤 시점에 따라 공백·줄바꿈이 달라질
// 수 있어서 공백은 느슨하게 맞춘다. 못 찾으면 조용히 원문 그대로 그린다 — 하이라이트가
// 없다고 공고 본문이 안 보이면 안 된다.
function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

interface Hit {
  start: number
  end: number
  item: StudyItem
}

function findHits(text: string, marks: StudyItem[]): Hit[] {
  const hits: Hit[] = []
  for (const item of marks) {
    const q = item.quote?.trim()
    if (!q) continue
    let start = text.indexOf(q)
    let end = start + q.length
    if (start < 0) {
      const re = new RegExp(escapeRe(q).replace(/\s+/g, '\\s+'))
      const m = re.exec(text)
      if (!m) continue
      start = m.index
      end = m.index + m[0].length
    }
    hits.push({ start, end, item })
  }
  // 겹치는 구간은 먼저 걸린 것만 남긴다. 두 항목이 같은 문장을 인용하면 자를 수 없다.
  hits.sort((a, b) => a.start - b.start)
  const out: Hit[] = []
  let cursor = -1
  for (const h of hits) {
    if (h.start >= cursor) {
      out.push(h)
      cursor = h.end
    }
  }
  return out
}

function Highlighted({
  text,
  marks,
  activeQuote,
  onQuote,
}: {
  text: string
  marks: StudyItem[]
  activeQuote?: string | null
  onQuote?: (q: string | null) => void
}) {
  const hits = useMemo(() => findHits(text, marks), [text, marks])
  const activeRef = useRef<HTMLElement>(null)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [activeQuote])

  if (hits.length === 0) return <>{text}</>

  const nodes: React.ReactNode[] = []
  let at = 0
  hits.forEach((h, i) => {
    if (h.start > at) nodes.push(text.slice(at, h.start))
    const color = PRIORITY_COLOR[h.item.priority]
    const active = activeQuote === h.item.quote
    nodes.push(
      <mark
        key={`h${i}`}
        ref={active ? activeRef : undefined}
        onClick={() => onQuote?.(active ? null : h.item.quote)}
        title={`${h.item.topic} — 눌러서 가이드로`}
        className="cursor-pointer rounded-sm px-0.5 -mx-0.5 transition"
        style={{
          background: active ? `color-mix(in srgb, ${color} 22%, transparent)` : 'transparent',
          boxShadow: `inset 0 -2px 0 ${active ? color : `color-mix(in srgb, ${color} 45%, transparent)`}`,
          color: 'inherit',
        }}
      >
        {text.slice(h.start, h.end)}
      </mark>,
    )
    at = h.end
  })
  if (at < text.length) nodes.push(text.slice(at))
  return <>{nodes}</>
}
