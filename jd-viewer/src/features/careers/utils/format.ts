/** 중앙값 칸 — 값이 없으면 '—'. */
export const med = (v: number | null | undefined, unit = '') => (v === null || v === undefined ? '—' : `${v}${unit}`)
