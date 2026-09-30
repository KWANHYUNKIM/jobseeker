import { describe, expect, it } from 'vitest'
import { emptyFilter } from './filter'
import { API_PAGE_SIZE, toParams } from './useJobsApi'

describe('toParams — /api/jobs 질의', () => {
  it('빈 필터', () => {
    expect(toParams(emptyFilter(), true, 0).toString()).toBe(
      `closed=hide&unverified=show&page=1&limit=${API_PAGE_SIZE}`,
    )
  })

  it('축마다 이름이 서버 파라미터와 같고, 값은 정렬해 캐시 키가 흔들리지 않는다', () => {
    const f = {
      ...emptyFilter(),
      sites: new Set(['saramin', 'wanted'] as const),
      careers: new Set(['3-4년']),
      stacks: new Set(['Spring', 'Java']),
      roles: new Set(['백엔드']),
      regions: new Set(['서울']),
      districts: new Set(['강남구']),
      sizes: new Set(['대기업'] as const),
      query: '  카프카 ',
      closed: 'show' as const,
    }
    const p = toParams(f, true, 2)
    expect(p.getAll('site')).toEqual(['saramin', 'wanted'])
    expect(p.getAll('stack')).toEqual(['Java', 'Spring'])
    expect(p.get('career')).toBe('3-4년')
    expect(p.get('role')).toBe('백엔드')
    expect(p.get('region')).toBe('서울')
    expect(p.get('district')).toBe('강남구')
    expect(p.get('size')).toBe('대기업')
    expect(p.get('q')).toBe('  카프카 ')
    expect(p.get('semantic')).toBe('1')
    expect(p.get('closed')).toBe('show')
    expect(p.get('page')).toBe('3')
  })

  it('의미 검색은 검색어가 있을 때만', () => {
    expect(toParams(emptyFilter(), true, 0).has('semantic')).toBe(false)
  })
})
