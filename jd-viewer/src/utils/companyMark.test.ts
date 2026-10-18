import { describe, expect, it } from 'vitest'
import { safeLogoUrl } from './companyMark'

describe('safeLogoUrl — 바깥에서 긁어 온 로고 주소 거르기', () => {
  it('허용한 호스트의 https 만', () => {
    expect(safeLogoUrl('https://board.catch.co.kr/Upload/Job/Company/CI/380954.jpg')).toBe(
      'https://board.catch.co.kr/Upload/Job/Company/CI/380954.jpg',
    )
    expect(safeLogoUrl('https://cdn.jumpit.co.kr/images/a.png')).not.toBeNull()
  })
  it('스킴이 다르면 버린다', () => {
    expect(safeLogoUrl('javascript:alert(1)')).toBeNull()
    expect(safeLogoUrl('data:image/svg+xml,<svg onload=alert(1)>')).toBeNull()
    expect(safeLogoUrl('http://board.catch.co.kr/x.jpg')).toBeNull()
  })
  it('다른 호스트·호스트 흉내는 버린다', () => {
    expect(safeLogoUrl('https://evil.example/x.png')).toBeNull()
    expect(safeLogoUrl('https://board.catch.co.kr.evil.example/x.png')).toBeNull()
    expect(safeLogoUrl('https://evil.example/?board.catch.co.kr')).toBeNull()
  })
  it('비었거나 너무 길면 버린다', () => {
    expect(safeLogoUrl(null)).toBeNull()
    expect(safeLogoUrl('https://cdn.jumpit.co.kr/' + 'a'.repeat(600))).toBeNull()
  })
})
