import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { JobList } from './components/JobList'
import { JobDetail } from './components/JobDetail'
import { CareerMap } from './components/CareerMap'
import { CompanyView } from './components/CompanyView'
import { BlogView } from './components/BlogView'
import { RadarView } from './components/RadarView'
import { RepostView } from './components/RepostView'
import { FreelanceView } from './components/FreelanceView'
import { FreelanceRatesView } from './components/FreelanceRatesView'
import { CalendarView } from './components/CalendarView'
import { TrendView } from './components/TrendView'
import { RevengView } from './components/RevengView'
import { HardwareView } from './components/HardwareView'
import { BookView } from './components/BookView'
import { Loader, ErrorState, MobileBar } from './components/ui'
import { useJobs } from './lib/useJobs'
import { navigate, onLinkClick, useRoute, useSetQuery } from './lib/router'
import { useSeo } from './lib/seo'
import { breadcrumbJsonLd, jobDescription, jobJsonLd, jobKey, jobTitle, paths, TAB_SEO } from './lib/urls'
import { absUrl, SITE_NAME } from './lib/seo'
import { useHybridSearch, useSearchAvailable } from './lib/useHybridSearch'
import { applyFilter, applyLocalFacets, computeFacets, emptyFilter } from './lib/filter'
import { EMPTY_FACETS, lookupJobKey, useJob, useJobPage, useJobsApiAvailable } from './lib/useJobsApi'
import type { Job } from './types'

type Tab = 'jobs' | 'companies' | 'mindmap' | 'blog' | 'radar' | 'calendar' | 'trend' | 'book' | 'reveng' | 'reposts' | 'freelance' | 'hardware'

// 경로 첫 세그먼트 → 탭. 루트(`/`)는 잡 리스트다.
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

