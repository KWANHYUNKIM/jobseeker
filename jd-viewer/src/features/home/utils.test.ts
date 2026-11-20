import { describe, expect, it } from 'vitest'
import { careerOf, careerRange, ddayLabel, shortTitle } from './utils'

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
  it('먼 날짜는 상시', () => expect(ddayLabel(355430)).toBe('상시'))
  it('90일 넘게 남으면 상시 — 잡코리아 기본 게재 1년', () => {
    expect(ddayLabel(346)).toBe('상시')
    expect(ddayLabel(90)).toBe('D-90')
  })
})

describe('shortTitle', () => {
  it('부서 꼬리표를 뗀다', () => expect(shortTitle('[PUBG STUDIOS] DevOps Engineer (1~3년)')).toBe('DevOps Engineer (1~3년)'))
  it('영문 병기를 뗀다', () => expect(shortTitle('서버 개발자 (Product) (Server Developer)')).toBe('서버 개발자 (Product)'))
  it('길면 괄호를 거듭 뗀다', () =>
    expect(shortTitle('LLM Research Engineer (Pre-training) (신입/경력)')).toBe('LLM Research Engineer'))
  it('짧으면 그대로', () => expect(shortTitle('백엔드 개발자')).toBe('백엔드 개발자'))
})
