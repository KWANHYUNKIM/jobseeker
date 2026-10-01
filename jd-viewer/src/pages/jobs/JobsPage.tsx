import { useMemo, useState } from 'react'
import { ErrorState, Loader, MobileBar } from '../../components/ui'
import { JobDetail } from '../../features/jobs/components/JobDetail'
import { JobList } from '../../features/jobs/components/JobList'
import { Sidebar } from '../../features/jobs/components/Sidebar'
import { useJobBoardContext } from '../../features/jobs/hooks/useJobBoard'
import { onLinkClick, useRoute } from '../../utils/navigation'
import { absUrl, SITE_NAME, useSeo } from '../../utils/seo'
import { breadcrumbJsonLd, jobDescription, jobJsonLd, jobTitle, paths, TAB_SEO } from '../../utils/urls'

/** `/` · `/jobs/<사이트>-<번호>` — 잡 리스트와 공고 상세. 상태는 app/providers 의 JobBoard. */
export function JobsPage() {
  const b = useJobBoardContext()
  const route = useRoute()
  const [filterOpen, setFilterOpen] = useState(false)

  // 공고 상세는 공고별 제목·설명·JobPosting 구조화 데이터를 쓴다. 검색어가 걸린 목록은
  // 색인하지 않는다(같은 목록의 무한 변형이라 색인해봐야 중복 페이지만 는다).
  const seo = useMemo(() => {
    const selected = b.selected
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
    return {
      title: TAB_SEO.jobs.title,
      description: TAB_SEO.jobs.desc,
      canonical: absUrl(route.path === '/jobs' ? '/' : route.path),
      robots: b.filter.query && b.isJobList ? 'noindex, follow' : undefined,
    }
  }, [b.selected, b.filter.query, b.isJobList, route.path])
  useSeo(seo)

  if (b.loading) return <Loader label="채용 데이터 불러오는 중…" />
  if (b.error) {
    return (
      <ErrorState
        title="데이터를 불러오지 못했습니다"
        detail={b.error}
        hint={
          b.apiMode ? (
            <>뷰어 API(/api/jobs)와 정본 DB 가 떠 있는지 확인하세요.</>
          ) : (
            <>public/all_jobs_enriched.json 이 있는지 확인하세요.</>
          )
        }
      />
    )
  }
  if (b.selectedLoading) return <Loader label="공고 불러오는 중…" />
  if (b.selected) {
    // 공고를 고르면 목록을 통째로 갈아끼운다. 모달로 띄우면 오른쪽 취업 가이드가
    // 들어갈 폭이 안 나오고, 좁은 칸에 겹쳐 둔 JD 와 가이드는 둘 다 안 읽힌다.
    return (
      <div key="jobdetail" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
        <JobDetail key={b.selected.url} job={b.selected} onOpenUrl={b.openJobByUrl} />
      </div>
    )
  }
  if (b.detail) {
    // 주소에는 공고 id 가 있는데 데이터에 없다 — 마감돼 걷힌 공고이거나 오래된 링크.
    return (
      <ErrorState
        title="없는 공고입니다"
        detail={`공고 ${b.detail} 을(를) 찾지 못했습니다.`}
        hint={
          <a href="/" onClick={onLinkClick('/')} className="text-(--color-accent) underline">
            전체 공고 목록으로
          </a>
        }
      />
    )
  }
  return (
    <div className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <Sidebar
        filter={b.filter}
        setFilter={b.setFilter}
        facets={b.facets}
        totalCount={b.totalCount}
        filteredCount={b.filteredCount}
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        semantic={
          b.searchAvailable
            ? { on: b.semantic, setOn: b.setSemantic, loading: b.searchState.loading, engines: b.searchState.engines }
            : undefined
        }
      />
      <main data-scroll className="flex-1 min-w-0 overflow-auto jd-panel">
        <MobileBar onMenu={() => setFilterOpen(true)} label="필터">
          <span className="ml-auto text-xs text-(--color-muted) tabular-nums">
            {b.filteredCount.toLocaleString()}건
          </span>
        </MobileBar>
        <JobList jobs={b.filtered} server={b.page} />
      </main>
    </div>
  )
}
