import { useCallback, useEffect, useState } from 'react'

// 탭 상태를 URL 해시(#radar 등)와 양방향 동기화한다.
// - 진입 시 해시를 읽어 초기 탭을 정한다(딥링크·새로고침 유지)
// - 탭 전환 시 해시를 갱신한다(주소창·공유 가능)
// - 브라우저 뒤로/앞으로(hashchange)로 이전·다음 탭으로 이동한다
export function useHashTab<T extends string>(tabs: readonly T[], fallback: T): [T, (tab: T) => void] {
  const read = useCallback((): T => {
    const raw = window.location.hash.replace(/^#/, '')
    return (tabs as readonly string[]).includes(raw) ? (raw as T) : fallback
  }, [tabs, fallback])

  const [tab, setTab] = useState<T>(read)

  useEffect(() => {
    const onHashChange = () => setTab(read())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [read])

  const select = useCallback((next: T) => {
    setTab(next)
    if (window.location.hash.replace(/^#/, '') !== next) {
      window.location.hash = next
    }
  }, [])

  return [tab, select]
}
