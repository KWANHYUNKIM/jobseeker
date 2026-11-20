import type { ScoreParts } from './api'

/** 메인 화면 표기 — D-day·경력 구간. */

/** 이보다 멀리 남은 마감일은 상시로 본다 — 진짜 마감은 거의 60일 안이고, 먼 날짜는 원본이 '채용시 마감'을
 *  먼 날로 적은 것이다(잡코리아 기본 게재 1년 → D-346, 9999년 → D-355430). backend home.service.ALWAYS_DDAY 와 같다. */
export const ALWAYS_DDAY = 90

export function ddayLabel(d: number | null | undefined): string {
  if (d == null || d > ALWAYS_DDAY) return '상시'
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

/**
 * 짧은 공고 제목 — 앞의 [부서] 꼬리표를 떼고, 길면 끝의 괄호(영문 병기·경력 표기)를 하나씩 뗀다.
 * '[PUBG STUDIOS] DevOps Engineer (1~3년)' → 'DevOps Engineer (1~3년)',
 * '서버 개발자 (Product) (Server Developer)' → '서버 개발자 (Product)'.
 */
export function shortTitle(t: string): string {
  let s = t.replace(/^\s*\[[^\]]*\]\s*/, '').trim() || t
  while (s.length > 22) {
    const m = s.match(/^(.*\S)\s*\([^()]*\)$/)
    if (!m) break
    s = m[1]
  }
  return s
}

const PART_LABEL: [keyof ScoreParts, string][] = [
  ['size', '규모'],
  ['fresh', '새 공고'],
  ['hiring', '적극 채용'],
  ['soon', '마감 임박'],
]

/** 인기 점수 내역 한 줄 — '규모 30 + 새 공고 24 + 적극 채용 15 = 69'. 0 인 항목은 뺀다(RankRule 이 규칙을 적는다). */
export function scoreText(score: number | null | undefined, p: ScoreParts | null | undefined): string {
  if (score == null || !p) return ''
  const plus = PART_LABEL.filter(([k]) => p[k]).map(([k, l]) => `${l} ${p[k]}`)
  const minus = p.agency ? ` − 채용대행 ${-p.agency}` : ''
  return `${plus.join(' + ') || '0'}${minus} = ${score}`
}
