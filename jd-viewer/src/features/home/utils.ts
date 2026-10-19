/** 메인 화면 표기 — D-day·경력 구간. */

export function ddayLabel(d: number | null | undefined): string {
  if (d == null) return '상시'
  if (d <= 0) return '오늘 마감'
  return `D-${d}`
}

/** D-day 가 가까울수록 진하게 — 사흘 안이면 마감 임박. */
export function ddayUrgent(d: number | null | undefined): boolean {
  return d != null && d <= 3
}

const RANGE: Record<string, [number, number | null]> = {
  '신입/무관': [0, 0],
  '1-2년': [1, 2],
  '3-4년': [3, 4],
  '5-7년': [5, 7],
  '8년+': [8, null],
}

/** 회사가 찾는 경력의 폭 — '신입 ~ 7년', '3~4년', '8년 이상'. 모르면 ''. */
export function careerRange(from: string | null, to: string | null): string {
  const a = from ? RANGE[from] : undefined
  const b = to ? RANGE[to] : undefined
  if (!a || !b) return ''
  const lo = a[0] === 0 ? '신입' : `${a[0]}`
  if (b[1] == null) return a[0] === 8 ? '8년 이상' : `${lo}${a[0] === 0 ? '' : '년'} ~ 8년+`
  if (a[0] === 0 && b[1] === 0) return '신입'
  return a[0] === 0 ? `신입 ~ ${b[1]}년` : `${lo}~${b[1]}년`
}

/** 한 공고의 경력 표기 — 원문이 짧으면 원문, 아니면 구간. */
export function careerOf(career: string | null, bucket: string): string {
  if (bucket === '신입/무관') return '신입 가능'
  if (bucket === '정보없음') return career && career.length <= 12 ? career : '경력 미표기'
  return `경력 ${bucket}`
}

export const SIZE_SHORT: Record<string, string> = { 대기업: '대기업', 중견기업: '중견', 중소기업: '중소', '해외 기업': '해외' }
