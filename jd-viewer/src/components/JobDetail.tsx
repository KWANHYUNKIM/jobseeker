import { useEffect, useRef } from 'react'
import type { Job } from '../types'
import { classifyRoles, roleColor } from '../lib/classify'
import { useIsLight } from '../lib/useIsLight'
import { useSimilarJobs } from '../lib/useSimilar'

interface Props {
  job: Job
  onClose: () => void
  /** 비슷한 공고를 눌렀을 때 그 공고로 갈아끼운다. 없으면 추천 섹션을 감춘다. */
  onOpenUrl?: (url: string) => void
}

export function JobDetail({ job, onClose, onOpenUrl }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  // 추천을 눌러 다른 공고로 갈아끼면 내용만 바뀌고 스크롤은 그대로라 본문 중간이 보인다.
  const scrollRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 })
  }, [job.url])

  const isLight = useIsLight()
  const roles = classifyRoles(job.title, job.tech_stack, job.qualifications || '')
  const { lookup } = useSimilarJobs()
  const similar = onOpenUrl ? lookup(job.url) : []

  return (
    <div
      ref={scrollRef}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className="relative bg-(--color-panel) border border-(--color-border) rounded-lg w-full max-w-4xl my-4 shadow-2xl jd-modal-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="bg-(--color-panel) border-b border-(--color-border) rounded-t-lg px-6 py-4">
          <div className="flex items-start gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="text-xs px-2 py-0.5 rounded bg-(--color-bg) text-(--color-muted) border border-(--color-border)">
                  {job.site}
                </span>
                {roles.map((r) => (
                  <span
                    key={r}
                    className="text-xs px-2 py-0.5 rounded border"
                    style={{ borderColor: roleColor(r, isLight), color: roleColor(r, isLight) }}
                  >
                    {r}
                  </span>
                ))}
                {job.career && <span className="text-xs text-(--color-muted)">· {job.career}</span>}
                {job.location && <span className="text-xs text-(--color-muted)">· {job.location}</span>}
              </div>
              <h2 className="text-(--color-text) text-xl leading-snug">{job.title}</h2>
              <p className="text-(--color-muted) text-sm mt-1">{job.company}</p>
            </div>
            <button
              onClick={onClose}
              className="text-(--color-muted) hover:text-(--color-text) text-3xl leading-none w-9 h-9 rounded hover:bg-(--hover) shrink-0"
              aria-label="닫기 (ESC)"
              title="닫기 (ESC)"
            >
              ×
            </button>
          </div>
          {/* 원본 공고 링크 - 상단 강조 */}
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-(--color-accent) text-(--color-on-accent) text-sm font-medium hover:opacity-90"
            >
              원본 공고 열기 ↗
            </a>
          )}
        </div>

        {/* 본문 */}
        <div className="px-6 py-5 space-y-5 text-sm">
          {job.tech_stack && job.tech_stack.length > 0 && (
            <Section title="기술 스택">
              <div className="flex flex-wrap gap-1.5">
                {job.tech_stack.map((t) => (
                  <span
                    key={t}
                    className="text-xs px-2 py-1 rounded bg-(--color-accent)/15 text-(--color-accent) border border-(--color-accent)/30"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </Section>
          )}

          <Section title="주요 업무">
            <FieldOrPlaceholder text={job.main_tasks} url={job.url} />
          </Section>

          <Section title="자격 요건">
            <FieldOrPlaceholder text={job.qualifications} url={job.url} />
          </Section>

          <Section title="우대 사항">
            <FieldOrPlaceholder text={job.preferences} url={job.url} />
          </Section>

          {job.benefits && (
            <Section title="복지 / 혜택">
              <Pre text={job.benefits} />
            </Section>
          )}

          {job.full_jd && (
            <details className="mt-4 border-t border-(--color-border) pt-4">
              <summary className="cursor-pointer text-(--color-muted) hover:text-(--color-text) text-xs uppercase tracking-wider">
                전체 JD 원문 보기
              </summary>
              <Pre text={job.full_jd} muted />
            </details>
          )}

          {similar.length > 0 && onOpenUrl && (
            <section className="mt-4 border-t border-(--color-border) pt-4">
              <h3 className="text-xs uppercase tracking-wider text-(--color-muted) mb-2.5 font-medium">
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
        </div>

        {/* 하단 푸터 - 다시 한번 원본 링크 */}
        <div className="border-t border-(--color-border) px-6 py-4 rounded-b-lg bg-(--color-bg)/40 flex flex-wrap items-center gap-3">
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
          <button
            onClick={onClose}
            className="ml-auto px-4 py-2 rounded border border-(--color-border) text-sm hover:bg-(--color-bg)"
          >
            닫기 (ESC)
          </button>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-wider text-(--color-muted) mb-2 font-medium">
        {title}
      </h3>
      {children}
    </section>
  )
}

function FieldOrPlaceholder({ text, url }: { text: string | undefined; url: string }) {
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
  return <Pre text={trimmed} />
}

function Pre({ text, muted = false }: { text: string; muted?: boolean }) {
  return (
    <pre
      className={
        'whitespace-pre-wrap font-sans text-[13px] leading-relaxed ' +
        (muted ? 'text-(--color-muted)' : 'text-(--color-text)')
      }
    >
      {text}
    </pre>
  )
}
