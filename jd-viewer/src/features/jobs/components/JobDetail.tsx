import { useEffect, useMemo, useRef, useState } from 'react'
import type { Job } from '../../../types'
import { classifyRoles } from '../../../utils/classify'
import { daysUntil, postedOf } from '../utils/recruit'
import { blendByEngagement, useEngagement } from '../../../hooks/useEngagement'
import { useSimilarJobs } from '../../../hooks/useSimilar'
import { track, useDwell } from '../../../utils/track'
import {
  useJobGuide,
  PRIORITY_COLOR,
  type HighlightMark,
  type StudyFrom,
} from '../hooks/useGuide'
import { goBack, onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { CompanyMark } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'
import { plainCompany } from '../../../utils/companyName'
import { useCompanies, type CompanyListItem } from '../../../hooks/useCompanies'
import { fetchHome, type HomeCompany } from '../../home/api'
import { careerOf, ddayLabel } from '../../home/utils'
import { JobGuide } from './JobGuide'
import { parseJdText, type JdBlock } from '../utils/jdText'
import { useRoleReading } from '../hooks/useRoleReading'
import { matchRoleLine } from '../utils/roleText'
import { RoleAside, RoleLineNote, RoleStudyPath, RoleSummary } from './RoleReading'

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
  const { items: similarItems } = useSimilarJobs(onOpenUrl ? job.url : null)
  const eng = useEngagement()
  // 유사도가 바닥을 잡고, 사람들이 실제로 그다음에 본 것이 순위를 조금 올린다.
  // 같은 공고가 다른 사이트에 올라온 사본(회사·제목이 같다)은 '비슷한' 공고가 아니라 같은 공고다 — 뺀다.
  const similar = onOpenUrl
    ? blendByEngagement(similarItems, eng, job.url).filter((s) => !(s.title === job.title && plainCompany(s.company) === plainCompany(job.company)))
    : []

  // 무엇을 열었고 얼마나 머물렀나. 이 둘이 추천을 고칠 유일한 근거다.
  useDwell(job.url)
  useEffect(() => {
    track('view', job.url)
  }, [job.url])

  // 본문 하이라이트는 가이드의 study[] 에서 나온다. 패널과 본문이 같은 데이터를 보되
  // 훅은 각자 부르는데, useJobGuide 는 fetch 를 캐시하므로 요청은 한 번이다.
  const { posting } = useJobGuide(job.company, job.url)
  const marksBySection = useMemo(() => {
    const by: Record<StudyFrom, HighlightMark[]> = { qualification: [], preference: [], task: [] }
    for (const s of posting?.study || []) if (by[s.from]) by[s.from].push(s)
    return by
  }, [posting])

  // 직무 역설계(공고 한 줄씩 읽기) — 풀이가 있는 공고만. 공고 줄 밑에 한 줄 답이 늘 보이고, 누르면 풀이가 펼쳐진다.
  const reading = useRoleReading(`${job.site}-${job.pid}`)
  const [openLines, setOpenLines] = useState<Set<string>>(() => new Set())
  const allOpen = !!reading && openLines.size >= reading.lines.length
  const toggleLine = (q: string) =>
    setOpenLines((prev) => {
      const next = new Set(prev)
      if (next.has(q)) next.delete(q)
      else next.add(q)
      return next
    })
  const toggleAll = () => setOpenLines(allOpen || !reading ? new Set() : new Set(reading.lines.map((l) => l.quote)))
  const noteFor = reading
    ? (text: string) => {
        const line = matchRoleLine(reading.lines, text)
        return line ? <RoleLineNote line={line} sources={reading.sources} resources={reading.resources} open={openLines.has(line.quote)} onToggle={() => toggleLine(line.quote)} /> : null
      }
    : undefined

  // 좁은 화면에서는 두 단이 안 들어간다. 가이드를 본문 아래로 흘리면 스크롤 두 화면
  // 아래로 밀려나 아무도 안 보므로, 탭으로 갈아끼운다.
  const jumpToGuide = (q: string | null) => {
    setActiveQuote(q)
    if (q && window.innerWidth < 1024) setPane('guide')
  }

  // 캐치형(Penpot 13 공고 상세) — 흰 바탕 가운데에 공고 카드 한 장(머리·핵심 띠·태그·본문 절·원문·기업 정보)과
  // 오른쪽 칸(비슷한 공고·이 회사의 다른 공고·취업 브리핑)을 나란히 둔다.
  const left = daysUntil(job.deadline_date)
  const ddayText = job.status === 'closed' ? '마감' : left != null && left >= 0 ? (left === 0 ? '오늘 마감' : `D-${left}`) : '상시'
  const posted = postedOf(job)
  const facts: [string, string, 'career' | 'type' | 'place' | 'deadline'][] = [
    ['경력', job.career || '무관', 'career'],
    ['고용형태', employmentOf(job), 'type'],
    ['근무지', job.location || '원문 확인', 'place'],
    ['마감', job.deadline_date ? `~${mdDay(job.deadline_date)} · ${ddayText}` : ddayText, 'deadline'],
  ]
  const co = useCompanyOf(job.company)
  const others = useOtherJobs(job)
  const tags = [
    ...roles.map((r) => ({ t: r, hot: true })),
    ...(/신입|무관/.test(job.career || '') ? [{ t: '신입 가능', hot: false }] : []),
    ...(job.company_size ? [{ t: job.company_size, hot: false }] : []),
    ...(co?.c.domains[0] ? [{ t: co.c.domains[0].name, hot: false }] : []),
  ]

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[45px] pb-[90px] lg:flex lg:items-start lg:gap-6">
        {/* 좁은 화면 전용 단 전환 */}
        <div className="lg:hidden mb-3 inline-flex rounded-md border border-(--color-border) overflow-hidden bg-(--color-panel)">
          <PaneBtn active={pane === 'jd'} onClick={() => setPane('jd')}>
            공고
          </PaneBtn>
          <PaneBtn active={pane === 'guide'} onClick={() => setPane('guide')}>
            취업 가이드
          </PaneBtn>
        </div>
        <article className={'w-full lg:flex-1 min-w-0 rounded-[30px] border border-[#e2e8ec] bg-white ' + (pane === 'jd' ? '' : 'hidden lg:block')}>
          {/* 머리 */}
          <div className="px-6 sm:px-10 pt-9 pb-[30px] border-b border-[#e2e8ec]">
            <div className="flex flex-wrap items-center gap-x-[10px] gap-y-2">
              <span className="grid place-items-center w-12 h-12 rounded-xl overflow-hidden shrink-0">
                <CompanyMark name={job.company} size={48} />
              </span>
              <span className="text-[17px] font-medium text-[#272727]">{job.company}</span>
              {co && (
                <a
                  href={paths.company(co.slug)}
                  onClick={onLinkClick(paths.company(co.slug))}
                  className="h-6 px-2 rounded-xl border border-[#d8d8d8] text-xs leading-[22px] text-[#474747] hover:border-[#272727]"
                >
                  기업정보
                </a>
              )}
              <span className="ml-auto text-[13px] text-[#999] tabular-nums">
                출처 {job.site}
                {posted && <span className="ml-5">{posted.estimated ? '수집' : '등록'} {posted.iso.slice(0, 10)}</span>}
              </span>
            </div>
            <h1 className="mt-4 text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">{job.title}</h1>
            <div className="mt-[22px] flex flex-wrap items-center gap-4">
              <StarToggle id={`${job.site}-${job.pid}`} />
              <ShareButton />
              <span className="text-base font-medium text-[#272727] tabular-nums">{ddayText}</span>
              {job.url && (
                <a
                  href={job.url}
                  onClick={() => track('click', 'outbound', job.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-auto inline-flex items-center gap-2 h-[46px] px-6 rounded-md bg-(--color-accent) text-base font-bold text-white hover:bg-(--color-accent-deep)"
                >
                  원본 공고 바로가기
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="1.4" aria-hidden>
                    <path d="M5 2H2v8h8V7M7 1.5h3.5V5M10.5 1.5 5.5 6.5" />
                  </svg>
                </a>
              )}
            </div>
          </div>

          <div className="px-6 sm:px-10 pt-[29px] pb-10">
            {/* 핵심 띠 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-y-4 rounded-2xl bg-[#f7f9fa] px-6 py-5">
              {facts.map(([k, v, icon]) => (
                <div key={k} className="min-w-0 pr-3">
                  <div className="flex items-center gap-1.5 text-[13px] text-[#777]">
                    <FactIcon kind={icon} />
                    {k}
                  </div>
                  <div className="mt-1.5 text-base font-medium text-[#272727] truncate" title={v}>
                    {v}
                  </div>
                </div>
              ))}
            </div>
            {tags.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {tags.map(({ t, hot }) => (
                  <span key={t} className={'rounded px-[7px] text-[13px] leading-[22px] ' + (hot ? 'bg-(--color-accent-weak) text-(--color-accent)' : 'bg-[#f4f4f4] text-[#474747]')}>
                    {t}
                  </span>
                ))}
              </div>
            )}

            <div className="mt-[49px] space-y-[49px] text-base text-[#272727]">
              {reading && <RoleSummary r={reading} allOpen={allOpen} onToggleAll={toggleAll} />}
              {job.tech_stack && job.tech_stack.length > 0 && (
                <Section title="기술 스택">
                  <div className="flex flex-wrap gap-2">
                    {job.tech_stack.map((t) => (
                      <span key={t} className="h-9 px-[17px] rounded-[18px] border border-[#d8d8d8] text-sm font-medium leading-[34px] text-[#272727]">
                        {t}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              <Section title="주요 업무" marks={marksBySection.task.length}>
                <FieldOrPlaceholder text={job.main_tasks} url={job.url} noteFor={noteFor} marks={marksBySection.task} activeQuote={activeQuote} onQuote={jumpToGuide} />
              </Section>

              <Section title="자격 요건" marks={marksBySection.qualification.length}>
                <FieldOrPlaceholder text={job.qualifications} url={job.url} noteFor={noteFor} marks={marksBySection.qualification} activeQuote={activeQuote} onQuote={jumpToGuide} />
              </Section>

              <Section title="우대 사항" marks={marksBySection.preference.length}>
                <FieldOrPlaceholder text={job.preferences} url={job.url} noteFor={noteFor} marks={marksBySection.preference} activeQuote={activeQuote} onQuote={jumpToGuide} />
              </Section>

              {reading && <RoleStudyPath r={reading} />}

              {job.benefits && (
                <Section title="복지 / 혜택">
                  <JdBody text={job.benefits} />
                </Section>
              )}

              {job.full_jd && <FullJd text={job.full_jd} />}

              {co && <CompanyInfo co={co} location={job.location} />}
            </div>
          </div>
        </article>

        {/* 오른쪽 칸 — 비슷한 공고 · 이 회사의 다른 공고 · 취업 브리핑 */}
        <aside className={'w-full lg:w-[352px] lg:shrink-0 mt-6 lg:mt-0 flex flex-col gap-[30px] ' + (pane === 'guide' ? 'block' : 'hidden lg:flex')}>
          {reading && <RoleAside r={reading} />}
          {similar.length > 0 && onOpenUrl && (
            <SideList title="비슷한 공고">
              {similar.slice(0, 5).map((s) => (
                <SideCard
                  key={s.url}
                  company={s.company}
                  title={s.title || s.url}
                  chip={`유사도 ${Math.round(s.score * 100)}%`}
                  hot
                  onClick={() => {
                    // 어느 공고에서 어느 공고로 넘어갔는지. score.py 의 'next' 가 이 한 줄에서 만들어진다.
                    track('click', s.url, job.url)
                    onOpenUrl(s.url)
                  }}
                />
              ))}
            </SideList>
          )}
          {others.length > 0 && (
            <SideList title="이 회사의 다른 공고">
              {others.slice(0, 4).map((o) => (
                <SideCard key={o.site + o.pid} company={job.company} title={o.title} dday={ddayLabel(o.dday)} chip={careerOf(null, o.career_bucket)} href={paths.job({ site: o.site as never, pid: o.pid })} />
              ))}
            </SideList>
          )}
          <div className="rounded-[22px] bg-[#f3f6f8] px-6 py-6 empty:hidden">
            <JobGuide company={job.company} url={job.url} activeQuote={activeQuote} onQuote={setActiveQuote} />
          </div>
        </aside>
      </div>
      <SiteFooter />
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
      <h3 className="flex items-center gap-2 text-xl font-bold leading-[29px] text-[#272727] pb-3 mb-4 border-b-2 border-[#272727]">
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
  noteFor,
}: {
  text: string | undefined
  url: string
  marks?: HighlightMark[]
  activeQuote?: string | null
  onQuote?: (q: string | null) => void
  noteFor?: (text: string) => React.ReactNode
}) {
  const trimmed = (text || '').trim()
  if (trimmed.length < 10) {
    return (
      <div className="rounded-2xl bg-[#f7f9fa] px-6 py-5 text-sm text-[#666]">
        이 공고는 해당 정보가 비어 있어요.{' '}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-(--color-accent) hover:underline"
          >
            원본 공고에서 확인하기 ↗
          </a>
        )}
      </div>
    )
  }
  return <JdBody text={trimmed} marks={marks} activeQuote={activeQuote} onQuote={onQuote} noteFor={noteFor} />
}

