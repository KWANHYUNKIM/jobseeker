import { describe, expect, it } from 'vitest'
import { companyLogoUrl, safeLogoUrl } from './companyMark'

describe('safeLogoUrl — 우리 서버에 둔 로고 파일만', () => {
  it('수집기가 둔 경로', () => {
    expect(safeLogoUrl('/logos/c/30f5c8d6e7008a50.png')).toBe('/logos/c/30f5c8d6e7008a50.png')
  })
  it('바깥 주소는 이제 쓰지 않는다', () => {
    expect(safeLogoUrl('https://board.catch.co.kr/Upload/Job/Company/CI/380954.jpg')).toBeNull()
    expect(safeLogoUrl('javascript:alert(1)')).toBeNull()
    expect(safeLogoUrl('//evil.example/logos/c/30f5c8d6e7008a50.png')).toBeNull()
  })
  it('다른 경로·형식은 버린다', () => {
    expect(safeLogoUrl('/logos/c/../../index.html')).toBeNull()
    expect(safeLogoUrl('/logos/c/30f5c8d6e7008a50.svg')).toBeNull()
    expect(safeLogoUrl(null)).toBeNull()
  })
})

describe('companyLogoUrl — 파비콘도 우리 서버에서', () => {
  it('표에 있는 회사는 /logos/d/<도메인>.png', () => {
    expect(companyLogoUrl('쿠팡 (Coupang)')).toBe('/logos/d/coupang.com.png')
  })
  it('표에 없으면 null', () => expect(companyLogoUrl('없는회사이름')).toBeNull())
})
