import { useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { JobList } from './components/JobList'
import { JobDetail } from './components/JobDetail'
import { TechChart } from './components/TechChart'
import { MindmapView } from './components/MindmapView'
import { useJobs } from './lib/useJobs'
import { applyFilter, emptyFilter, stackCounts } from './lib/filter'
import type { Job } from './types'

type Tab = 'jobs' | 'mindmap'

function App() {
  const { jobs, loading, error } = useJobs()
  const [filter, setFilter] = useState(emptyFilter)
  const [selected, setSelected] = useState<Job | null>(null)
  const [tab, setTab] = useState<Tab>('jobs')

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
        <TabButton active={tab === 'mindmap'} onClick={() => setTab('mindmap')}>
          커리어 마인드맵
        </TabButton>
        <span className="ml-auto text-xs text-(--color-muted)">
          {jobs.length}건 / 필터 {filtered.length}건
        </span>
      </nav>

      {tab === 'jobs' ? (
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
          <MindmapView />
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
