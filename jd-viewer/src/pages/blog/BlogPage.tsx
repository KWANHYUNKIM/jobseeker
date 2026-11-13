import { BlogView } from '../../features/blog/components/BlogView'
import { RadarView } from '../../features/radar/components/RadarView'

/**
 * `/blog` · `/radar` — 기술 블로그 글과 기업 100(레이더). 둘 사이를 오가던 막대는 뺐다 —
 * 블로그는 '학습', 레이더는 '기업정보' 묶음의 하위 메뉴(app/App.tsx)에서 들어간다.
 */
export function BlogPage({ mode, detail }: { mode: 'blog' | 'radar'; detail: string | null }) {
  return (
    <div key="blogradar" className="flex flex-col flex-1 min-h-0 jd-fade-in">
      {mode === 'blog' ? <BlogView postId={detail} /> : <RadarView companyKey={detail} />}
    </div>
  )
}
