import { describe, expect, it } from 'vitest'
import { careerOf, careerRange, ddayLabel } from './utils'

describe('careerRange', () => {
  it('신입부터 위까지', () => {
    expect(careerRange('신입/무관', '5-7년')).toBe('신입 ~ 7년')
    expect(careerRange('신입/무관', '신입/무관')).toBe('신입')
  })
  it('경력 구간 하나', () => expect(careerRange('3-4년', '3-4년')).toBe('3~4년'))
  it('8년 이상', () => {
    expect(careerRange('8년+', '8년+')).toBe('8년 이상')
    expect(careerRange('3-4년', '8년+')).toBe('3년 ~ 8년+')
  })
  it('모르면 비운다', () => expect(careerRange(null, null)).toBe(''))
})

describe('careerOf', () => {
  it('경력 정보가 없으면 무관이 아니라 미표기', () => {
    expect(careerOf(null, '정보없음')).toBe('경력 미표기')
    expect(careerOf(null, '신입/무관')).toBe('신입 가능')
  })
})

describe('ddayLabel', () => {
  it('마감일 없음은 상시', () => expect(ddayLabel(null)).toBe('상시'))
  it('오늘', () => expect(ddayLabel(0)).toBe('오늘 마감'))
  it('남은 날', () => expect(ddayLabel(5)).toBe('D-5'))
})
