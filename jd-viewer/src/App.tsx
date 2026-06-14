import { useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { JobList } from './components/JobList'
import { JobDetail } from './components/JobDetail'
import { TechChart } from './components/TechChart'
import { CareerMap } from './components/CareerMap'
import { CompanyView } from './components/CompanyView'
import { ExpansionView } from './components/ExpansionView'
import { BlogView } from './components/BlogView'
import { RadarView } from './components/RadarView'
import { CalendarView } from './components/CalendarView'
import { Loader, ErrorState } from './components/ui'
import { useJobs } from './lib/useJobs'
import { useHashTab } from './lib/useHashTab'
import { applyFilter, emptyFilter, stackCounts } from './lib/filter'
import type { Job } from './types'

type Tab = 'jobs' | 'companies' | 'expansion' | 'mindmap' | 'blog' | 'radar' | 'calendar'

const TABS: readonly Tab[] = ['jobs', 'companies', 'expansion', 'mindmap', 'blog', 'radar', 'calendar']

function App() {
  const { jobs, loading, error } = useJobs()
  const [filter, setFilter] = useState(emptyFilter)
  const [selected, setSelected] = useState<Job | null>(null)
  const [tab, setTab] = useHashTab(TABS, 'jobs')
  const [companyFocus, setCompanyFocus] = useState<string | null>(null)
  const [techFocus, setTechFocus] = useState<{ tech: string; n: number } | null>(null)

  const openCompany = (norm: string) => {
    setCompanyFocus(norm)
    setTab('companies')
  }

  // 회사 → "이 기술 공부하기": 기술스택 확장 탭으로 이동해 해당 기술 선택.
  // n 카운터로 같은 기술을 다시 눌러도 useEffect 가 재실행되게 한다.
  const openStudy = (tech: string) => {
    setTechFocus((prev) => ({ tech, n: (prev?.n ?? 0) + 1 }))
    setTab('expansion')
  }

  const filtered = useMemo(() => applyFilter(jobs, filter), [jobs, filter])
  const stacks = useMemo(() => stackCounts(filtered), [filtered])
  const allStacks = useMemo(() => stackCounts(jobs), [jobs])

  const toggleStack = (name: string) => {
    const next = new Set(filter.stacks)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setFilter({ ...filter, stacks: next })
  }

  return (
    <div className="flex flex-col h-screen">
      <nav className="flex items-center gap-2 px-3 sm:px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/95 backdrop-blur supports-[backdrop-filter]:bg-(--color-panel)/80 sticky top-0 z-30">
        <span className="hidden md:flex items-center gap-2 shrink-0 mr-1 select-none">
          <span className="h-5 w-5 rounded bg-(--color-accent)/20 border border-(--color-accent)/40 flex items-center justify-center text-(--color-accent) text-[11px] font-bold">
            JD
          </span>
          <span className="text-sm font-semibold text-white tracking-tight">Viewer</span>
        </span>
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar -mx-1 px-1">
          <TabButton active={tab === 'jobs'} onClick={() => setTab('jobs')}>
            잡 리스트
          </TabButton>
          <TabButton active={tab === 'companies'} onClick={() => setTab('companies')}>
            기업 기술스택
          </TabButton>
          <TabButton active={tab === 'expansion'} onClick={() => setTab('expansion')}>
            기술스택 확장
          </TabButton>
          <TabButton active={tab === 'mindmap'} onClick={() => setTab('mindmap')}>
            커리어 마인드맵
          </TabButton>
          <TabButton active={tab === 'blog'} onClick={() => setTab('blog')}>
            기술 블로그
          </TabButton>
          <TabButton active={tab === 'radar'} onClick={() => setTab('radar')}>
            기술 스택 레이더
          </TabButton>
          <TabButton active={tab === 'calendar'} onClick={() => setTab('calendar')}>
            모집 캘린더
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
        <div key="companies" className="flex flex-1 min-h-0 jd-fade-in">
          <CompanyView focusNorm={companyFocus} onStudyTech={openStudy} />
        </div>
      ) : tab === 'expansion' ? (
        <div key="expansion" className="flex flex-1 min-h-0 jd-fade-in">
          <ExpansionView onOpenCompany={openCompany} focusTech={techFocus} />
        </div>
      ) : tab === 'blog' ? (
        <div key="blog" className="flex flex-1 min-h-0 jd-fade-in">
          <BlogView />
        </div>
      ) : tab === 'radar' ? (
        <div key="radar" className="flex flex-1 min-h-0 jd-fade-in">
          <RadarView />
        </div>
      ) : tab === 'calendar' ? (
        <div key="calendar" className="flex flex-1 min-h-0 jd-fade-in">
          <CalendarView />
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
          <div className="flex flex-1 min-h-0 jd-fade-in">
            <Sidebar
              filter={filter}
              setFilter={setFilter}
              topStacks={allStacks}
              totalCount={jobs.length}
              filteredCount={filtered.length}
            />
            <main className="flex-1 min-w-0 overflow-auto">
              <TechChart data={stacks} onPick={toggleStack} highlight={filter.stacks} />
              <JobList jobs={filtered} selected={selected} onSelect={setSelected} />
            </main>
            {selected && <JobDetail job={selected} onClose={() => setSelected(null)} />}
          </div>
        )
      ) : (
        <div key="mindmap" className="flex flex-1 min-h-0 relative jd-fade-in">
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
      className={`px-4 py-1.5 text-sm rounded transition ${
        active
          ? 'bg-(--color-accent) text-black font-medium'
          : 'text-(--color-text) hover:bg-(--color-bg) border border-transparent hover:border-(--color-border)'
      }`}
    >
      {children}
    </button>
  )
}

export default App
