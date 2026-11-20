import { describe, expect, it } from 'vitest'
import { paths } from '../../../utils/urls'
import { projectState, splitProjectSlug } from './freelance'

describe('splitProjectSlug', () => {
  it('사이트와 번호를 첫 - 에서 가른다', () => {
    expect(splitProjectSlug('jobkorea-50346332')).toEqual(['jobkorea', '50346332'])
    expect(splitProjectSlug('wanted_gigs-14765')).toEqual(['wanted_gigs', '14765'])
  })
  it('주소를 만든 것과 되읽은 것이 같다', () => {
    const to = paths.freelanceProject('saramin', '55298406')
    expect(splitProjectSlug(to.split('/')[2])).toEqual(['saramin', '55298406'])
  })
  it('- 가 없으면 프로젝트 주소가 아니다', () => {
    expect(splitProjectSlug('rates')).toBeNull()
  })
})

describe('projectState — 접수마감 판정', () => {
  const now = Date.parse('2026-11-20T12:00:00+09:00')
  const today = '2026-11-20'
  const base = { status: 'active' as const, deadline: null, last_seen_at: '2026-11-20T09:00:00+09:00' }

  it('원본이 닫은 것은 그 근거로 접수마감', () => {
    expect(projectState({ ...base, status: 'closed', closed_reason: '원본 확인: 접수마감' }, today, now)).toEqual({
      open: false,
      label: '접수마감',
      reason: '원본 확인: 접수마감',
    })
  })
  it('status 가 모집중이어도 마감일이 지났으면 접수마감', () => {
    const s = projectState({ ...base, deadline: '2026-11-19' }, today, now)
    expect(s.open).toBe(false)
    expect(s.reason).toBe('마감일 경과(2026-11-19)')
  })
  it('마감일 당일은 아직 모집중', () => {
    expect(projectState({ ...base, deadline: today }, today, now).open).toBe(true)
  })
  it('14일 넘게 목록에 안 보이면 접수마감, API 의 stale 도 같다', () => {
    expect(projectState({ ...base, last_seen_at: '2026-11-01T09:00:00+09:00' }, today, now).open).toBe(false)
    expect(projectState({ ...base, status: 'stale' }, today, now).label).toBe('접수마감')
  })
  it('나머지는 모집중', () => {
    expect(projectState(base, today, now)).toEqual({ open: true, label: '모집중', reason: null })
  })
})
