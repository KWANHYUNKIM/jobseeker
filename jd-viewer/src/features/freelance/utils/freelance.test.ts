import { describe, expect, it } from 'vitest'
import { paths } from '../../../utils/urls'
import { splitProjectSlug } from './freelance'

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
