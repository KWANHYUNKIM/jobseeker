/**
 * 공고의 근무지 문자열 → 지역(시도) / 시군구.
 *
 * 사이트마다 표기가 제각각이다: '서울강남구' '서울 강남구' '경기성남시 분당구'
 * '세종특별자치시' 'San Francisco, CA' '교육생 | 서울 송파구'. 필터가 서려면
 * 이 잡음을 17개 시도 + 해외·원격 + 정보없음으로 접어야 한다.
 *
 * 경력(careerBucket)과 같은 방식으로 화면에서 계산한다 — 원본 문자열은 데이터에
 * 그대로 남기고, 접는 규칙만 여기 한 곳에서 고친다.
 */

export const REGIONS = [
  '서울', '경기', '인천', '부산', '대구', '광주', '대전', '울산', '세종',
  '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
] as const

export const OVERSEAS = '해외·원격'
export const UNKNOWN_REGION = '정보없음'

/** 필터 칩 순서 — 시도 다음에 해외, 마지막이 정보없음. */
export const REGION_OPTIONS: string[] = [...REGIONS, OVERSEAS, UNKNOWN_REGION]

// 시도 뒤에 붙는 시군구. '경기성남시 분당구' 는 '성남시'(첫 시/군/구)까지만 본다 —
// 그 아래까지 쪼개면 칩이 수백 개가 되고, 통근 판단에는 시 단위면 충분하다.
const DISTRICT = /^\s*([가-힣]+?(?:시|군|구))/
const ADMIN_SUFFIX = /특별|광역|자치/

// 정식 명칭도 들어온다(잡코리아 JSON-LD 는 '대한민국 서울특별시 …' 로 준다).
const LONG_SIDO: Record<string, (typeof REGIONS)[number]> = {
  서울특별시: '서울', 부산광역시: '부산', 대구광역시: '대구', 인천광역시: '인천',
  광주광역시: '광주', 대전광역시: '대전', 울산광역시: '울산', 세종특별자치시: '세종',
  경기도: '경기', 강원특별자치도: '강원', 강원도: '강원',
  충청북도: '충북', 충청남도: '충남', 전라북도: '전북', 전북특별자치도: '전북',
  전라남도: '전남', 경상북도: '경북', 경상남도: '경남',
  제주특별자치도: '제주', 제주도: '제주',
}

// 한글로 적힌 해외 근무지. 사람인의 '일본 | 6,000 만원', 잡코리아 백필이 붙이는
// '해외 도쿄' 같은 값들이다. 도시 이름을 다 나열하는 대신 나라·대륙만 본다 —
// 백필이 국내 시도로 안 접히는 주소에 '해외' 를 붙여 주므로 도시는 그쪽에서 걸린다.
const FOREIGN = [
  '해외', '일본', '중국', '미국', '인도', '베트남', '싱가포르', '대만', '홍콩',
  '필리핀', '인도네시아', '태국', '말레이시아', '캄보디아', '캐나다', '호주',
  '독일', '영국', '프랑스', '아시아', '유럽', '북미', '중동', '아프리카',
]

// 영문 표기로 오는 국내 근무지(해외 보드·자체 채용페이지). 'Pangyo (Software
// Dream Center), South Korea' 같은 값을 해외로 세지 않기 위한 최소 목록이다.
const ROMANIZED: [RegExp, (typeof REGIONS)[number]][] = [
  [/seoul/i, '서울'],
  [/pangyo|seongnam|bundang/i, '경기'],
  [/busan/i, '부산'], [/incheon/i, '인천'], [/daejeon/i, '대전'],
  [/daegu/i, '대구'], [/gwangju/i, '광주'], [/ulsan/i, '울산'],
  [/sejong/i, '세종'], [/jeju/i, '제주'],
]

function matchRegion(text: string): (typeof REGIONS)[number] | null {
  for (const [long, short] of Object.entries(LONG_SIDO)) {
    if (text.startsWith(long)) return short
  }
  for (const r of REGIONS) {
    if (text.startsWith(r)) return r
  }
  return null
}

function isForeign(text: string): boolean {
  return FOREIGN.some((f) => text.startsWith(f))
}

/** '교육생 | 서울 송파구' 처럼 앞에 다른 정보가 붙은 표기를 위해 구분자로 나눠 본다. */
function segments(location: string): string[] {
  return location
    .split(/[|\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export interface Place {
  region: string
  district: string | null
}

export function placeOf(job: {
  location?: string
  overseas?: boolean
  site?: string
}): Place {
  if (job.overseas) return { region: OVERSEAS, district: null }
  const raw = (job.location || '').trim()
  if (!raw) return { region: UNKNOWN_REGION, district: null }

  // 국내 주소가 먼저다. '해외 도쿄' 같은 값은 시도로 안 접히므로 다음 단계로 넘어간다.
  const segs = segments(raw.replace(/^대한민국\s*/, ''))
  for (const seg of segs) {
    const region = matchRegion(seg)
    if (!region) continue
    const rest = seg.slice(seg.startsWith(region) ? region.length : 0)
    const m = DISTRICT.exec(rest)
    const district = m && !ADMIN_SUFFIX.test(m[1]) ? m[1] : null
    return { region, district }
  }
  if (segs.some(isForeign)) return { region: OVERSEAS, district: null }

  // 한글이 하나도 없으면 해외 보드/자체 채용페이지의 영문 주소다.
  if (!/[가-힣]/.test(raw)) {
    for (const [re, region] of ROMANIZED) {
      if (re.test(raw)) return { region, district: null }
    }
    if (/korea/i.test(raw)) return { region: UNKNOWN_REGION, district: null }
    return { region: OVERSEAS, district: null }
  }
  return { region: UNKNOWN_REGION, district: null }
}

export function regionOf(job: { location?: string; overseas?: boolean }): string {
  return placeOf(job).region
}

/** 지역 하나를 고른 뒤 보여줄 시군구 목록(건수 내림차순). */
export function districtCounts(
  jobs: { location?: string; overseas?: boolean }[],
  region: string,
): { name: string; count: number }[] {
  const c = new Map<string, number>()
  for (const j of jobs) {
    const p = placeOf(j)
    if (p.region !== region || !p.district) continue
    c.set(p.district, (c.get(p.district) ?? 0) + 1)
  }
  return [...c.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
}

export function regionCounts(
  jobs: { location?: string; overseas?: boolean }[],
): { name: string; count: number }[] {
  const c = new Map<string, number>()
  for (const j of jobs) {
    const r = regionOf(j)
    c.set(r, (c.get(r) ?? 0) + 1)
  }
  return REGION_OPTIONS.map((name) => ({ name, count: c.get(name) ?? 0 })).filter(
    (x) => x.count > 0,
  )
}
