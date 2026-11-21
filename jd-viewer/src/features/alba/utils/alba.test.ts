import { describe, expect, it } from 'vitest'
import { ALL_FILTER, countBy, dayLabel, deadlineLabel, filterPosts, payLabel, sourceLabel, sourceOf, type AlbaPost } from './alba'

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

  it('기본은 전체 — 모집중이 먼저(등록일 최신순), 마감은 뒤에 남는다', () => {
    expect(filterPosts(rows, ALL_FILTER).map((p) => p.id)).toEqual(['d', 'b', 'a', 'c'])
    expect(filterPosts(rows, { ...ALL_FILTER, status: 'open' }).map((p) => p.id)).toEqual(['d', 'b', 'a'])
    expect(filterPosts(rows, { ...ALL_FILTER, status: 'closed' }).map((p) => p.id)).toEqual(['c'])
  })

  it('분류·지역으로 거른다', () => {
    expect(filterPosts(rows, { ...ALL_FILTER, category: '코딩·IT 강사' }).map((p) => p.id)).toEqual(['b'])
    expect(filterPosts(rows, { ...ALL_FILTER, sido: '부산' }).map((p) => p.id)).toEqual(['d', 'b'])
  })

  it('칩 건수는 다른 축의 선택 안에서 센다', () => {
    const f = { ...ALL_FILTER, status: 'open' as const, sido: '부산' }
    expect(Object.fromEntries(countBy(rows, 'category', f))).toEqual({ '웹·앱 제작': 1, '코딩·IT 강사': 1 })
    expect(Object.fromEntries(countBy(rows, 'sido', { ...ALL_FILTER, status: 'open' }))).toEqual({ 서울: 1, 부산: 2 })
    expect(Object.fromEntries(countBy(rows, 'sido', ALL_FILTER))).toEqual({ 서울: 2, 부산: 2 })
  })

  it('급여·날짜 표기', () => {
    expect(payLabel(null)).toBe('급여 협의')
    expect(payLabel({ amount: 40000, unit: '건당', text: '건당 40,000원' })).toBe('건당 40,000원')
    expect(payLabel({ amount: 12000, unit: '시급', text: '' })).toBe('시급 12,000원')
    expect(dayLabel('2026-11-20T16:00:00Z')).toBe('11.21') // KST 로 넘어간다
    expect(dayLabel(null)).toBe('')
  })

  it('출처로 거르고, 출처 칩 건수는 다른 축 안에서 센다', () => {
    const multi = [
      post({ id: 'daangn-a' }), // 옛 파일 — source 가 없으면 당근
      post({ id: 'albamon-1', source: 'albamon', category: '디자인·영상' }),
      post({ id: 'saramin-2', source: 'saramin', status: 'closed' }),
      post({ id: 'albamon-3', source: 'albamon', sido: '부산' }),
    ]
    expect(sourceOf(multi[0])).toBe('daangn')
    expect(filterPosts(multi, { ...ALL_FILTER, source: 'albamon' }).map((p) => p.id)).toEqual(['albamon-1', 'albamon-3'])
    // 마감한 사람인 공고도 '전체'에서는 남는다(뒤로 간다).
    expect(filterPosts(multi, ALL_FILTER).at(-1)?.id).toBe('saramin-2')
    expect(Object.fromEntries(countBy(multi, 'source', { ...ALL_FILTER, sido: '서울' }))).toEqual({ daangn: 1, albamon: 1, saramin: 1 })
    expect(Object.fromEntries(countBy(multi, 'category', { ...ALL_FILTER, source: 'albamon' }))).toEqual({ '디자인·영상': 1, '웹·앱 제작': 1 })
    expect(sourceLabel('albacheonguk')).toBe('알바천국')
    expect(sourceLabel('daangn', { daangn: '당근알바' })).toBe('당근알바')
  })

  it('급여 없음은 출처에 따라 다르게, 마감일은 모집중에만', () => {
    expect(payLabel(null, 'saramin')).toBe('급여 원문 확인') // 사람인 목록은 급여를 주지 않는다
    expect(payLabel(null, 'albamon')).toBe('급여 협의')
    expect(deadlineLabel(post({ deadline: '2026-12-03' }))).toBe('~12.3 마감')
    expect(deadlineLabel(post({ deadline: '2026-12-03', status: 'closed' }))).toBe('')
    expect(deadlineLabel(post({}))).toBe('')
  })
})