// ── 본문 ────────────────────────────────────────────────────────────────
// 원문 줄바꿈을 <pre> 로 그대로 그리면 사이트마다 다른 글머리표·소제목·구분선이 한
// 무게로 섞여 글자벽이 된다. parseJdText 가 가른 덩어리를 번호 붙은 줄(구분선으로
// 나뉜) · 소제목 · 하위 항목 · ※ 안내로 각자 그린다. 번호는 소제목마다 01 부터.
type Row = { no: number; text: string; subs: string[] }
type Group =
  | { kind: 'list'; rows: Row[] }
  | { kind: 'heading' | 'note' | 'para'; text: string }

function groupBlocks(blocks: JdBlock[]): Group[] {
  const out: Group[] = []
  let no = 0
  for (const b of blocks) {
    if (b.kind !== 'item') {
      if (b.kind === 'heading') no = 0
      out.push({ kind: b.kind, text: b.text })
      continue
    }
    const last = out[out.length - 1]
    if (b.depth === 1 && last?.kind === 'list') {
      last.rows[last.rows.length - 1].subs.push(b.text)
    } else if (last?.kind === 'list') {
      last.rows.push({ no: ++no, text: b.text, subs: [] })
    } else {
      out.push({ kind: 'list', rows: [{ no: ++no, text: b.text, subs: [] }] })
    }
  }
  return out
}

