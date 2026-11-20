import { describe, expect, it } from 'vitest'
import { ALL_FILTER, countBy, dayLabel, filterPosts, payLabel, type AlbaPost } from './alba'

const post = (o: Partial<AlbaPost>): AlbaPost => ({
  id: 'x',
  url: 'https://jobs.daangn.com/job-posts/x',
  title: '홈페이지 제작',
  category: '웹·앱 제작',
  pay: null,
  sido: '서울',
  sigungu: '강남구',
  employment: '알바',
  hours: '',
  posted_at: '2026-11-20T09:00:00Z',
  first_seen_at: '2026-11-21T10:00:00+09:00',
  last_seen_at: '2026-11-21T10:00:00+09:00',
  status: 'open',
  ...o,
})

describe('alba', () => {
  const rows = [
    post({ id: 'a', posted_at: '2026-11-18T00:00:00Z' }),
    post({ id: 'b', category: '코딩·IT 강사', sido: '부산' }),
    post({ id: 'c', status: 'closed' }),
    post({ id: 'd', posted_at: null, first_seen_at: '2026-11-21T01:00:00Z', sido: '부산' }),
  ]

  it('기본은 모집중만, 등록일 최신순', () => {
    expect(filterPosts(rows, ALL_FILTER).map((p) => p.id)).toEqual(['d', 'b', 'a'])
    expect(filterPosts(rows, { ...ALL_FILTER, status: 'closed' }).map((p) => p.id)).toEqual(['c'])
  })

  it('분류·지역으로 거른다', () => {
    expect(filterPosts(rows, { ...ALL_FILTER, category: '코딩·IT 강사' }).map((p) => p.id)).toEqual(['b'])
    expect(filterPosts(rows, { ...ALL_FILTER, sido: '부산' }).map((p) => p.id)).toEqual(['d', 'b'])
  })

  it('칩 건수는 다른 축의 선택 안에서 센다', () => {
    const f = { ...ALL_FILTER, sido: '부산' }
    expect(Object.fromEntries(countBy(rows, 'category', f))).toEqual({ '웹·앱 제작': 1, '코딩·IT 강사': 1 })
    expect(Object.fromEntries(countBy(rows, 'sido', ALL_FILTER))).toEqual({ 서울: 1, 부산: 2 })
  })

  it('급여·날짜 표기', () => {
    expect(payLabel(null)).toBe('급여 협의')
    expect(payLabel({ amount: 40000, unit: '건당', text: '건당 40,000원' })).toBe('건당 40,000원')
    expect(payLabel({ amount: 12000, unit: '시급', text: '' })).toBe('시급 12,000원')
    expect(dayLabel('2026-11-20T16:00:00Z')).toBe('11.21') // KST 로 넘어간다
    expect(dayLabel(null)).toBe('')
  })
})
