import { useEffect } from 'react'
import type { Job } from '../types'
import { classifyRoles, ROLE_COLORS } from '../lib/classify'

interface Props {
  job: Job
  onClose: () => void
}

export function JobDetail({ job, onClose }: Props) {
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

  const roles = classifyRoles(job.title, job.tech_stack, job.qualifications || '')

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className="relative bg-(--color-panel) border border-(--color-border) rounded-lg w-full max-w-4xl my-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="sticky top-0 z-10 bg-(--color-panel)/95 backdrop-blur border-b border-(--color-border) rounded-t-lg px-6 py-4">
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
                    style={{ borderColor: ROLE_COLORS[r] || '#444', color: ROLE_COLORS[r] || '#aaa' }}
                  >
                    {r}
                  </span>
                ))}
                {job.career && <span className="text-xs text-(--color-muted)">· {job.career}</span>}
                {job.location && <span className="text-xs text-(--color-muted)">· {job.location}</span>}
              </div>
              <h2 className="text-white text-xl leading-snug">{job.title}</h2>
              <p className="text-(--color-muted) text-sm mt-1">{job.company}</p>
            </div>
            <button
              onClick={onClose}
              className="text-(--color-muted) hover:text-white text-3xl leading-none w-9 h-9 rounded hover:bg-white/5 shrink-0"
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
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-(--color-accent) text-black text-sm font-medium hover:opacity-90"
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
              <summary className="cursor-pointer text-(--color-muted) hover:text-white text-xs uppercase tracking-wider">
                전체 JD 원문 보기
              </summary>
              <Pre text={job.full_jd} muted />
            </details>
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
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-(--color-accent) text-black font-medium hover:opacity-90"
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
