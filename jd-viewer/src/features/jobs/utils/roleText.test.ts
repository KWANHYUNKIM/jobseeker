import { describe, expect, it } from 'vitest'
import { matchRoleLine, roleTokens } from './roleText'

describe('roleTokens', () => {
  it('굵게·출처 번호·추론을 조각으로 나눈다', () => {
    expect(roleTokens('같은 용량이면 **10배** 비쌌다.[2] {추론}')).toEqual([
      { kind: 'text', text: '같은 용량이면 ' },
      { kind: 'bold', text: '10배' },
      { kind: 'text', text: ' 비쌌다.' },
      { kind: 'ref', n: 2 },
      { kind: 'text', text: ' ' },
      { kind: 'guess' },
    ])
  })
})

describe('matchRoleLine', () => {
  const lines = [{ quote: 'SQL의 언어를 자유롭게 다룰 수 있는 분이 필요해요.' }, { quote: 'Hadoop-Ecosystem 환경의 데이터처리 기술 활용 경험이 있으면 더 좋아요.' }]
  it('글머리표·공백·문장부호가 달라도 같은 줄로 본다', () => {
    expect(matchRoleLine(lines, '- SQL의 언어를  자유롭게 다룰 수 있는 분이 필요해요')).toBe(lines[0])
  })
  it('짧거나 다른 줄은 맞추지 않는다', () => {
    expect(matchRoleLine(lines, '- SQL')).toBeUndefined()
    expect(matchRoleLine(lines, '- Kubernetes 운영 경험이 있으면 좋아요')).toBeUndefined()
  })
})
