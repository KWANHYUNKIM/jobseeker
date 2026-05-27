import { useEffect, useRef, useState } from 'react'
import type { Job } from '../types'

interface Props {
  jobs: Job[]
  selected: Job | null
  onSelect: (j: Job) => void
}

const PAGE = 50

export function JobList({ jobs, selected, onSelect }: Props) {
  const [limit, setLimit] = useState(PAGE)
  const sentinel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLimit(PAGE)
  }, [jobs])

  useEffect(() => {
    if (!sentinel.current) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) setLimit((l) => Math.min(l + PAGE, jobs.length))
      },
      { rootMargin: '400px' },
    )
    obs.observe(sentinel.current)
    return () => obs.disconnect()
  }, [jobs.length, limit])

  if (jobs.length === 0) {
    return (
      <div className="p-8 text-center text-(--color-muted)">
        조건에 맞는 공고가 없습니다.
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      {jobs.slice(0, limit).map((j) => (
        <Row
          key={`${j.site}-${j.pid}-${j.idx}`}
          job={j}
          active={selected?.site === j.site && selected?.pid === j.pid}
          onClick={() => onSelect(j)}
        />
      ))}
      {limit < jobs.length && (
        <div ref={sentinel} className="p-4 text-center text-xs text-(--color-muted)">
          {limit} / {jobs.length} 표시 중... (스크롤하면 더 로드)
        </div>
      )}
    </div>
  )
}

function Row({ job, active, onClick }: { job: Job; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={
        'text-left px-4 py-3 border-b border-(--color-border) transition ' +
        (active ? 'bg-(--color-accent)/15' : 'hover:bg-white/3')
      }
    >
      <div className="flex items-baseline gap-2">
        <span className="text-xs px-1.5 py-0.5 rounded bg-(--color-bg) text-(--color-muted) border border-(--color-border)">
          {job.site}
        </span>
        <span className="text-sm text-(--color-muted) truncate">{job.company}</span>
        {job.career && (
          <span className="text-xs text-(--color-muted) ml-auto">{job.career}</span>
        )}
      </div>
      <div className="mt-1 text-white text-[15px] leading-snug">{job.title}</div>
      {job.tech_stack.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {job.tech_stack.slice(0, 10).map((t) => (
            <span
              key={t}
              className="text-[11px] px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)"
            >
              {t}
            </span>
          ))}
          {job.tech_stack.length > 10 && (
            <span className="text-[11px] text-(--color-muted)">+{job.tech_stack.length - 10}</span>
          )}
        </div>
      )}
    </button>
  )
}
