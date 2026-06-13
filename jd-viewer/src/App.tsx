import { useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { JobList } from './components/JobList'
import { JobDetail } from './components/JobDetail'
import { TechChart } from './components/TechChart'
import { CareerMap } from './components/CareerMap'
import { CompanyView } from './components/CompanyView'
import { ExpansionView } from './components/ExpansionView'
import { BlogView } from './components/BlogView'
import { useJobs } from './lib/useJobs'
import { applyFilter, emptyFilter, stackCounts } from './lib/filter'
import type { Job } from './types'

type Tab = 'jobs' | 'companies' | 'expansion' | 'mindmap' | 'blog'

function App() {
  const { jobs, loading, error } = useJobs()
  const [filter, setFilter] = useState(emptyFilter)
  const [selected, setSelected] = useState<Job | null>(null)
  const [tab, setTab] = useState<Tab>('jobs')
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
      <nav className="flex items-center gap-1 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)">
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
        <span className="ml-auto text-xs text-(--color-muted)">
          {jobs.length}건 / 필터 {filtered.length}건
        </span>
      </nav>

      {tab === 'companies' ? (
        <div className="flex flex-1 min-h-0">
          <CompanyView focusNorm={companyFocus} onStudyTech={openStudy} />
        </div>
      ) : tab === 'expansion' ? (
        <div className="flex flex-1 min-h-0">
          <ExpansionView onOpenCompany={openCompany} focusTech={techFocus} />
        </div>
      ) : tab === 'blog' ? (
        <div className="flex flex-1 min-h-0">
          <BlogView />
        </div>
      ) : tab === 'jobs' ? (
        loading ? (
          <div className="p-8 text-(--color-muted)">데이터 로딩 중...</div>
        ) : error ? (
          <div className="p-8 text-red-400">
            데이터 로드 실패: {error}
            <br />
            <span className="text-(--color-muted) text-sm">
              public/all_jobs_enriched.json 이 있는지 확인하세요.
            </span>
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
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
        <div className="flex flex-1 min-h-0 relative">
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
