/** 중앙값 칸 — 값이 없으면 '—'. */
export const med = (v: number | null | undefined, unit = '') => (v === null || v === undefined ? '—' : `${v}${unit}`)
/** 학점 — 소수 한 자리로(4 → 4.0). 값이 없으면 '—'. */
export const gpa = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v.toFixed(1))
