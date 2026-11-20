import { useEffect } from 'react'
import { AlbaPage } from '../pages/alba/AlbaPage'
import { BlogPage } from '../pages/blog/BlogPage'
import { BookPage } from '../pages/book/BookPage'
import { CalendarPage } from '../pages/calendar/CalendarPage'
import { CareersPage } from '../pages/careers/CareersPage'
import { CompaniesPage } from '../pages/companies/CompaniesPage'
import { FreelancePage } from '../pages/freelance/FreelancePage'
import { HomePage } from '../pages/home/HomePage'
import { HardwarePage } from '../pages/hardware/HardwarePage'
import { JobsPage } from '../pages/jobs/JobsPage'
import { MindmapPage } from '../pages/mindmap/MindmapPage'
import { RepostsPage } from '../pages/reposts/RepostsPage'
import { RevengPage } from '../pages/reveng/RevengPage'
import { LecturesPage } from '../pages/lectures/LecturesPage'
import { TopPage } from '../pages/top/TopPage'
import { TrendPage } from '../pages/trend/TrendPage'
import { navigate, useRoute, type Route } from '../utils/navigation'
import { useSeo, absUrl } from '../utils/seo'
import { paths, TAB_SEO } from '../utils/urls'

/** 페이지 경로 설정 — 경로 첫 세그먼트 → 탭 → 페이지. 루트(`/`)는 회사별 메인, `/jobs` 가 잡 리스트다. */
export type Tab =
  | 'home' | 'jobs' | 'companies' | 'mindmap' | 'blog' | 'radar' | 'calendar' | 'trend'
  | 'book' | 'careers' | 'reveng' | 'lectures' | 'reposts' | 'freelance' | 'alba' | 'hardware' | 'top'

const TAB_BY_SEG: Record<string, Tab> = {
  '': 'home',
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
  // 학습 › 취업후기 — 합격·이직 후기(정본 DB career_*)
  careers: 'careers',
  reveng: 'reveng',
  lectures: 'lectures',
  reposts: 'reposts',
  freelance: 'freelance',
  alba: 'alba',
  hardware: 'hardware',
  // 메인 배너 한 장이 여는 구역 TOP 50 — `/top/entry`
  top: 'top',
}

export function tabOf(route: Route): Tab {
  return TAB_BY_SEG[route.seg[0] ?? ''] ?? 'home'
}

/**
 * 옛 주소를 새 주소로 넘긴다. `/jobs` 와 `/` 는 같은 화면이라 목록의 주소는 `/` 하나로
 * 모은다(주소 두 개로 색인되면 서로의 순위를 갉아먹는다). 경로에 쓰던 한글 낱말
 * (`/reveng/문서/...`)은 영어로 바꿨다 — 이미 나간 링크는 새 주소로 넘긴다.
 */
function useLegacyRedirects(route: Route) {
  useEffect(() => {
    if (route.seg[0] === 'reveng' && route.seg[1] === '문서') {
      navigate(route.seg[2] ? paths.revengDoc(route.seg[2]) : paths.reveng(), { replace: true })
    }
    // 취업후기는 처음에 책장 안(`/wiki/careers`)에 있었다 — 메뉴로 올라가며 `/careers` 로 옮겼다.
    if (route.seg[0] === 'wiki' && route.seg[1] === 'careers') {
      navigate(route.seg[2] ? paths.careersStory(route.seg[2]) : paths.careers() + window.location.search, { replace: true })
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
    (!!detail && (tab === 'companies' || tab === 'radar' || tab === 'reveng' || tab === 'lectures' || tab === 'blog')) ||
    tab === 'book' ||
    // 취업후기는 혼자 보는 화면이라 CareersView 가 noindex 를 단다.
    tab === 'careers' ||
    tab === 'hardware' ||
    tab === 'home' ||
    // 구역 TOP 50 은 구역 이름이 제목에 들어간다 — TopBoard 가 단다.
    tab === 'top' ||
    // 외주 프로젝트 한 건은 상세 화면이 제 제목·noindex 를 단다(남의 글을 옮긴 화면이다).
    (tab === 'freelance' && !!detail && detail !== 'rates') ||
    // 당근알바 IT 공고는 남의 목록을 다시 보여 주는 화면이라 AlbaView 가 noindex 를 단다.
    tab === 'alba' ||
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
    case 'alba':
      return <AlbaPage />
    case 'trend':
      return <TrendPage focusTech={route.query.get('tech')} />
    case 'book':
      return <BookPage seg={route.seg.slice(1)} />
    case 'careers':
      return <CareersPage seg={route.seg.slice(1)} />
    case 'reveng':
      return <RevengPage seg={route.seg.slice(1)} />
    case 'lectures':
      return <LecturesPage seg={route.seg.slice(1)} />
    case 'hardware':
      return <HardwarePage seg={route.seg.slice(1)} />
    case 'mindmap':
      return <MindmapPage />
    case 'jobs':
      return <JobsPage />
    case 'top':
      return <TopPage sectionKey={detail} />
    case 'home':
      return <HomePage />
  }
}
