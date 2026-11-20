import { useMemo, useState } from 'react'
import { useLectureIndex, useLecture, hms, at, type LectureCard, type Lecture, type Chapter } from '../hooks/useLectures'
import { ArchitectureDiagram } from '../../../components/ArchitectureDiagram'
import { goBack, onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import { Loader, ErrorState, EmptyState, hits } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'

// 강의 노트 — 공개 강의 영상(Stanford CS229·CS336·CS25 …)을 자막(말)과 장면(판서·슬라이드)으로
// 읽고 우리 말로 다시 쓴 노트. 목적은 둘이다: 요즘 업계가 어디로 가나(trends), 그래서 무엇을
// 어떤 순서로 공부하나(study). 원본 영상은 챕터마다 그 시각으로 링크한다 — 노트는 원본을
// 대신하지 않고, 어디를 다시 볼지 알려 준다.

const LEVEL_TONE: Record<string, string> = {
  입문: 'bg-[#e8f6ee] text-[#1b7a44]',
  중급: 'bg-[#eef2ff] text-[#3b4fc4]',
  심화: 'bg-[#fdecec] text-[#b42318]',
}

export function LecturesView({ seg = [] }: { seg?: string[] }) {
  const id = seg[0] ?? null
  const { data, loading, error } = useLectureIndex()
  const [topic, setTopic] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const items = useMemo(() => data?.items ?? [], [data])
  const shown = useMemo(
    () =>
      items.filter(
        (c) =>
          (!topic || c.topic === topic) &&
          hits(query, c.title, c.title_ko, c.one_line, c.code, c.school, c.speaker, ...(c.tags ?? [])),
      ),
    [items, topic, query],
  )
  const entry = id ? items.find((c) => c.id === id) : null
  useSeo(
    entry
      ? {
          title: `${entry.title_ko} — ${[entry.school, entry.code].filter(Boolean).join(' ')} 강의 노트`,
          description: clip(entry.one_line),
          canonical: absUrl(paths.lecture(entry.id)),
        }
      : null,
  )

  if (id) return <LectureDetail id={id} />
  if (loading) return <Loader label="강의 노트 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="lectures/index.json 로드 실패"
        detail={error}
        hint={<code className="text-(--color-text)">python lecture-engine/validate.py</code>}
      />
    )

  const schools = new Set(items.map((c) => c.school).filter(Boolean)).size
  const totalSec = items.reduce((s, c) => s + (c.duration_sec ?? 0), 0)

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">강의 노트</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          Stanford 같은 공개 강의 영상을 <b className="font-bold text-(--color-accent)">자막과 장면(슬라이드·판서)으로 끝까지 읽고</b>{' '}
          요약·업계 흐름·공부 순서로 다시 정리했어요. 챕터를 누르면 원본 영상의 그 자리로 갑니다.
        </p>

        {items.length === 0 ? (
          <EmptyState title="아직 정리한 강의가 없습니다" hint={<code>lecture-engine/state/QUEUE.md</code>} />
        ) : (
          <>
            <div className="mt-[27px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
              <Stat label="정리한 강의" value={`${items.length}편`} accent />
              <Stat label="영상 길이 합" value={`${Math.round(totalSec / 3600)}시간`} />
              <Stat label="학교·채널" value={`${schools}곳`} />
              <Stat label="갱신" value={data?.generated_at.slice(0, 10) ?? '-'} />
            </div>

            <label className="mt-[26px] flex items-center gap-2.5 h-[52px] rounded-[26px] border border-[#c4c4c4] pl-[23px] pr-5 focus-within:border-[#272727]">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2" aria-hidden className="shrink-0">
                <circle cx="8.5" cy="8.5" r="5.5" />
                <path d="M12.5 12.5 16 16" strokeLinecap="round" />
              </svg>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="주제·과목·기술로 찾아보세요 (예: Transformer, CS229, 에이전트)"
                aria-label="강의 검색"
                className="flex-1 min-w-0 bg-transparent text-[15px] text-[#272727] placeholder:text-[#999] outline-none"
              />
            </label>

            <div className="mt-[18px] flex flex-wrap gap-2">
              <Chip active={!topic} onClick={() => setTopic(null)}>
                전체 <span className="opacity-60">{items.length}</span>
              </Chip>
              {(data?.topics ?? []).map((t) => (
                <Chip key={t.key} active={topic === t.key} onClick={() => setTopic(topic === t.key ? null : t.key)}>
                  {t.label} <span className="opacity-60">{t.count}</span>
                </Chip>
              ))}
            </div>

            <div className="mt-[34px] grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {shown.map((c) => (
                <Card key={c.id} c={c} />
              ))}
            </div>
            {shown.length === 0 && <EmptyState title="조건에 맞는 강의가 없습니다" />}
          </>
        )}
      </div>
      <SiteFooter />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-[#e5e5e5] px-5 py-4">
      <div className="text-[13px] text-[#888]">{label}</div>
      <div className={`mt-1 text-[22px] font-bold ${accent ? 'text-(--color-accent)' : 'text-[#272727]'}`}>{value}</div>
    </div>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`h-9 px-4 rounded-full border text-sm transition ${
        active ? 'border-(--color-accent) bg-(--color-accent-weak) text-(--color-accent) font-bold' : 'border-[#d8d8d8] text-[#444] hover:border-[#272727]'
      }`}
    >
      {children}
    </button>
  )
}