function JdBody({
  text,
  marks,
  activeQuote,
  onQuote,
  noteFor,
}: {
  text: string
  marks?: HighlightMark[]
  activeQuote?: string | null
  onQuote?: (q: string | null) => void
  noteFor?: (text: string) => React.ReactNode
}) {
  const groups = useMemo(() => groupBlocks(parseJdText(text)), [text])
  // 하이라이트는 덩어리마다 다시 찾는다. 인용이 줄을 넘나들면 못 찾는데, 그때는
  // 밑줄만 빠지고 글은 그대로 보인다.
  const t = (s: string) =>
    marks && marks.length > 0 ? (
      <Highlighted text={s} marks={marks} activeQuote={activeQuote} onQuote={onQuote} />
    ) : (
      s
    )
  return (
    <div className="text-base leading-[26px] text-[#272727]">
      {groups.map((g, gi) => {
        if (g.kind === 'heading') {
          return (
            <h4
              key={gi}
              className="mt-6 first:mt-0 mb-2 flex items-center gap-2 text-[13px] font-semibold text-(--color-text)"
            >
              <span className="w-1 h-3.5 rounded-sm bg-(--color-accent)" aria-hidden />
              {g.text}
            </h4>
          )
        }
        if (g.kind === 'note') {
          return (
            <p key={gi} className="mt-2 text-xs text-(--color-muted)">
              ※ {t(g.text)}
            </p>
          )
        }
        if (g.kind !== 'list') {
          return (
            <p key={gi} className="my-2 first:mt-0">
              {t(g.text)}
            </p>
          )
        }
        return (
          <ol key={gi}>
            {g.rows.map((r, ri) => (
              <li
                key={ri}
                className="grid grid-cols-[2.25rem_1fr] gap-x-2 py-[14px] border-b border-[#eef1f3]"
              >
                <span className="pt-px text-[15px] font-bold tabular-nums text-(--color-accent)">
                  {String(r.no).padStart(2, '0')}
                </span>
                <div className="min-w-0">
                  <div>{t(r.text)}</div>
                  {noteFor?.(r.text)}
                  {r.subs.length > 0 && (
                    <ul className="mt-1.5 space-y-1 text-[13px] text-(--color-muted)">
                      {r.subs.map((sub, si) => (
                        <li key={si} className="flex gap-1.5">
                          <span aria-hidden>–</span>
                          <span className="min-w-0">{t(sub)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )
      })}
    </div>
  )
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
  marks?: HighlightMark[]
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
  item: HighlightMark
}

function findHits(text: string, marks: HighlightMark[]): Hit[] {
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
  marks: HighlightMark[]
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

const WEEK = ['일', '월', '화', '수', '목', '금', '토']
/** '2026-11-15' → '11.15(일)' */
function mdDay(iso: string): string {
  const d = new Date(iso + 'T00:00:00')
  return Number.isNaN(d.getTime()) ? iso : `${d.getMonth() + 1}.${String(d.getDate()).padStart(2, '0')}(${WEEK[d.getDay()]})`
}

/** 고용형태 — 원문에 적힌 것만 말한다. 아무 표기가 없으면 짐작하지 않고 원문을 보라고 한다. */
function employmentOf(job: Job): string {
  const t = `${job.title} ${job.full_jd || ''}`
  if (/인턴/.test(t)) return '인턴'
  if (/계약직|기간제|프리랜서/.test(t)) return '계약직'
  if (/정규직/.test(t)) return '정규직'
  return '원문 확인'
}

/** 이 공고 회사의 기술스택 프로필(company_stacks) — 이름에서 법인 표기를 떼고 맞춘다. */
function useCompanyOf(name: string) {
  const { companies, slugOf } = useCompanies()
  return useMemo(() => {
    const key = plainCompany(name)
    const c = companies.find((x) => x.name === name || plainCompany(x.name) === key)
    return c ? { c, slug: slugOf(c.norm) } : null
    // slugOf 는 목록이 그대로면 결과도 그대로다(렌더마다 새 함수일 뿐).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companies, name])
}

/** 같은 회사의 다른 공고 — 메인 화면의 회사 묶음(/api/home, 없으면 스냅숏)에서 찾는다. */
function useOtherJobs(job: Job): HomeCompany['titles'] {
  const [list, setList] = useState<HomeCompany['titles']>([])
  useEffect(() => {
    const ctl = new AbortController()
    const key = plainCompany(job.company)
    fetchHome({ size: '', industry: '', sort: 'popular', limit: 300 }, { signal: ctl.signal })
      .then((d) => {
        const c = d.companies.find((x) => x.name === job.company || plainCompany(x.name) === key)
        setList((c?.titles ?? []).filter((t) => !(t.site === job.site && t.pid === job.pid)))
      })
      .catch(() => {})
    return () => ctl.abort()
  }, [job.company, job.site, job.pid])
  return list
}

function FactIcon({ kind }: { kind: 'career' | 'type' | 'place' | 'deadline' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#777" strokeWidth="1.3" aria-hidden className="shrink-0">
      {kind === 'career' && (
        <>
          <circle cx="7" cy="7" r="5.5" />
          <path d="M7 4v3.2l2 1.2" strokeLinecap="round" />
        </>
      )}
      {kind === 'type' && (
        <>
          <rect x="1.5" y="4" width="11" height="8" rx="1.5" />
          <path d="M5 4V2.5h4V4" />
        </>
      )}
      {kind === 'place' && (
        <>
          <path d="M7 12.5s4-3.6 4-6.6a4 4 0 0 0-8 0c0 3 4 6.6 4 6.6Z" />
          <circle cx="7" cy="5.8" r="1.5" />
        </>
      )}
      {kind === 'deadline' && (
        <>
          <circle cx="7" cy="7" r="5.5" />
          <path d="M7 3.8V7h2.6" strokeLinecap="round" />
        </>
      )}
    </svg>
  )
}

const STAR_KEY = 'jd-stars'

/** 관심 공고 별 — 잡 리스트의 별과 같은 저장소(이 브라우저에만 남는다). */
function StarToggle({ id }: { id: string }) {
  const read = (): string[] => {
    try {
      return JSON.parse(localStorage.getItem(STAR_KEY) || '[]') as string[]
    } catch {
      return []
    }
  }
  const [on, setOn] = useState(() => read().includes(id))
  const flip = () => {
    const cur = new Set(read())
    if (cur.has(id)) cur.delete(id)
    else cur.add(id)
    try {
      localStorage.setItem(STAR_KEY, JSON.stringify([...cur]))
    } catch {
      /* 저장소가 막힌 브라우저 — 이번 화면에서만 바뀐다 */
    }
    setOn(cur.has(id))
  }
  return (
    <button type="button" onClick={flip} aria-pressed={on} aria-label={on ? '관심 공고에서 빼기' : '관심 공고로 담기'}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill={on ? '#f45757' : 'none'} stroke={on ? '#f45757' : '#999'} strokeWidth="1.5" strokeLinejoin="round" aria-hidden>
        <path d="M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8Z" />
      </svg>
    </button>
  )
}

/** 이 공고 주소를 복사한다(공유). */
function ShareButton() {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      aria-label="주소 복사"
      title={done ? '주소를 복사했어요' : '주소 복사'}
      onClick={() =>
        navigator.clipboard?.writeText(window.location.href).then(
          () => {
            setDone(true)
            setTimeout(() => setDone(false), 1500)
          },
          () => {},
        )
      }
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke={done ? '#f45757' : '#999'} strokeWidth="1.5" aria-hidden>
        <circle cx="15" cy="4.5" r="2.2" />
        <circle cx="5" cy="10" r="2.2" />
        <circle cx="15" cy="15.5" r="2.2" />
        <path d="M7 9 13 5.6M7 11l6 3.4" />
      </svg>
    </button>
  )
}

/** 전체 JD 원문 — 검은 단추로 편다. */
function FullJd({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full inline-flex items-center justify-center gap-2 h-11 rounded-[30px] bg-[#272727] text-base font-medium text-white hover:bg-black"
      >
        {open ? '원문 접기' : '공고 원문 전체 보기'}
        <svg width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
          <path d={open ? 'M1.5 5.5 5 2l3.5 3.5' : 'M1.5 2.5 5 6l3.5-3.5'} />
        </svg>
      </button>
      {open && <Pre text={text} muted />}
    </div>
  )
}

/** 기업 정보 — 회사 기술스택 프로필의 요약. 회사 화면으로 가는 단추가 붙는다. */
function CompanyInfo({ co, location }: { co: { c: CompanyListItem; slug: string }; location?: string }) {
  const { c, slug } = co
  const roles = Object.entries(c.roles).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...roles.map(([, n]) => n))
  const meta = [c.size, c.domains[0]?.name, location].filter(Boolean).join(' · ')
  return (
    <Section title="기업 정보">
      <div className="flex flex-wrap items-center gap-4">
        <span className="grid place-items-center w-[72px] h-[72px] rounded-2xl overflow-hidden shrink-0">
          <CompanyMark name={c.name} size={72} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-xl font-bold text-[#272727]">{c.name}</div>
          <div className="mt-0.5 text-sm text-[#666] truncate">{meta}</div>
        </div>
        <a
          href={paths.company(slug)}
          onClick={onLinkClick(paths.company(slug))}
          className="h-9 px-4 rounded-[18px] border border-(--color-accent) text-sm font-medium leading-[34px] text-(--color-accent) hover:bg-(--color-accent-weak)"
        >
          기업 기술스택 보기 ›
        </a>
      </div>
      <div className="mt-5 grid sm:grid-cols-3 gap-[10px]">
        <InfoStat label="채용중인 공고" value={`${c.posting_count}`} unit="건" />
        <InfoStat label="가장 많이 뽑는 직군" value={roles[0]?.[0] ?? '-'} unit={roles[0] ? `${roles[0][1]}건` : ''} />
        <InfoStat label="많이 쓰는 기술" value={c.top_tech[0]?.name ?? '-'} unit={c.top_tech.slice(1, 3).map((t) => ` · ${t.name}`).join('')} />
      </div>
      {roles.length > 0 && (
        <ul className="mt-5 flex flex-col gap-3">
          {roles.slice(0, 5).map(([r, n]) => (
            <li key={r} className="flex items-center">
              <span className="w-[124px] shrink-0 text-sm text-[#474747] truncate">{r}</span>
              <span className="flex-1 h-3 rounded-md bg-[#f1f3f5] overflow-hidden">
                <span className="block h-full rounded-md bg-[#f67979]" style={{ width: `${(n / max) * 100}%` }} />
              </span>
              <span className="w-11 shrink-0 text-right text-sm font-medium text-[#272727] tabular-nums">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

function InfoStat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="h-[92px] rounded-2xl border border-[#e2e8ec] px-5 pt-4">
      <div className="text-[13px] text-[#777]">{label}</div>
      <div className="mt-1.5 truncate">
        <span className="text-xl font-bold text-[#272727]">{value}</span>
        {unit && <span className="text-sm text-[#474747]">{unit}</span>}
      </div>
    </div>
  )
}

function SideList({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-lg font-bold leading-[26px] text-[#272727]">{title}</h2>
      <div className="mt-[14px] flex flex-col gap-[10px]">{children}</div>
    </section>
  )
}

function SideCard({
  company,
  title,
  dday,
  chip,
  hot,
  onClick,
  href,
}: {
  company: string
  title: string
  dday?: string
  chip?: string
  hot?: boolean
  onClick?: () => void
  href?: string
}) {
  const body = (
    <>
      <span className="grid place-items-center w-9 h-9 rounded-[9px] overflow-hidden shrink-0">
        <CompanyMark name={company} size={36} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className="text-[15px] font-bold text-[#272727] truncate">{plainCompany(company)}</span>
          {dday && <span className="shrink-0 text-xs text-[#999]">{dday}</span>}
        </span>
        <span className="mt-0.5 block text-[13px] leading-[19px] text-[#474747] truncate">{title}</span>
        {chip && (
          <span className={'mt-2 inline-block rounded px-[7px] text-xs leading-[22px] ' + (hot ? 'bg-(--color-accent-weak) text-(--color-accent)' : 'bg-[#f4f4f4] text-[#474747]')}>
            {chip}
          </span>
        )}
      </span>
    </>
  )
  const cls = 'w-full text-left flex gap-3 rounded-[18px] border border-[#e2e8ec] bg-white px-[18px] py-4 hover:border-[#999]'
  return href ? (
    <a href={href} onClick={onLinkClick(href)} className={cls}>
      {body}
    </a>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {body}
    </button>
  )
}
