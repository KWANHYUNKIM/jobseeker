import { describe, expect, it } from 'vitest'
import { parseJdText } from './jdText'

describe('parseJdText', () => {
  it('글머리표 없는 줄은 줄마다 항목, 구분선은 버린다', () => {
    const b = parseJdText('시스템 고도화 추진\n라이프사이클 관리\n------------')
    expect(b).toEqual([
      { kind: 'item', text: '시스템 고도화 추진', depth: 0 },
      { kind: 'item', text: '라이프사이클 관리', depth: 0 },
    ])
  })

  it('[소제목] 은 heading, 글머리표는 떼어 낸다', () => {
    const b = parseJdText('・ 우대합니다.\n[주의사항]\n・ 허위사실은 취소\n・ 조기마감 가능')
    expect(b.map((x) => x.kind)).toEqual(['item', 'heading', 'item', 'item'])
    expect(b[1]).toEqual({ kind: 'heading', text: '주의사항' })
    expect(b[2]).toMatchObject({ text: '허위사실은 취소', depth: 0 })
  })

  it('다른 글머리표는 하위 항목이다', () => {
    const b = parseJdText('• 백엔드 개발\n - API 설계\n - 운영\n• 인프라')
    expect(b.map((x) => (x.kind === 'item' ? x.depth : -1))).toEqual([0, 1, 1, 0])
  })

  it('숫자 목록과 ※ 안내', () => {
    const b = parseJdText('1. 첫째\n2) 둘째\n※ 경력 3년 이상')
    expect(b).toEqual([
      { kind: 'item', text: '첫째', depth: 0 },
      { kind: 'item', text: '둘째', depth: 0 },
      { kind: 'note', text: '경력 3년 이상' },
    ])
  })

  it('버전 숫자(3.5)는 번호로 보지 않는다', () => {
    const b = parseJdText('- 하나\n3.5년 이상 경력')
    expect(b[1]).toEqual({ kind: 'para', text: '3.5년 이상 경력' })
  })

  it('항목 하나뿐이면 문단', () => {
    expect(parseJdText('한 줄짜리 설명입니다')).toEqual([
      { kind: 'para', text: '한 줄짜리 설명입니다' },
    ])
  })
})