function Card({ c }: { c: LectureCard }) {
  const href = paths.lecture(c.id)
  return (
    <a href={href} onClick={onLinkClick(href)} className="group flex flex-col rounded-xl border border-[#e5e5e5] overflow-hidden hover:border-[#272727] transition">
      <div className="relative aspect-video bg-[#f2f2f2]">
        {c.thumbnail && <img src={c.thumbnail} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />}
        {c.duration_sec != null && (
          <span className="absolute right-2 bottom-2 rounded bg-black/75 px-1.5 py-0.5 text-xs text-white">{hms(c.duration_sec)}</span>
        )}
      </div>
      <div className="flex-1 flex flex-col p-4">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="font-bold text-[#272727]">{[c.school, c.code].filter(Boolean).join(' ')}</span>
          {c.term && <span className="text-[#888]">· {c.term}</span>}
          <span className={`ml-auto rounded px-1.5 py-0.5 ${LEVEL_TONE[c.level] ?? ''}`}>{c.level}</span>
        </div>
        <h3 className="mt-2 text-[17px] font-bold leading-6 text-[#272727] group-hover:text-(--color-accent)">{c.title_ko}</h3>
        <p className="mt-1.5 text-sm leading-5 text-[#666] line-clamp-2">{c.one_line}</p>
        <div className="mt-auto pt-3 flex flex-wrap gap-1">
          {c.tags.slice(0, 5).map((t) => (
            <span key={t} className="rounded bg-[#f4f4f4] px-1.5 py-0.5 text-xs text-[#555]">
              {t}
            </span>
          ))}
        </div>
      </div>
    </a>
  )
}

// ── 상세 ─────────────────────────────────────────────────────

