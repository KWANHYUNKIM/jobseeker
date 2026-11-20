import { useEffect, useState } from 'react'

/**
 * 키가 바뀔 때마다 다시 받는다. 앞 요청은 끊는다(필터를 빨리 바꿔도 늦게 온 답이 덮지 않게).
 * 받는 동안에도 앞의 답(data)은 그대로 둔다 — 화면이 깜빡이지 않고 흐려지기만 한다.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, key: string) {
  const [state, setState] = useState<{ key: string | null; data: T | null; error: string | null }>({
    key: null,
    data: null,
    error: null,
  })
  useEffect(() => {
    const ac = new AbortController()
    load(ac.signal)
      .then((data) => setState({ key, data, error: null }))
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setState({ key, data: null, error: e.message })
      })
    return () => ac.abort()
    // load 는 key 로 대표된다 — 호출부가 매 렌더 새 함수를 넘겨도 다시 받지 않는다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return { data: state.data, error: state.key === key ? state.error : null, loading: state.key !== key }
}
