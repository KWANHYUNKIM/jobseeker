import { createContext, useContext, useDeferredValue, useEffect, useMemo, useState } from 'react'
import type { Job } from '../../../types'
import { navigate, useRoute, useSetQuery } from '../../../utils/navigation'
import { jobKey, paths } from '../../../utils/urls'
import { EMPTY_FACETS, lookupJobKey } from '../api'
import { applyFilter, applyLocalFacets, computeFacets, emptyFilter } from '../utils/filter'
import { useHybridSearch, useSearchAvailable } from './useHybridSearch'
import { useJobs } from './useJobs'
import { useJob, useJobPage, useJobsApiAvailable } from './useJobsApi'

/**
 * 잡 리스트 화면의 상태 전부 — 필터, API/파일 모드, 목록 한 쪽, 고른 공고.
 *
 * 화면 위 헤더가 어느 탭에서든 '전체 N건 · 필터 M건' 을 보여주므로 잡 리스트 페이지
 * 안에 둘 수 없다. app/providers.tsx 가 한 번 만들어 헤더와 JobsPage 가 같이 읽는다.
 */
export function useJobBoard() {
  // 공고 API 가 있으면 목록·칩 건수·상세를 DB 에서 받는다. 없는 배포에서만
  // 예전처럼 공고 전량 파일(184MB)을 받아 화면에서 거른다.
  const api = useJobsApiAvailable()
  const apiMode = api === 'yes'
  const { jobs, loading: fileLoading, error: fileError } = useJobs(api === 'no')
  const route = useRoute()
  const setQueryParam = useSetQuery()
  const onJobsTab = route.seg[0] === undefined || route.seg[0] === '' || route.seg[0] === 'jobs'
  // 주소의 두 번째 세그먼트가 공고 키다(`/jobs/<사이트>-<번호>`).
  const detail = onJobsTab ? (route.seg[1] ?? null) : null

  // 검색어는 주소에 담아 공유·새로고침에 살아남게 한다. 다만 타이핑마다 히스토리를
  // 쌓으면 뒤로가기가 글자 수만큼 눌러야 하는 물건이 되므로 replace 로만 갱신한다.
  const [filter, setFilter] = useState(() => ({
    ...emptyFilter(),
    query: new URLSearchParams(window.location.search).get('q') ?? '',
  }))
  // 검색 API 가 있으면 의미 검색을 기본으로 쓴다. 키워드 필터는 사전에 있는 단어가
  // 정확히 나와야만 잡아서, 문장으로 물으면 대개 0건이 된다 — 그게 기본값일 이유가 없다.
  const [semantic, setSemantic] = useState(true)

  const isJobList = onJobsTab && !detail
  useEffect(() => {
    if (!isJobList) return
    setQueryParam('q', filter.query || null)
  }, [filter.query, isJobList, setQueryParam])

  // 선택된 공고는 상태가 아니라 주소에서 나온다 — 뒤로가기·새로고침·링크 공유가
  // 전부 같은 경로 하나로 해결된다.
  const selectedLocal = useMemo(
    () => (!apiMode && detail ? (jobs.find((j) => jobKey(j) === detail) ?? null) : null),
    [apiMode, jobs, detail],
  )
  const remoteJob = useJob(detail, apiMode)
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
  // 늦게 찍힌다. 입력 칸은 filter 로 바로 그리고, 무거운 계산은 한 박자 늦은 사본으로 한다.
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
    // /api/search 는 검색어만 받는다 — 모든 축은 여기서 건다(순서는 그대로 둔다).
    return applyLocalFacets(found, view)
  }, [apiMode, remote.items, hits, localFiltered, jobs, view])
  // 칩 건수는 필터를 타야 한다. 예전에는 jobs 전체로 셌더니, 목록은 '모집중만'
  // 3천 건인데 사이드바는 마감까지 합친 1만 건을 말하고 있었다.
  const localFacets = useMemo(() => (apiMode ? EMPTY_FACETS : computeFacets(jobs, view)), [apiMode, jobs, view])

  return {
    api,
    apiMode,
    detail,
    isJobList,
    filter,
    setFilter,
    semantic,
    setSemantic,
    searchAvailable,
    selected,
    selectedLoading: apiMode && !!detail && remoteJob.loading,
    openJobByUrl,
    filtered,
    facets: apiMode ? remote.facets : localFacets,
    // 헤더·사이드바의 건수. API 모드에서는 목록이 한 쪽뿐이라 서버가 센 값을 쓴다.
    totalCount: apiMode ? remote.allTotal : jobs.length,
    filteredCount: apiMode ? remote.total : filtered.length,
    loading: api === 'unknown' || (apiMode ? remote.loading && remote.allTotal === 0 && !detail : fileLoading),
    error: apiMode ? remote.error : fileError,
    countsReady: apiMode ? remote.allTotal > 0 : !fileLoading,
    searchState: {
      loading: apiMode ? remote.loading : searching,
      engines: apiMode ? remote.engines : engines,
    },
    page: apiMode ? { page: apiPage, total: remote.total, onChange: setApiPage } : undefined,
  }
}

export type JobBoard = ReturnType<typeof useJobBoard>

export const JobBoardContext = createContext<JobBoard | null>(null)

export function useJobBoardContext(): JobBoard {
  const board = useContext(JobBoardContext)
  if (!board) throw new Error('JobBoardContext 밖에서 불렀다 — app/providers.tsx 가 감싸야 한다')
  return board
}
