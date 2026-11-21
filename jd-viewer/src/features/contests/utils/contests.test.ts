import { describe, expect, it } from 'vitest'
import {
  ALL_FILTER,
  countBy,
  ddayLabel,
  dupsByRep,
  filterContests,
  periodLabel,
  statusOf,
  todayKst,
  type Contest,
} from './contests'

const TODAY = '2026-11-21'

const c = (o: Partial<Contest>): Contest => ({
  id: 'x',
  source: 'wevity',
  url: 'https://www.wevity.com/?c=find&s=1&gbn=view&ix=1',
  title: 'AI 공모전',
  host: '주최',
  category: '개발·AI·데이터',
  prize: '',
  target: '',
  period_start: '2026-11-01',
  period_end: '2026-11-30',
  status: 'open',
  first_seen_at: '2026-11-21T10:00:00+09:00',
  last_seen_at: '2026-11-21T10:00:00+09:00',
  ...o,
})

describe('contests', () => {
  const rows = [
    c({ id: 'a', period_end: '2026-12-10' }),
    c({ id: 'b', period_end: '2026-11-25', category: '디자인·UI', source: 'thinkcontest' }),
    c({ id: 'c', status: 'closed', period_end: '2026-11-10' }),
    c({ id: 'd', period_end: '2026-11-20' }), // 받은 status 는 open 이지만 날짜가 지났다
    c({ id: 'e', period_end: null }),
    c({ id: 'f', period_end: '2026-11-25', dup_of: 'b', category: '디자인·UI', source: 'contestkorea' }),
  ]

  it('마감일이 지나면 받은 status 와 무관하게 닫는다', () => {
    expect(statusOf(rows[3], TODAY)).toBe('closed')
    expect(statusOf(c({ period_end: TODAY }), TODAY)).toBe('open') // 오늘 마감은 아직 열림
  })

  it('기본은 전체 — 모집중이 먼저(마감 가까운 순, 모름은 뒤), 마감은 뒤(최근 마감부터), 사본은 뺀다', () => {
    expect(filterContests(rows, ALL_FILTER, TODAY).map((x) => x.id)).toEqual(['b', 'a', 'e', 'd', 'c'])
    expect(filterContests(rows, { ...ALL_FILTER, status: 'open' }, TODAY).map((x) => x.id)).toEqual(['b', 'a', 'e'])
    expect(filterContests(rows, { ...ALL_FILTER, status: 'closed' }, TODAY).map((x) => x.id)).toEqual(['d', 'c'])
  })

  it('출처를 고르면 그 출처의 사본도 보인다', () => {
    expect(filterContests(rows, { ...ALL_FILTER, source: 'contestkorea' }, TODAY).map((x) => x.id)).toEqual(['f'])
    expect(dupsByRep(rows).get('b')?.map((x) => x.id)).toEqual(['f'])
  })

  it('칩 건수는 다른 축의 선택 안에서 센다', () => {
    expect(Object.fromEntries(countBy(rows, 'category', ALL_FILTER, TODAY))).toEqual({ '개발·AI·데이터': 4, '디자인·UI': 1 })
    expect(Object.fromEntries(countBy(rows, 'source', { ...ALL_FILTER, category: '디자인·UI' }, TODAY))).toEqual({
      thinkcontest: 1,
      contestkorea: 1,
    })
    expect(Object.fromEntries(countBy(rows, 'category', { ...ALL_FILTER, status: 'open' }, TODAY))).toEqual({
      '개발·AI·데이터': 2,
      '디자인·UI': 1,
    })
  })

  it('D-day·기간 표기', () => {
    expect(ddayLabel('2026-11-28', TODAY)).toBe('D-7')
    expect(ddayLabel(TODAY, TODAY)).toBe('D-day')
    expect(ddayLabel('2026-11-20', TODAY)).toBe('')
    expect(ddayLabel(null, TODAY)).toBe('')
    expect(periodLabel({ period_start: '2026-10-19', period_end: '2026-11-22' }, TODAY)).toBe('10.19 ~ 11.22')
    expect(periodLabel({ period_start: '2026-12-01', period_end: '2027-01-15' }, TODAY)).toBe('12.1 ~ 27.1.15')
    expect(periodLabel({ period_start: null, period_end: '2026-11-30' }, TODAY)).toBe('~ 11.30')
  })

  it('오늘은 KST 로 센다', () => {
    expect(todayKst(new Date('2026-11-20T15:30:00Z'))).toBe('2026-11-21')
  })
})
