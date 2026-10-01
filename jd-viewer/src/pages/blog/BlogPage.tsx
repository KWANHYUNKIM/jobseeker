import type { ReactNode } from 'react'
import { BlogView } from '../../features/blog/components/BlogView'
import { RadarView } from '../../features/radar/components/RadarView'
import { onLinkClick } from '../../utils/navigation'
import { paths } from '../../utils/urls'

/** `/blog` · `/radar` — 기술 블로그 글과 기업 100(레이더)을 한 탭에서 바꿔 본다. */
export function BlogPage({ mode, detail }: { mode: 'blog' | 'radar'; detail: string | null }) {
  return (
    <div key="blogradar" className="flex flex-col flex-1 min-h-0 jd-fade-in jd-canvas">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60">
        <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden shrink-0">
          <ModeLink active={mode === 'blog'} to={paths.blog()}>블로그 글</ModeLink>
          <ModeLink active={mode === 'radar'} to={paths.radar()}>기업 100 (레이더)</ModeLink>
        </div>
        <span className="hidden sm:inline text-xs text-(--color-muted) truncate">
          {mode === 'blog' ? '기업 기술 블로그 글 모음' : '글로벌 IT 대기업 100곳의 기술 스택·아키텍처·토론·전형'}
        </span>
      </div>
      {mode === 'blog' ? <BlogView postId={detail} /> : <RadarView companyKey={detail} />}
    </div>
  )
}

function ModeLink({ active, to, children }: { active: boolean; to: string; children: ReactNode }) {
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className={`px-3 py-1 text-xs font-medium transition whitespace-nowrap ${
        active ? 'bg-(--color-accent) text-(--color-on-accent)' : 'bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {children}
    </a>
  )
}
