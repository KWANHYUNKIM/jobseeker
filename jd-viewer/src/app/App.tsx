import type { ReactNode } from 'react'
import { useJobBoardContext } from '../features/jobs/hooks/useJobBoard'
import { onLinkClick, useRoute } from '../utils/navigation'
import { paths } from '../utils/urls'
import { Providers } from './providers'
import { RouteView, tabOf, type Tab } from './router'

/** 앱 껍데기 — 위쪽 탭 막대와, 주소에 맞는 페이지(app/router.tsx). */
function App() {
  return (
    <Providers>
      <div className="flex flex-col h-screen">
        <TopNav />
        <RouteView />
      </div>
    </Providers>
  )
}

const TABS: { tab: Tab; label: string; to: () => string; also?: Tab[] }[] = [
  { tab: 'jobs', label: '잡 리스트', to: paths.jobs },
  { tab: 'companies', label: '기업 기술스택', to: paths.companies },
  { tab: 'mindmap', label: '커리어 마인드맵', to: paths.mindmap },
  { tab: 'blog', label: '기술 블로그', to: paths.blog, also: ['radar'] },
  { tab: 'calendar', label: '모집 캘린더', to: paths.calendar },
  { tab: 'reposts', label: '재공고', to: paths.reposts },
  { tab: 'freelance', label: '외주·프리', to: paths.freelance },
  { tab: 'trend', label: '개발 트렌드', to: () => paths.trend() },
  { tab: 'book', label: '기술도서', to: paths.wiki },
  { tab: 'reveng', label: '기술 역설계', to: paths.reveng },
  { tab: 'hardware', label: 'PC 하드웨어', to: paths.hardware },
]

function TopNav() {
  const tab = tabOf(useRoute())
  const { countsReady, totalCount, filteredCount } = useJobBoardContext()
  return (
    <nav className="flex items-center gap-3 px-4 sm:px-6 h-14 border-b border-(--color-border) bg-(--color-panel) sticky top-0 z-30">
      <a href="/" onClick={onLinkClick('/')} className="hidden md:flex items-baseline gap-1.5 shrink-0 mr-3 select-none">
        <span className="text-lg font-extrabold text-(--color-accent) tracking-tight">JD</span>
        <span className="text-lg font-bold text-(--color-text) tracking-tight">Viewer</span>
      </a>
      <div className="flex items-center gap-1 overflow-x-auto no-scrollbar -mx-1 px-1">
        {TABS.map((t) => (
          <TabLink key={t.tab} active={tab === t.tab || !!t.also?.includes(tab)} to={t.to()}>
            {t.label}
          </TabLink>
        ))}
      </div>
      <span className="ml-auto shrink-0 text-xs text-(--color-muted) tabular-nums whitespace-nowrap">
        {/* 첫 응답 전에는 0 이 아니라 '…' — 0건은 "공고가 없다" 로 읽힌다. */}
        <span className="text-(--color-text) font-medium">{countsReady ? totalCount.toLocaleString() : '…'}</span>건
        <span className="hidden sm:inline"> · 필터 </span>
        <span className="hidden sm:inline text-(--color-accent) font-medium">
          {countsReady ? filteredCount.toLocaleString() : '…'}
        </span>
        <span className="hidden sm:inline">건</span>
      </span>
    </nav>
  )
}

// 탭은 진짜 링크다. 크롤러는 onClick 을 따라가지 않는다 — href 가 있어야 다음 페이지를 본다.
function TabLink({ active, to, children }: { active: boolean; to: string; children: ReactNode }) {
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className={`relative px-3 py-2 text-[15px] transition whitespace-nowrap shrink-0 after:absolute after:left-3 after:right-3 after:-bottom-px after:h-0.5 ${
        active
          ? 'text-(--color-accent) font-bold after:bg-(--color-accent)'
          : 'text-(--color-muted) hover:text-(--color-text) after:bg-transparent'
      }`}
    >
      {children}
    </a>
  )
}

export default App
