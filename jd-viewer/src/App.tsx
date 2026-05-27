import { useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { JobList } from './components/JobList'
import { JobDetail } from './components/JobDetail'
import { TechChart } from './components/TechChart'
import { useJobs } from './lib/useJobs'
import { applyFilter, emptyFilter, stackCounts } from './lib/filter'
import type { Job } from './types'

function App() {
  const { jobs, loading, error } = useJobs()
  const [filter, setFilter] = useState(emptyFilter)
  const [selected, setSelected] = useState<Job | null>(null)

  const filtered = useMemo(() => applyFilter(jobs, filter), [jobs, filter])
  const stacks = useMemo(() => stackCounts(filtered), [filtered])
  const allStacks = useMemo(() => stackCounts(jobs), [jobs])

  if (loading) {
    return <div className="p-8 text-(--color-muted)">데이터 로딩 중...</div>
  }
  if (error) {
    return (
      <div className="p-8 text-red-400">
        데이터 로드 실패: {error}
        <br />
        <span className="text-(--color-muted) text-sm">
          public/all_jobs_enriched.json 이 있는지 확인하세요.
        </span>
      </div>
    )
  }

  const toggleStack = (name: string) => {
    const next = new Set(filter.stacks)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setFilter({ ...filter, stacks: next })
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar
        filter={filter}
        setFilter={setFilter}
        topStacks={allStacks}
        totalCount={jobs.length}
        filteredCount={filtered.length}
      />
      <main className="flex-1 min-w-0">
        <TechChart data={stacks} onPick={toggleStack} highlight={filter.stacks} />
        <JobList jobs={filtered} selected={selected} onSelect={setSelected} />
      </main>
      {selected && <JobDetail job={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

export default App