function App() {
  // 공고 API(store.api)가 있으면 목록·칩 건수·상세를 DB 에서 받는다. 없는 배포에서만
  // 예전처럼 공고 전량 파일(184MB)을 받아 화면에서 거른다.
  const api = useJobsApiAvailable()
  const apiMode = api === 'yes'
  const { jobs, loading: fileLoading, error: fileError } = useJobs(api === 'no')
  const route = useRoute()
  const setQueryParam = useSetQuery()
  const tab: Tab = TAB_BY_SEG[route.seg[0] ?? ''] ?? 'jobs'
  // 상세 화면 식별자 — 탭마다 두 번째 세그먼트가 무엇인지가 다르다.
  const detail = route.seg[1] ?? null

  // 검색어는 주소에 담아 공유·새로고침에 살아남게 한다. 다만 타이핑마다 히스토리를
  // 쌓으면 뒤로가기가 글자 수만큼 눌러야 하는 물건이 되므로 replace 로만 갱신한다.
  const [filter, setFilter] = useState(() => ({
    ...emptyFilter(),
    query: new URLSearchParams(window.location.search).get('q') ?? '',
  }))
  const [filterOpen, setFilterOpen] = useState(false)
  // 검색 API 가 있으면 의미 검색을 기본으로 쓴다. 키워드 필터는 사전에 있는 단어가
  // 정확히 나와야만 잡아서, 문장으로 물으면 대개 0건이 된다 — 그게 기본값일 이유가 없다.
  // 끄면 기존 로컬 필터로 돌아간다(API 가 없으면 토글 자체가 안 보인다).
  const [semantic, setSemantic] = useState(true)

  // `/jobs` 와 `/` 는 같은 화면이다. 같은 내용이 주소 두 개로 색인되면 서로의 순위를
  // 갉아먹으므로 목록의 주소는 `/` 하나로 모은다.
  // 경로에 쓰던 한글 낱말(`/reveng/문서/...`)은 영어로 바꿨다 — 퍼센트 인코딩된 주소는
  // 공유·로그·검색결과 어디서도 읽히지 않는다. 이미 나간 링크는 새 주소로 넘긴다.
  useEffect(() => {
    if (route.path === '/jobs') navigate(paths.jobs(), { replace: true })
    else if (route.seg[0] === 'reveng' && route.seg[1] === '문서') {
      navigate(route.seg[2] ? paths.revengDoc(route.seg[2]) : paths.reveng(), { replace: true })
    }
  }, [route.path, route.seg])

  const isJobList = tab === 'jobs' && !detail
  useEffect(() => {
    if (!isJobList) return
    setQueryParam('q', filter.query || null)
  }, [filter.query, isJobList, setQueryParam])

  // 선택된 공고는 상태가 아니라 주소에서 나온다 — 뒤로가기·새로고침·링크 공유가
  // 전부 같은 경로 하나로 해결된다.
  const selectedLocal = useMemo(
    () => (!apiMode && tab === 'jobs' && detail ? (jobs.find((j) => jobKey(j) === detail) ?? null) : null),
    [apiMode, jobs, tab, detail],
  )
  const remoteJob = useJob(tab === 'jobs' ? detail : null, apiMode)
  const selected = apiMode ? remoteJob.job : selectedLocal

  // 추천 목록은 url 만 들고 있어서 실제 Job 을 여기서 찾는다(필터에 걸려 목록에
  // 없는 공고도 열려야 하므로 jobs 전체 대상). API 모드에서는 서버에 주소 키를 묻는다.
  const openJobByUrl = (url: string) => {
    if (apiMode) {
      void lookupJobKey(url).then((key) => key && navigate(`/jobs/${key}`))
      return
    }
    const next = jobs.find((j) => j.url === url)
    if (next) navigate(paths.job(next))
  }

  const searchAvailable = useSearchAvailable()
  const semanticOn = semantic && searchAvailable
  // 목록·칩 건수는 1만 7천 건을 다시 훑는 일이라 입력 칸과 같은 렌더에 두면 글자가
  // 늦게 찍힌다. 입력 칸은 filter 로 바로 그리고, 무거운 계산은 한 박자 늦은 사본으로
  // 한다 — 빠르게 치는 동안의 중간 값은 React 가 건너뛴다.
  const view = useDeferredValue(filter)
  // API 모드에서는 의미 검색도 /api/jobs 가 한다(후보를 뽑은 뒤 모든 필터 축을 서버가 건다).
  const { hits, loading: searching, engines } = useHybridSearch(view.query, semanticOn && !apiMode, view)

  // API 모드의 쪽 번호. 필터가 바뀌면 1쪽으로 — usePaged 와 같은 '렌더 중 조정' 패턴.
  const [apiPage, setApiPage] = useState(0)
  const [pagedFor, setPagedFor] = useState(view)
  if (pagedFor !== view) {
    setPagedFor(view)
    setApiPage(0)
  }
  // 목록 탭이 아니어도 받는다 — 헤더의 전체·필터 건수가 이 응답에서 온다(한 쪽 20건,
  // gzip 8KB 남짓. 예전에는 어느 탭에서든 184MB 를 받았다).
  const remote = useJobPage(view, semanticOn, apiPage, apiMode)

  const localFiltered = useMemo(() => (apiMode ? [] : applyFilter(jobs, view)), [apiMode, jobs, view])

  // 의미 검색이 돌 때는 API 가 매긴 관련도 순서가 결과의 핵심이라 그대로 따른다.
  // API 는 url 만 돌려주므로 여기서 실제 Job 으로 되돌린다.
  const filtered = useMemo(() => {
    if (apiMode) return remote.items
    if (!hits) return localFiltered
    const byUrl = new Map(jobs.map((j) => [j.url, j]))
    const found = hits.map((h) => byUrl.get(h.url)).filter((j): j is Job => Boolean(j))
    // 지역·규모는 API 가 모르는 축이라 여기서 한 번 더 건다(순서는 그대로 둔다).
    return applyLocalFacets(found, view)
  }, [apiMode, remote.items, hits, localFiltered, jobs, view])
  // 칩 건수는 필터를 타야 한다. 예전에는 jobs 전체로 셌더니, 목록은 '모집중만'
  // 3천 건인데 사이드바는 마감까지 합친 1만 건을 말하고 있었다.
  const localFacets = useMemo(() => (apiMode ? EMPTY_FACETS : computeFacets(jobs, view)), [apiMode, jobs, view])
  const facets = apiMode ? remote.facets : localFacets
  // 헤더·사이드바의 건수. API 모드에서는 목록이 한 쪽뿐이라 서버가 센 값을 쓴다.
  const totalCount = apiMode ? remote.allTotal : jobs.length
  const filteredCount = apiMode ? remote.total : filtered.length
  const loading = api === 'unknown' || (apiMode ? remote.loading && remote.allTotal === 0 && !detail : fileLoading)
  const error = apiMode ? remote.error : fileError
  const countsReady = apiMode ? remote.allTotal > 0 : !fileLoading

  // 공고 상세는 공고별 제목·설명·JobPosting 구조화 데이터를 쓰고, 그 외 탭은
  // 탭 문구를 쓴다. 검색어가 걸린 목록은 색인하지 않는다(같은 목록의 무한 변형이라
  // 색인해봐야 중복 페이지만 늘어난다).
  const seo = useMemo(() => {
    if (selected) {
      const url = absUrl(paths.job(selected))
      return {
        title: jobTitle(selected),
        description: jobDescription(selected),
        canonical: url,
        jsonLd: {
          '@context': 'https://schema.org',
          '@graph': [
            jobJsonLd(selected, url),
            breadcrumbJsonLd([
              { name: SITE_NAME, url: absUrl('/') },
              { name: selected.company, url },
            ]),
          ],
        },
      }
    }
    // 회사·레이더·역설계·블로그 상세의 제목은 그 데이터를 들고 있는 뷰가 직접 단다.
    // 여기서 탭 제목을 달면 모든 회사 페이지가 "기업 기술스택 분석" 한 줄로 색인된다.
    if (detail && (tab === 'companies' || tab === 'radar' || tab === 'reveng' || tab === 'blog')) return null
    // 책은 제목도 noindex 도 BookView 가 직접 단다(책·절 데이터를 그쪽이 들고 있다).
    if (tab === 'book') return null
    // 부품 화면은 하위 화면(조립·비교·가격)마다 제목과 noindex 를 HardwareView 가 직접 단다.
    if (tab === 'hardware') return null

    const t = TAB_SEO[tab === 'freelance' && detail === 'rates' ? 'freelanceRates' : tab] ?? TAB_SEO.jobs
    return {
      title: t.title,
      description: t.desc,
      canonical: absUrl(route.path === '/jobs' ? '/' : route.path),
      // 검색어가 걸린 목록은 같은 목록의 무한 변형이라 색인해봐야 중복 페이지만 는다.
      robots: filter.query && isJobList ? 'noindex, follow' : undefined,
    }
  }, [selected, tab, detail, route.path, filter.query, isJobList])
  useSeo(seo)

  return (
    <div className="flex flex-col h-screen">
      <nav className="flex items-center gap-3 px-4 sm:px-6 h-14 border-b border-(--color-border) bg-(--color-panel) sticky top-0 z-30">
        <a href="/" onClick={onLinkClick('/')} className="hidden md:flex items-baseline gap-1.5 shrink-0 mr-3 select-none">
          <span className="text-lg font-extrabold text-(--color-accent) tracking-tight">JD</span>
          <span className="text-lg font-bold text-(--color-text) tracking-tight">Viewer</span>
        </a>
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar -mx-1 px-1">
          <TabLink active={tab === 'jobs'} to={paths.jobs()}>
            잡 리스트
          </TabLink>
          <TabLink active={tab === 'companies'} to={paths.companies()}>
            기업 기술스택
          </TabLink>
          <TabLink active={tab === 'mindmap'} to={paths.mindmap()}>
            커리어 마인드맵
          </TabLink>
          <TabLink active={tab === 'blog' || tab === 'radar'} to={paths.blog()}>
            기술 블로그
          </TabLink>
          <TabLink active={tab === 'calendar'} to={paths.calendar()}>
            모집 캘린더
          </TabLink>
          <TabLink active={tab === 'reposts'} to={paths.reposts()}>
            재공고
          </TabLink>
          <TabLink active={tab === 'freelance'} to={paths.freelance()}>
            외주·프리
          </TabLink>
          <TabLink active={tab === 'trend'} to={paths.trend()}>
            개발 트렌드
          </TabLink>
          <TabLink active={tab === 'book'} to={paths.wiki()}>
            기술도서
          </TabLink>
          <TabLink active={tab === 'reveng'} to={paths.reveng()}>
            기술 역설계
          </TabLink>
          <TabLink active={tab === 'hardware'} to={paths.hardware()}>
            PC 하드웨어
          </TabLink>
        </div>
        <span className="ml-auto shrink-0 text-xs text-(--color-muted) tabular-nums whitespace-nowrap">
          {/* 첫 응답 전에는 0 이 아니라 '…' — 0건은 "공고가 없다" 로 읽힌다. */}
          <span className="text-(--color-text) font-medium">{countsReady ? totalCount.toLocaleString() : '…'}</span>건
          <span className="hidden sm:inline"> · 필터 </span>
          <span className="hidden sm:inline text-(--color-accent) font-medium">{countsReady ? filteredCount.toLocaleString() : '…'}</span>
          <span className="hidden sm:inline">건</span>
        </span>
      </nav>

      {tab === 'companies' ? (
        <div key="companies" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <CompanyView
            selectedSlug={detail}
            onSelectCompany={(slug) => navigate(paths.company(slug))}
            onStudyTech={(tech) => navigate(paths.trend(tech))}
          />
        </div>
      ) : tab === 'blog' || tab === 'radar' ? (
        <div key="blogradar" className="flex flex-col flex-1 min-h-0 jd-fade-in jd-canvas">
          <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60">
            <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden shrink-0">
              <ModeLink active={tab === 'blog'} to={paths.blog()}>블로그 글</ModeLink>
              <ModeLink active={tab === 'radar'} to={paths.radar()}>기업 100 (레이더)</ModeLink>
            </div>
            <span className="hidden sm:inline text-xs text-(--color-muted) truncate">
              {tab === 'blog' ? '기업 기술 블로그 글 모음' : '글로벌 IT 대기업 100곳의 기술 스택·아키텍처·토론·전형'}
            </span>
          </div>
          {tab === 'blog' ? <BlogView postId={detail} /> : <RadarView companyKey={detail} />}
        </div>
      ) : tab === 'calendar' ? (
        <div key="calendar" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <CalendarView />
        </div>
      ) : tab === 'reposts' ? (
        <RepostView />
      ) : tab === 'freelance' ? (
        // 단가 분석은 목록 위에 얹지 않고 따로 뺀다(/freelance/rates).
        detail === 'rates' ? <FreelanceRatesView /> : <FreelanceView />
      ) : tab === 'trend' ? (
        <div key="trend" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <TrendView onOpenCompany={(slug) => navigate(paths.company(slug))} focusTech={route.query.get('tech')} />
        </div>
      ) : tab === 'book' ? (
        <div key="book" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <BookView seg={route.seg.slice(1)} />
        </div>
      ) : tab === 'reveng' ? (
        <div key="reveng" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <RevengView seg={route.seg.slice(1)} />
        </div>
      ) : tab === 'hardware' ? (
        <div key="hardware" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <HardwareView seg={route.seg.slice(1)} />
        </div>
      ) : tab === 'jobs' ? (
        loading ? (
          <Loader label="채용 데이터 불러오는 중…" />
        ) : error ? (
          <ErrorState
            title="데이터를 불러오지 못했습니다"
            detail={error}
            hint={
              apiMode ? (
                <>공고 API(/api/jobs)와 정본 DB 가 떠 있는지 확인하세요.</>
              ) : (
                <>public/all_jobs_enriched.json 이 있는지 확인하세요.</>
              )
            }
          />
        ) : apiMode && detail && remoteJob.loading ? (
          <Loader label="공고 불러오는 중…" />
        ) : selected ? (
          // 공고를 고르면 목록을 통째로 갈아끼운다. 모달로 띄우면 오른쪽 취업 가이드가
          // 들어갈 폭이 안 나오고, 좁은 칸에 겹쳐 둔 JD 와 가이드는 둘 다 안 읽힌다.
          <div key="jobdetail" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
            <JobDetail key={selected.url} job={selected} onOpenUrl={openJobByUrl} />
          </div>
        ) : detail ? (
          // 주소에는 공고 id 가 있는데 데이터에 없다 — 마감돼 걷힌 공고이거나 오래된 링크.
          <ErrorState
            title="없는 공고입니다"
            detail={`공고 ${detail} 을(를) 찾지 못했습니다.`}
            hint={<a href="/" onClick={onLinkClick('/')} className="text-(--color-accent) underline">전체 공고 목록으로</a>}
          />
        ) : (
          <div className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
            <Sidebar
              filter={filter}
              setFilter={setFilter}
              facets={facets}
              totalCount={totalCount}
              filteredCount={filteredCount}
              open={filterOpen}
              onClose={() => setFilterOpen(false)}
              semantic={
                searchAvailable
                  ? {
                      on: semantic,
                      setOn: setSemantic,
                      loading: apiMode ? remote.loading : searching,
                      engines: apiMode ? remote.engines : engines,
                    }
                  : undefined
              }
            />
            <main data-scroll className="flex-1 min-w-0 overflow-auto jd-panel">
              <MobileBar onMenu={() => setFilterOpen(true)} label="필터">
                <span className="ml-auto text-xs text-(--color-muted) tabular-nums">
                  {filteredCount.toLocaleString()}건
                </span>
              </MobileBar>
              <JobList
                jobs={filtered}
                server={apiMode ? { page: apiPage, total: remote.total, onChange: setApiPage } : undefined}
              />
            </main>
          </div>
        )
      ) : (
        <div key="mindmap" className="flex flex-1 min-h-0 relative jd-fade-in jd-canvas">
          <CareerMap />
        </div>
      )}
    </div>
  )
}

// 탭은 진짜 링크다. 크롤러는 onClick 을 따라가지 않는다 — href 가 있어야 다음 페이지를 본다.
function TabLink({ active, to, children }: { active: boolean; to: string; children: React.ReactNode }) {
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

function ModeLink({ active, to, children }: { active: boolean; to: string; children: React.ReactNode }) {
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

export default App
