import { useEffect, useState } from 'react'

// 현재 라이트 테마 여부 — App의 테마 토글이 발행하는 themechange 이벤트로 갱신.
// 차트/배지 등 인라인 색을 테마에 맞게 고를 때 사용.
export function useIsLight() {
  const [light, setLight] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('light'),
  )
  useEffect(() => {
    const on = () => setLight(document.documentElement.classList.contains('light'))
    window.addEventListener('themechange', on)
    return () => window.removeEventListener('themechange', on)
  }, [])
  return light
}