function LectureDetail({ id }: { id: string }) {
  const { data: d, loading, error } = useLecture(id)
  if (loading) return <Loader label="노트 불러오는 중…" />
  if (error || !d) return <ErrorState title="노트를 찾을 수 없습니다" detail={error ?? id} />
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[34px] pb-[90px]">
      {/* jd-container 가 폭을 넓게 잡는다 — 읽는 글이라 안쪽에서 한 줄 길이를 다시 줄인다 */}
      <article className="max-w-[860px] mx-auto">
        <button type="button" onClick={() => goBack(paths.lectures())} className="text-sm text-[#666] hover:text-[#272727]">
          ← 강의 노트
        </button>
        <Head d={d} />
        <Section title="한눈에">
          <div className="space-y-3 text-[15px] leading-7 text-[#333]">
            {d.summary.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
          {d.why_now && (
            <div className="mt-5 rounded-xl bg-(--color-accent-weak) px-5 py-4 text-[15px] leading-7 text-[#272727]">
              <b className="text-(--color-accent)">왜 지금 이걸 보나 · </b>
              {d.why_now}
            </div>
          )}
        </Section>

        <Section title="본문" sub="챕터마다 설명 → 식 → 손으로 따라가는 예 → 코드 → 확인 문제. 시각을 누르면 원본 영상의 그 자리로 갑니다">
          <Toc d={d} />
          <div className="mt-8 space-y-14">
            {d.chapters.map((c, i) => (
              <ChapterView key={i} c={c} n={i + 1} url={d.source.url} id={d.id} />
            ))}
          </div>
        </Section>

        <Section title="핵심 개념">
          <dl className="grid sm:grid-cols-2 gap-3">
            {d.concepts.map((c) => (
              <div key={c.term} className="rounded-xl border border-[#e5e5e5] px-4 py-3">
                <dt className="flex items-baseline gap-2 font-bold text-[#272727]">
                  {c.term}
                  {c.at != null && (
                    <a href={at(d.source.url, c.at)} target="_blank" rel="noreferrer" className="ml-auto font-mono text-xs font-normal text-[#888] hover:text-(--color-accent)">
                      {hms(c.at)}
                    </a>
                  )}
                </dt>
                <dd className="mt-1 text-[14px] leading-6 text-[#555]">{c.explain}</dd>
              </div>
            ))}
          </dl>
        </Section>

        {!!d.trends?.length && (
          <Section title="업계 흐름" sub="강의가 말한 것 — 강사 개인 의견은 따로 표시했습니다">
            <ul className="space-y-3">
              {d.trends.map((t, i) => (
                <li key={i} className="rounded-xl bg-[#fafafa] px-4 py-3">
                  <div className="flex gap-2">
                    <span className="font-bold text-[#272727]">{t.claim}</span>
                    {t.at != null && (
                      <a href={at(d.source.url, t.at)} target="_blank" rel="noreferrer" className="ml-auto shrink-0 font-mono text-xs text-[#888] hover:text-(--color-accent)">
                        {hms(t.at)}
                      </a>
                    )}
                  </div>
                  {t.evidence && <p className="mt-1 text-[14px] leading-6 text-[#555]">{t.evidence}</p>}
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="이렇게 공부하세요">
          {!!d.study.prereq?.length && (
            <p className="mb-4 text-[14.5px] text-[#444]">
              <b className="text-[#272727]">먼저 알면 좋은 것 · </b>
              {d.study.prereq.join(' · ')}
            </p>
          )}
          <ol className="space-y-3">
            {d.study.steps.map((s, i) => (
              <li key={i} className="flex gap-3">
                <span className="shrink-0 w-7 h-7 rounded-full bg-(--color-accent) text-white text-sm font-bold flex items-center justify-center">{i + 1}</span>
                <div>
                  <div className="font-bold text-[#272727] leading-7">{s.do}</div>
                  {s.why && <div className="text-[14px] leading-6 text-[#666]">{s.why}</div>}
                </div>
              </li>
            ))}
          </ol>
          {!!d.study.practice?.length && (
            <div className="mt-6">
              <h3 className="font-bold text-[#272727]">손으로 해 볼 것</h3>
              <ul className="mt-2 space-y-1.5">
                {d.study.practice.map((p, i) => (
                  <li key={i} className="flex gap-2 text-[14.5px] leading-6 text-[#444]">
                    <span className="text-(--color-accent)">☐</span>
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!!d.study.resources?.length && (
            <div className="mt-6">
              <h3 className="font-bold text-[#272727]">공식 자료</h3>
              <ul className="mt-2 space-y-1">
                {d.study.resources.map((r) => (
                  <li key={r.url}>
                    <a href={r.url} target="_blank" rel="noreferrer" className="text-[14.5px] text-(--color-accent) hover:underline">
                      {r.title} ↗
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Section>

        {(d.jobs?.roles?.length || d.jobs?.skills?.length) && (
          <Section title="채용과 잇기" sub="기술을 누르면 그 기술을 찾는 공고로 갑니다">
            {!!d.jobs?.roles?.length && <p className="text-[14.5px] text-[#444]"><b className="text-[#272727]">닿는 직무 · </b>{d.jobs.roles.join(' · ')}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              {(d.jobs?.skills ?? []).map((s) => {
                const href = `${paths.jobs()}?q=${encodeURIComponent(s)}`
                return (
                  <a key={s} href={href} onClick={onLinkClick(href)} className="h-8 px-3 rounded-full border border-[#d8d8d8] text-sm leading-8 text-[#444] hover:border-(--color-accent) hover:text-(--color-accent)">
                    {s}
                  </a>
                )
              })}
            </div>
          </Section>
        )}

        <p className="mt-12 text-xs leading-5 text-[#999]">
          이 노트는 원본 영상의 {d.materials.transcript === 'official' ? '공식' : d.materials.transcript === 'auto' ? '자동' : ''} 자막
          {d.materials.frames ? `과 ${d.materials.every_sec}초 간격 장면 ${d.materials.frames}장` : ''}을 읽고 직접 다시 쓴 요약입니다(작성 {d.written_at}).
          강의의 저작권은 {d.source.channel}에 있으며, 정확한 내용은 원본을 확인하세요.
        </p>
      </article>
      </div>
      <SiteFooter />
    </div>
  )
}

function Head({ d }: { d: Lecture }) {
  return (
    <header className="mt-4 pb-6 border-b-2 border-[#272727]">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-bold text-[#272727]">{[d.course.school, d.course.code].filter(Boolean).join(' ')}</span>
        {d.course.term && <span className="text-[#888]">{d.course.term}</span>}
        {d.course.speaker && <span className="text-[#888]">· {d.course.speaker}</span>}
        <span className={`rounded px-1.5 py-0.5 text-xs ${LEVEL_TONE[d.level] ?? ''}`}>{d.level}</span>
      </div>
      <h1 className="mt-2 text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">{d.title_ko}</h1>
      <p className="text-[15px] text-[#888]">{d.title}</p>
      <p className="mt-3 text-[16px] leading-7 text-[#333]">{d.one_line}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-[#666]">
        <a href={d.source.url} target="_blank" rel="noreferrer" className="h-9 px-4 rounded-full bg-[#272727] text-white leading-9 font-bold hover:bg-black">
          원본 영상 보기 ↗
        </a>
        <span>{d.source.channel}</span>
        {d.source.duration_sec != null && <span>· {hms(d.source.duration_sec)}</span>}
        {d.source.published && <span>· {d.source.published}</span>}
        {d.source.views != null && <span>· 조회 {d.source.views.toLocaleString()}</span>}
      </div>
    </header>
  )
}

function Section({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-[21px] font-bold text-[#272727]">{title}</h2>
      {sub && <p className="mt-0.5 text-[13px] text-[#888]">{sub}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** 차례 — 노트가 길어져서(1시간 강의면 본문 1만 자 넘게) 바로 건너뛸 곳이 필요하다. */
function Toc({ d }: { d: Lecture }) {
  return (
    <nav aria-label="차례" className="rounded-xl bg-[#fafafa] px-5 py-4">
      <div className="text-sm font-bold text-[#272727]">차례</div>
      <ol className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-1">
        {d.chapters.map((c, i) => (
          <li key={i} className="text-[14px] leading-6">
            <a href={`#ch-${i + 1}`} className="text-[#444] hover:text-(--color-accent)">
              <span className="font-mono text-[#999] mr-1.5">{i + 1}.</span>
              {c.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}

function ChapterView({ c, n, url, id }: { c: Chapter; n: number; url: string; id: string }) {
  return (
    <section id={`ch-${n}`} className="scroll-mt-28">
      <div className="flex items-baseline gap-3 flex-wrap pb-2 border-b border-[#e5e5e5]">
        <span className="text-[13px] font-bold text-(--color-accent)">{n}장</span>
        <h3 className="text-[19px] font-bold text-[#272727]">{c.title}</h3>
        <a href={at(url, c.start)} target="_blank" rel="noreferrer" className="ml-auto font-mono text-sm text-(--color-accent) hover:underline">
          ▶ {hms(c.start)}
        </a>
      </div>

      {c.explain?.length ? (
        <div className="mt-4 space-y-3 text-[15.5px] leading-[1.85] text-[#2b2b2b]">
          {c.explain.map((p, j) => (
            <p key={j}>{p}</p>
          ))}
        </div>
      ) : null}

      {!!c.formulas?.length && (
        <div className="mt-5 space-y-2">
          {c.formulas.map((f, j) => (
            <div key={j} className="rounded-lg border border-[#e5e5e5] overflow-hidden">
              <div className="bg-[#f7f7fb] px-4 py-2.5 font-mono text-[15px] text-[#1f2a5a] overflow-x-auto whitespace-pre">{f.expr}</div>
              <div className="px-4 py-2 text-[14px] leading-6 text-[#555]">{f.meaning}</div>
            </div>
          ))}
        </div>
      )}

      {c.example && (
        <div className="mt-5 rounded-xl border-l-4 border-(--color-accent) bg-(--color-accent-weak) px-5 py-4">
          <div className="text-sm font-bold text-(--color-accent)">손으로 따라가 보기 · {c.example.title}</div>
          <p className="mt-1.5 text-[14.5px] leading-7 text-[#2b2b2b] whitespace-pre-line">{c.example.body}</p>
        </div>
      )}

      {c.code && (
        <figure className="mt-5">
          <pre className="rounded-xl bg-[#1e1e24] text-[#e8e8ee] px-4 py-3 text-[13px] leading-6 overflow-x-auto">
            <code>{c.code.src}</code>
          </pre>
          <figcaption className="mt-1 text-[13px] text-[#888]">
            {c.code.lang}
            {c.code.note ? ` · ${c.code.note}` : ''}
          </figcaption>
        </figure>
      )}

      {c.diagram && (
        <figure className="mt-5 rounded-xl border border-[#e5e5e5] p-3">
          {c.diagram.title && <figcaption className="mb-2 text-sm font-bold text-[#272727]">{c.diagram.title}</figcaption>}
          <ArchitectureDiagram code={c.diagram.code} idKey={`lec-${id}-${n}`} soft />
        </figure>
      )}

      {c.on_screen && (
        <p className="mt-5 rounded-lg border border-dashed border-[#d0d0d0] px-3 py-2 text-[13.5px] leading-6 text-[#555]">
          <span className="font-bold text-[#272727]">화면에 뜬 것 · </span>
          {c.on_screen}
        </p>
      )}

      {!!c.pitfalls?.length && (
        <div className="mt-5 rounded-xl bg-[#fff7ec] px-5 py-3">
          <div className="text-sm font-bold text-[#a15c00]">헷갈리기 쉬운 것</div>
          <ul className="mt-1 list-disc pl-5 space-y-1 text-[14.5px] leading-6 text-[#5a4320]">
            {c.pitfalls.map((p, j) => (
              <li key={j}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 rounded-xl bg-[#fafafa] px-5 py-3">
        <div className="text-sm font-bold text-[#272727]">요점</div>
        <ul className="mt-1 list-disc pl-5 space-y-1 text-[14.5px] leading-6 text-[#444]">
          {c.points.map((p, j) => (
            <li key={j}>{p}</li>
          ))}
        </ul>
      </div>

      {!!c.check?.length && (
        <div className="mt-4 space-y-2">
          {c.check.map((q, j) => (
            <details key={j} className="group rounded-xl border border-[#e5e5e5] px-4 py-3">
              <summary className="cursor-pointer list-none text-[14.5px] font-bold text-[#272727]">
                <span className="text-(--color-accent) mr-1.5">Q.</span>
                {q.q}
                <span className="ml-2 text-xs font-normal text-[#999] group-open:hidden">답 보기</span>
              </summary>
              <p className="mt-2 text-[14.5px] leading-7 text-[#444]">{q.a}</p>
            </details>
          ))}
        </div>
      )}
    </section>
  )
}
