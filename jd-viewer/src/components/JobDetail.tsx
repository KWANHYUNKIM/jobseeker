import { useEffect } from 'react'
import type { Job } from '../types'

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
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <aside className="w-[40%] min-w-[460px] max-w-[640px] shrink-0 border-l border-(--color-border) bg-(--color-panel) h-screen sticky top-0 overflow-y-auto">
      <div className="sticky top-0 bg-(--color-panel) border-b border-(--color-border) p-4 flex items-start gap-3 z-10">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs px-1.5 py-0.5 rounded bg-(--color-bg) text-(--color-muted) border border-(--color-border)">
              {job.site}
            </span>
            {job.career && (
              <span className="text-xs text-(--color-muted)">{job.career}</span>
            )}
            {job.location && (
              <span className="text-xs text-(--color-muted)">· {job.location}</span>
            )}
          </div>
          <h2 className="text-white text-lg leading-snug">{job.title}</h2>
          <p className="text-(--color-muted) text-sm mt-0.5">{job.company}</p>
        </div>
        <button
          onClick={onClose}
          className="text-(--color-muted) hover:text-white text-2xl leading-none w-8 h-8 rounded hover:bg-white/5"
          aria-label="닫기"
        >
          ×
        </button>
      </div>

      <div className="p-4 space-y-4 text-sm">
        {job.tech_stack.length > 0 && (
          <Section title="기술스택">
            <div className="flex flex-wrap gap-1.5">
              {job.tech_stack.map((t) => (
                <span
                  key={t}
                  className="text-xs px-2 py-0.5 rounded bg-(--color-accent)/15 text-(--color-accent) border border-(--color-accent)/30"
                >
                  {t}
                </span>
              ))}
            </div>
          </Section>
        )}
        {job.main_tasks && <Section title="주요업무"><Pre text={job.main_tasks} /></Section>}
        {job.qualifications && <Section title="자격요건"><Pre text={job.qualifications} /></Section>}
        {job.preferences && <Section title="우대사항"><Pre text={job.preferences} /></Section>}
        {job.benefits && <Section title="복지/혜택"><Pre text={job.benefits} /></Section>}

        <div className="pt-2">
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block px-3 py-2 rounded bg-(--color-accent) text-black font-medium hover:opacity-90"
          >
            원본 공고 열기 ↗
          </a>
        </div>

        <details className="mt-4">
          <summary className="cursor-pointer text-(--color-muted) hover:text-white text-xs">
            전체 JD 본문 보기
          </summary>
          <Pre text={job.full_jd} muted />
        </details>
      </div>
    </aside>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-wider text-(--color-muted) mb-2">{title}</h3>
      {children}
    </section>
  )
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
