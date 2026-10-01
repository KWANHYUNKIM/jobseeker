import { useEffect } from 'react'
import { BlogPage } from '../pages/blog/BlogPage'
import { BookPage } from '../pages/book/BookPage'
import { CalendarPage } from '../pages/calendar/CalendarPage'
import { CompaniesPage } from '../pages/companies/CompaniesPage'
import { FreelancePage } from '../pages/freelance/FreelancePage'
import { HardwarePage } from '../pages/hardware/HardwarePage'
import { JobsPage } from '../pages/jobs/JobsPage'
import { MindmapPage } from '../pages/mindmap/MindmapPage'
import { RepostsPage } from '../pages/reposts/RepostsPage'
import { RevengPage } from '../pages/reveng/RevengPage'
import { TrendPage } from '../pages/trend/TrendPage'
import { navigate, useRoute, type Route } from '../utils/navigation'
import { useSeo, absUrl } from '../utils/seo'
import { paths, TAB_SEO } from '../utils/urls'

/** 페이지 경로 설정 — 경로 첫 세그먼트 → 탭 → 페이지. 루트(`/`)는 잡 리스트다. */
export type Tab =
  | 'jobs' | 'companies' | 'mindmap' | 'blog' | 'radar' | 'calendar' | 'trend'
  | 'book' | 'reveng' | 'reposts' | 'freelance' | 'hardware'

const TAB_BY_SEG: Record<string, Tab> = {
  '': 'jobs',
  jobs: 'jobs',
  companies: 'companies',
  mindmap: 'mindmap',
  blog: 'blog',
  radar: 'radar',
  calendar: 'calendar',
  trend: 'trend',
  // `/wiki` 는 예전에 기술 백과사전(낱말 단위)이었고 지금은 책장이다. 경로를 그대로
  // 물려받은 이유는 북마크·기록이 이미 그 주소를 가리키고 있어서다.
  wiki: 'book',
  reveng: 'reveng',
  reposts: 'reposts',
  freelance: 'freelance',
  hardware: 'hardware',
}

export function tabOf(route: Route): Tab {
  return TAB_BY_SEG[route.seg[0] ?? ''] ?? 'jobs'
}

/**
 * 옛 주소를 새 주소로 넘긴다. `/jobs` 와 `/` 는 같은 화면이라 목록의 주소는 `/` 하나로
 * 모은다(주소 두 개로 색인되면 서로의 순위를 갉아먹는다). 경로에 쓰던 한글 낱말
 * (`/reveng/문서/...`)은 영어로 바꿨다 — 이미 나간 링크는 새 주소로 넘긴다.
 */
function useLegacyRedirects(route: Route) {
  useEffect(() => {
    if (route.path === '/jobs') navigate(paths.jobs(), { replace: true })
    else if (route.seg[0] === 'reveng' && route.seg[1] === '문서') {
      navigate(route.seg[2] ? paths.revengDoc(route.seg[2]) : paths.reveng(), { replace: true })
    }
  }, [route.path, route.seg])
}

/**
 * 탭 단위 제목·설명. 상세 화면(공고·회사·레이더·역설계·블로그 글)과 책·부품 화면은
 * 그 데이터를 들고 있는 페이지가 직접 단다 — 여기서 탭 제목을 달면 모든 회사 페이지가
 * "기업 기술스택 분석" 한 줄로 색인된다.
 */
function useTabSeo(route: Route, tab: Tab) {
  const detail = route.seg[1] ?? null
  const own =
    (tab === 'jobs' && !!detail) ||
    (!!detail && (tab === 'companies' || tab === 'radar' || tab === 'reveng' || tab === 'blog')) ||
    tab === 'book' ||
    tab === 'hardware' ||
    // 잡 리스트는 검색어가 걸렸을 때 noindex 를 다는 일까지 JobsPage 가 한다.
    tab === 'jobs'
  const t = TAB_SEO[tab === 'freelance' && detail === 'rates' ? 'freelanceRates' : tab] ?? TAB_SEO.jobs
  useSeo(own ? null : { title: t.title, description: t.desc, canonical: absUrl(route.path) })
}

export function RouteView() {
  const route = useRoute()
  const tab = tabOf(route)
  const detail = route.seg[1] ?? null
  useLegacyRedirects(route)
  useTabSeo(route, tab)

  switch (tab) {
    case 'companies':
      return <CompaniesPage slug={detail} />
    case 'blog':
    case 'radar':
      return <BlogPage mode={tab} detail={detail} />
    case 'calendar':
      return <CalendarPage />
    case 'reposts':
      return <RepostsPage />
    case 'freelance':
      return <FreelancePage sub={detail} />
    case 'trend':
      return <TrendPage focusTech={route.query.get('tech')} />
    case 'book':
      return <BookPage seg={route.seg.slice(1)} />
    case 'reveng':
      return <RevengPage seg={route.seg.slice(1)} />
    case 'hardware':
      return <HardwarePage seg={route.seg.slice(1)} />
    case 'mindmap':
      return <MindmapPage />
    case 'jobs':
      return <JobsPage />
  }
}
