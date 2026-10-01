import { useEffect, useRef, useState } from 'react'
import type { FilterState } from './filter'

/** 뷰어 API(backend, 8771)의 /api/search 응답. */
export interface SearchHit {
  id: string
  url: string
  site: string
  company: string
  title: string
  career: string
  location: string
  tech_stack: string[]
  score: number
  rank_fts: number | null
  rank_vec: number | null
}

interface SearchResponse {
  query: string
  total: number
  engines: { fts: number; vector: number }
  results: SearchHit[]
}

interface State {
  hits: SearchHit[] | null // null = 검색 안 함(기존 로컬 필터를 쓰라는 뜻)
  loading: boolean
  error: string | null
  engines: { fts: number; vector: number } | null
}

// 개발 중에는 뷰어(5173)와 API(8771)가 다른 포트다. 배포에서는 nginx 가 /api 를
// 같은 오리진으로 프록시하므로 상대 경로면 된다.
export const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:8771' : ''

/** 검색 API 가 떠 있는지. 없으면 UI 에서 의미 검색 자체를 감춘다.
 *
 * 상태 코드만 보면 안 된다. /api/ 프록시가 없는 배포에서는 SPA 폴백이 걸려
 * index.html 이 200 으로 돌아오고, 그걸 "검색 살아있음"으로 읽으면 토글은 켜지는데
 * 질의는 전부 HTML 을 받아 빈 결과가 된다(실제로 그렇게 깨져 있었다).
 * 그래서 응답을 JSON 으로 파싱해 서버가 자기 소개한 {ok:true} 까지 확인한다.
 */
export function useSearchAvailable(): boolean {
  const [ok, setOk] = useState(false)
  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/api/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => !cancelled && setOk(body?.ok === true))
      .catch(() => !cancelled && setOk(false))
    return () => {
      cancelled = true
    }
  }, [])
  return ok
}

const DEBOUNCE_MS = 350

/**
 * 하이브리드 검색. enabled 가 false 이거나 질의가 비면 hits 를 null 로 둬서
 * 호출부가 기존 로컬 필터로 되돌아갈 수 있게 한다.
 *
 * 질의마다 임베딩이 걸리므로 타이핑 중에 매번 때리면 Ollama 가 큐에 쌓인다.
 * 디바운스하고, 앞선 요청은 취소한다.
 */
export function useHybridSearch(query: string, enabled: boolean, filter: FilterState): State {
  const [state, setState] = useState<State>({
    hits: null,
    loading: false,
    error: null,
    engines: null,
  })
  const abortRef = useRef<AbortController | null>(null)

  // 축 필터는 결과를 받은 뒤 화면이 건다(applyLocalFacets) — /api/search 는 검색어만
  // 받는다. 마감 공고까지 보는 중이면 후보에도 마감을 넣어 달라고 한다.
  const includeClosed = filter.closed !== 'hide'

  useEffect(() => {
    const q = query.trim()
    if (!enabled || !q) {
      abortRef.current?.abort()
      setState({ hits: null, loading: false, error: null, engines: null })
      return
    }

    setState((s) => ({ ...s, loading: true, error: null }))
    const timer = setTimeout(() => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac

      const params = new URLSearchParams({ q, kind: 'job', limit: '100' })
      if (includeClosed) params.set('include_closed', '1')

      fetch(`${API_BASE}/api/search?${params}`, { signal: ac.signal })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`)
          return r.json() as Promise<SearchResponse>
        })
        .then((d) => setState({ hits: d.results, loading: false, error: null, engines: d.engines }))
        .catch((e) => {
          if (e.name === 'AbortError') return // 뒤 요청이 이어받는다
          setState({ hits: [], loading: false, error: String(e), engines: null })
        })
    }, DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [query, enabled, includeClosed])

  return state
}
