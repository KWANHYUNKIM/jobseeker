import { describe, expect, it } from 'vitest'
import type { Job } from '../types'
import { applyFilter, computeFacets, emptyFilter } from './filter'

function job(over: Partial<Job>): Job {
  return {
    site: 'wanted', idx: 0, pid: over.pid ?? 'x', company: '회사', title: '백엔드 개발자',
    url: `https://e.x/${over.pid ?? 'x'}`, career: '신입', location: '서울 강남구', tech_stack: [],
    main_tasks: '', qualifications: '', preferences: '', benefits: '', full_jd: '',
    status: 'active', first_seen_at: '2026-09-01', ...over,
  }
}

const JOBS = [
  job({ pid: '1', company: '현대자동차', title: '백엔드', tech_stack: ['Java', 'Spring'], first_seen_at: '2026-09-01' }),
  job({ pid: '2', company: '다른회사', title: '현대자동차 협력 프론트엔드', location: '부산 해운대구', first_seen_at: '2026-09-03' }),
  job({ pid: '3', company: '카카오', title: 'iOS', full_jd: '현대자동차 고객사', first_seen_at: '2026-09-05', status: 'closed' }),
  job({ pid: '4', company: '토스', title: '백엔드', tech_stack: ['java'], first_seen_at: '2026-09-04', status_source: 'unknown' }),
]

describe('applyFilter', () => {
  it('기본은 모집중만, 최신순', () => {
    expect(applyFilter(JOBS, emptyFilter()).map((j) => j.pid)).toEqual(['4', '2', '1'])
  })
  it('검색어는 회사 > 제목 > 본문 순으로 먼저 온다', () => {
    const f = { ...emptyFilter(), query: '현대자동차', closed: 'show' as const }
    expect(applyFilter(JOBS, f).map((j) => j.pid)).toEqual(['1', '2', '3'])
  })
  it('스택은 고른 것을 전부 가진 공고(대소문자 무시)', () => {
    const f = { ...emptyFilter(), stacks: new Set(['JAVA']) }
    expect(applyFilter(JOBS, f).map((j) => j.pid)).toEqual(['4', '1'])
  })
  it('미확인 숨김은 모집중 unknown 만 뺀다', () => {
    const f = { ...emptyFilter(), unverified: 'hide' as const }
    expect(applyFilter(JOBS, f).map((j) => j.pid)).toEqual(['2', '1'])
  })
})

describe('computeFacets', () => {
  it('칩 건수는 자기 축만 빼고 센다', () => {
    const f = { ...emptyFilter(), regions: new Set(['서울']) }
    const fc = computeFacets(JOBS, f)
    // 지역 칩은 지역 필터를 빼고 센다 → 부산도 1 로 보인다
    expect(fc.regions.find((r) => r.name === '부산')?.count).toBe(1)
    // 다른 축은 서울 필터를 탄다 → 모집중 서울 공고 2건
    expect([...fc.siteCount.values()].reduce((a, b) => a + b, 0)).toBe(2)
  })
})
