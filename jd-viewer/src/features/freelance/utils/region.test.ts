import { describe, expect, it } from 'vitest'
import { projectPlace, REMOTE } from './region'

describe('projectPlace', () => {
  it.each([
    ['서울 영등포구', '서울', '영등포구'],
    ['가산디지털단지, 금천구', '서울', '금천구'],
    ['을지로입구, 명동', '서울', null],
    ['판교, 성남시', '경기', '성남시'],
    ['기흥', '경기', null],
    ['전남광주 서구', '광주', '서구'],
    ['천안시, 두정', '충남', '천안시'],
    ['창원시, 의창구', '경남', '창원시'],
    ['도쿄', '해외·원격', null],
    ['중구', '정보없음', null],
  ])('%s → %s %s', (location, region, district) => {
    expect(projectPlace({ location, kind: 'onsite' })).toEqual({ region, district })
  })

  it('근무지 없는 원격 도급은 원격, 상주는 정보없음', () => {
    expect(projectPlace({ location: '', kind: 'remote' }).region).toBe(REMOTE)
    expect(projectPlace({ location: '', kind: 'onsite' }).region).toBe('정보없음')
  })
})
