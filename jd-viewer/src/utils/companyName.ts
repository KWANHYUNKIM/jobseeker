/**
 * 화면에 적을 회사 이름 — 법인 표기를 뗀다('(주)펄어비스' → '펄어비스', '주식회사 카카오' → '카카오').
 * 목록에서는 이름만 읽히고, 붙어 있으면 같은 회사가 다른 회사처럼 보인다. 데이터는 그대로 둔다.
 */
export function plainCompany(name: string): string {
  return name.replace(/\(주\)|㈜|주식회사/g, '').trim() || name
}
