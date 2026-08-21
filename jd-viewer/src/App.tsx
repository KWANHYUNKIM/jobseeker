import { useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { JobList } from './components/JobList'
import { JobDetail } from './components/JobDetail'
import { CareerMap } from './components/CareerMap'
import { CompanyView } from './components/CompanyView'
import { BlogView } from './components/BlogView'
import { RadarView } from './components/RadarView'
import { RepostView } from './components/RepostView'
import { CalendarView } from './components/CalendarView'
import { TrendView } from './components/TrendView'
import { RevengView } from './components/RevengView'
import { Loader, ErrorState, MobileBar } from './components/ui'
import { useJobs } from './lib/useJobs'
import { useHashTab } from './lib/useHashTab'
import { useHybridSearch, useSearchAvailable } from './lib/useHybridSearch'
import { applyFilter, emptyFilter, stackCounts, roleCounts } from './lib/filter'
import type { Job } from './types'

type Tab = 'jobs' | 'companies' | 'mindmap' | 'blog' | 'radar' | 'calendar' | 'trend' | 'reveng' | 'reposts'

const TABS: readonly Tab[] = ['jobs', 'companies', 'mindmap', 'blog', 'radar', 'calendar', 'trend', 'reveng', 'reposts']

function App() {
  const { jobs, loading, error } = useJobs()
  const [filter, setFilter] = useState(emptyFilter)
  const [selected, setSelected] = useState<Job | null>(null)
  const [tab, setTab] = useHashTab(TABS, 'jobs')
  const [companyFocus, setCompanyFocus] = useState<string | null>(null)
  const [techFocus, setTechFocus] = useState<{ tech: string; n: number } | null>(null)
  const [filterOpen, setFilterOpen] = useState(false)
  // 검색 API 가 있으면 의미 검색을 기본으로 쓴다. 키워드 필터는 사전에 있는 단어가
  // 정확히 나와야만 잡아서, 문장으로 물으면 대개 0건이 된다 — 그게 기본값일 이유가 없다.
  // 끄면 기존 로컬 필터로 돌아간다(API 가 없으면 토글 자체가 안 보인다).
  const [semantic, setSemantic] = useState(true)
  // 추천 목록에서 고른 공고로 모달을 갈아끼운다. 추천 JSON 은 url 만 들고 있어서
  // 실제 Job 객체는 여기서 찾는다(필터에 걸려 목록에 없는 공고도 열려야 하므로 jobs 전체 대상).
  const openJobByUrl = (url: string) => {
    const next = jobs.find((j) => j.url === url)
    if (next) setSelected(next)
  }

  const openCompany = (norm: string) => {
    setCompanyFocus(norm)
    setTab('companies')
  }

  // 회사 → "이 기술 공부하기": 개발 트렌드 탭의 학습·확장 모드로 이동해 해당 기술 선택.
  // n 카운터로 같은 기술을 다시 눌러도 useEffect 가 재실행되게 한다.
  const openStudy = (tech: string) => {
    setTechFocus((prev) => ({ tech, n: (prev?.n ?? 0) + 1 }))
    setTab('trend')
  }

  const searchAvailable = useSearchAvailable()
  const semanticOn = semantic && searchAvailable
  const { hits, loading: searching, engines } = useHybridSearch(filter.query, semanticOn, filter)

  const localFiltered = useMemo(() => applyFilter(jobs, filter), [jobs, filter])

  // 의미 검색이 돌 때는 API 가 매긴 관련도 순서가 결과의 핵심이라 그대로 따른다.
  // API 는 url 만 돌려주므로 여기서 실제 Job 으로 되돌린다.
  const filtered = useMemo(() => {
    if (!hits) return localFiltered
    const byUrl = new Map(jobs.map((j) => [j.url, j]))
    return hits.map((h) => byUrl.get(h.url)).filter((j): j is Job => Boolean(j))
  }, [hits, localFiltered, jobs])
  const allStacks = useMemo(() => stackCounts(jobs), [jobs])
  const allRoles = useMemo(() => roleCounts(jobs), [jobs])

  return (
    <div className="flex flex-col h-screen">
      <nav className="flex items-center gap-3 px-4 sm:px-6 h-14 border-b border-(--color-border) bg-(--color-panel) sticky top-0 z-30">
        <span className="hidden md:flex items-baseline gap-1.5 shrink-0 mr-3 select-none">
          <span className="text-lg font-extrabold text-(--color-accent) tracking-tight">JD</span>
          <span className="text-lg font-bold text-(--color-text) tracking-tight">Viewer</span>
        </span>
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar -mx-1 px-1">
          <TabButton active={tab === 'jobs'} onClick={() => setTab('jobs')}>
            잡 리스트
          </TabButton>
          <TabButton active={tab === 'companies'} onClick={() => setTab('companies')}>
            기업 기술스택
          </TabButton>
          <TabButton active={tab === 'mindmap'} onClick={() => setTab('mindmap')}>
            커리어 마인드맵
          </TabButton>
          <TabButton active={tab === 'blog' || tab === 'radar'} onClick={() => setTab('blog')}>
            기술 블로그
          </TabButton>
          <TabButton active={tab === 'calendar'} onClick={() => setTab('calendar')}>
            모집 캘린더
          </TabButton>
          <TabButton active={tab === 'reposts'} onClick={() => setTab('reposts')}>
            재공고
          </TabButton>
          <TabButton active={tab === 'trend'} onClick={() => setTab('trend')}>
            개발 트렌드
          </TabButton>
          <TabButton active={tab === 'reveng'} onClick={() => setTab('reveng')}>
            기술 역설계
          </TabButton>
        </div>
        <span className="ml-auto shrink-0 text-xs text-(--color-muted) tabular-nums whitespace-nowrap">
          <span className="text-(--color-text) font-medium">{jobs.length.toLocaleString()}</span>건
          <span className="hidden sm:inline"> · 필터 </span>
          <span className="hidden sm:inline text-(--color-accent) font-medium">{filtered.length.toLocaleString()}</span>
          <span className="hidden sm:inline">건</span>
        </span>
      </nav>

      {tab === 'companies' ? (
        <div key="companies" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <CompanyView focusNorm={companyFocus} onStudyTech={openStudy} />
        </div>
      ) : tab === 'blog' || tab === 'radar' ? (
        <div key="blogradar" className="flex flex-col flex-1 min-h-0 jd-fade-in jd-canvas">
          <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60">
            <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden shrink-0">
              <ModeBtn active={tab === 'blog'} onClick={() => setTab('blog')}>블로그 글</ModeBtn>
              <ModeBtn active={tab === 'radar'} onClick={() => setTab('radar')}>기업 100 (레이더)</ModeBtn>
            </div>
            <span className="hidden sm:inline text-xs text-(--color-muted) truncate">
              {tab === 'blog' ? '기업 기술 블로그 글 모음' : '글로벌 IT 대기업 100곳의 기술 스택·아키텍처·토론·전형'}
            </span>
          </div>
          {tab === 'blog' ? <BlogView /> : <RadarView />}
        </div>
      ) : tab === 'calendar' ? (
        <div key="calendar" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <CalendarView />
        </div>
      ) : tab === 'reposts' ? (
        <RepostView />
      ) : tab === 'trend' ? (
        <div key="trend" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <TrendView onOpenCompany={openCompany} focusTech={techFocus} />
        </div>
      ) : tab === 'reveng' ? (
        <div key="reveng" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
          <RevengView />
        </div>
      ) : tab === 'jobs' ? (
        loading ? (
          <Loader label="채용 데이터 불러오는 중…" />
        ) : error ? (
          <ErrorState
            title="데이터를 불러오지 못했습니다"
            detail={error}
            hint={<>public/all_jobs_enriched.json 이 있는지 확인하세요.</>}
          />
        ) : (
          <div className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
            <Sidebar
              filter={filter}
              setFilter={setFilter}
              topStacks={allStacks}
              roleCounts={allRoles}
              totalCount={jobs.length}
              filteredCount={filtered.length}
              open={filterOpen}
              onClose={() => setFilterOpen(false)}
              semantic={
                searchAvailable
                  ? { on: semantic, setOn: setSemantic, loading: searching, engines }
                  : undefined
              }
            />
            <main className="flex-1 min-w-0 overflow-auto jd-panel">
              <MobileBar onMenu={() => setFilterOpen(true)} label="필터">
                <span className="ml-auto text-xs text-(--color-muted) tabular-nums">
                  {filtered.length.toLocaleString()}건
                </span>
              </MobileBar>
              <JobList jobs={filtered} selected={selected} onSelect={setSelected} />
            </main>
            {selected && (
              <JobDetail
                job={selected}
                onClose={() => setSelected(null)}
                onOpenUrl={openJobByUrl}
              />
            )}
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

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`relative px-3 py-2 text-[15px] transition whitespace-nowrap shrink-0 after:absolute after:left-3 after:right-3 after:-bottom-px after:h-0.5 ${
        active
          ? 'text-(--color-accent) font-bold after:bg-(--color-accent)'
          : 'text-(--color-muted) hover:text-(--color-text) after:bg-transparent'
      }`}
    >
      {children}
    </button>
  )
}

function ModeBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs font-medium transition whitespace-nowrap ${
        active ? 'bg-(--color-accent) text-(--color-on-accent)' : 'bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {children}
    </button>
  )
}

export default App
