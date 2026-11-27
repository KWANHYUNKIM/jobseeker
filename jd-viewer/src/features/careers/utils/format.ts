/** 중앙값 칸 — 값이 없으면 '—'. */
export const med = (v: number | null | undefined, unit = '') => (v === null || v === undefined ? '—' : `${v}${unit}`)

/** 비율 표기 — 반올림해서 0% 인데 실제 건수가 있으면 '<1%'. */
export function pctText(n: number, pct: number | undefined): string | null {
  if (pct === undefined) return null
  return pct === 0 && n > 0 ? '<1%' : `${pct}%`
}
