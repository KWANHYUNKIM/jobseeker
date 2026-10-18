import { useEffect, useState } from 'react'

const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * 숫자가 0 에서 목표까지 한 번 올라간다 — 첫 화면에서 한 번만(그다음 값이 바뀌면 바로 그 값).
 * 움직임 줄이기를 켰으면 처음부터 목표 값.
 */
export function useCountUp(target: number, ms = 900): number {
  const [v, setV] = useState(() => (reduced() ? target : 0))
  const [done, setDone] = useState(reduced())
  useEffect(() => {
    if (done) return
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      const eased = 1 - Math.pow(1 - p, 3)
      setV(Math.round(target * eased))
      if (p < 1) raf = requestAnimationFrame(tick)
      else setDone(true)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [done, target, ms])
  return done ? target : v
}
