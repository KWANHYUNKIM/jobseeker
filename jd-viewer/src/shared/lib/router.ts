import { useCallback, useMemo, useSyncExternalStore } from 'react'

// 히스토리 API 라우터 — 화면 상태를 주소창으로 옮긴다.
//
// 왜 해시(#radar/netflix)를 버렸나:
//  - 검색엔진은 `#` 뒤를 URL 의 일부로 보지 않는다. 해시 라우팅이면 공고가 몇 만 건이든
//    색인되는 주소는 `/` 하나뿐이라, 사실상 색인이 안 된다.
//  - 해시는 프리렌더(주소별 정적 HTML)를 만들 수도 없다. 서버는 해시를 못 보기 때문.
// 그래서 pushState 로 진짜 경로(/jobs/wanted-364849)를 쓴다. 서버는 없는 경로를
// index.html 로 폴백하고(nginx try_files / serve_viewer.py), 빌드 때 주소별 HTML 을 깐다.
//
// 라우터 라이브러리를 안 쓴 이유: 필요한 게 "경로 읽기 + 이동 + 뒤로가기"뿐이라
// 60 줄이면 끝나고, 의존성 없이 프리렌더 스크립트와 규칙을 공유하기도 쉽다.

const listeners = new Set<() => void>()

function readLocation(): string {
  return window.location.pathname + window.location.search
}

// useSyncExternalStore 는 getSnapshot 이 같은 값이면 같은 참조를 돌려주길 요구한다.
// (매번 새 문자열을 만들어도 값이 같으면 문제없지만, 캐시해 두면 비교가 확실하다.)
let snapshot = typeof window === 'undefined' ? '/' : readLocation()

function emit() {
  snapshot = readLocation()
  for (const l of listeners) l()
}

function subscribe(l: () => void): () => void {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('popstate', emit)
}

// 앱 안에서 push 한 횟수. goBack 이 "뒤로 가면 우리 화면인가"를 판단하는 데 쓴다.
// (외부에서 상세 링크로 바로 들어온 사람은 뒤로 가면 우리 사이트를 떠나게 되므로,
//  그럴 땐 history.back() 대신 목록 주소로 이동시킨다.)
let pushDepth = 0

export function navigate(to: string, opts: { replace?: boolean } = {}): void {
  const url = to.startsWith('/') ? to : `/${to}`
  if (url === readLocation()) return
  if (opts.replace) {
    window.history.replaceState(null, '', url)
  } else {
    window.history.pushState(null, '', url)
    pushDepth += 1
  }
  emit()
}

/** 뒤로가기. 앱 안에서 들어온 화면이면 실제 뒤로, 외부 유입이면 fallback 주소로. */
export function goBack(fallback: string): void {
  if (pushDepth > 0) {
    pushDepth -= 1
    window.history.back()
  } else {
    navigate(fallback, { replace: true })
  }
}

export interface Route {
  /** 쿼리 제외 경로 (예: `/jobs/wanted-364849`) */
  path: string
  /** 경로 세그먼트 (예: `['jobs', 'wanted-364849']`) */
  seg: string[]
  query: URLSearchParams
}

export function useRoute(): Route {
  const loc = useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => '/',
  )
  return useMemo(() => {
    const [path, search = ''] = loc.split('?')
    return {
      path,
      seg: path.split('/').filter(Boolean).map(decodeURIComponent),
      query: new URLSearchParams(search),
    }
  }, [loc])
}

/** 현재 주소의 쿼리 한 개만 바꾼다(값이 falsy 면 제거). 기본은 replace — 타이핑마다 히스토리가 쌓이면 뒤로가기가 망가진다. */
export function useSetQuery(): (key: string, value: string | null, opts?: { push?: boolean }) => void {
  return useCallback((key, value, opts = {}) => {
    const url = new URL(window.location.href)
    if (value) url.searchParams.set(key, value)
    else url.searchParams.delete(key)
    navigate(url.pathname + (url.searchParams.toString() ? `?${url.searchParams}` : ''), {
      replace: !opts.push,
    })
  }, [])
}

/** 링크 클릭 가로채기 — 새 탭(⌘/Ctrl·가운데 버튼)이나 수정자 키는 브라우저에 맡긴다. */
export function onLinkClick(to: string) {
  return (e: React.MouseEvent) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault()
    navigate(to)
  }
}

/**
 * 예전 해시 주소(#radar/netflix)를 새 경로(/radar/netflix)로 넘긴다.
 * 북마크·공유된 링크가 이미 돌아다니므로 조용히 리다이렉트한다.
 */
export function migrateLegacyHash(): void {
  const hash = window.location.hash.replace(/^#/, '')
  if (!hash) return
  const clean = hash.split('/').filter(Boolean).map(encodeURIComponent).join('/')
  if (!clean) return
  window.history.replaceState(null, '', `/${clean}${window.location.search}`)
  emit()
}
