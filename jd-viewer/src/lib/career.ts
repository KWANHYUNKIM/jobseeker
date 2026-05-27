import type { CareerBucket } from '../types'

export function careerBucket(career: string): CareerBucket {
  if (!career) return '정보없음'
  if (/신입|무관/.test(career)) return '신입/무관'
  const m = career.match(/(\d+)/)
  if (!m) return '정보없음'
  const n = parseInt(m[1], 10)
  if (n <= 2) return '1-2년'
  if (n <= 4) return '3-4년'
  if (n <= 7) return '5-7년'
  return '8년+'
}
