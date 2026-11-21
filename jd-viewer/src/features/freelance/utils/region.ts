/**
 * 외주 프로젝트의 근무지 → 시/도·시/군/구.
 *
 * 채용 공고의 규칙(features/jobs/utils/region.ts 의 placeOf)을 먼저 쓴다. 외주는 그 위에 잡음이
 * 하나 더 있다 — 에이전시가 시/도를 빼고 동네·역 이름만 적는다('가산디지털단지, 금천구'
 * '을지로입구, 명동' '판교, 성남시' '기흥'). placeOf 가 못 접은 것은 아래 동네 사전으로 한 번 더 본다.
 * 근무지가 없는 원격 도급은 '원격' 으로 따로 센다(지역을 고를 이유가 없는 일감).
 */
import { placeOf, REGIONS, UNKNOWN_REGION, OVERSEAS } from '../../jobs/utils/region'

export const REMOTE = '원격(근무지 없음)'
/** 고르는 칸의 순서 — 시/도 다음에 원격·해외, 마지막이 정보없음. */
export const PROJECT_REGION_ORDER: string[] = [...REGIONS, REMOTE, OVERSEAS, UNKNOWN_REGION]

type Sido = (typeof REGIONS)[number]

// 시/도 없이 오는 이름. 위에서부터 먼저 맞는 것 — 구 이름이 동네보다 앞이다('영등포구, 양평' 은 서울).
const SEOUL_GU =
  /(강남|서초|송파|강동|영등포|마포|금천|구로|종로|용산|성동|광진|동대문|중랑|성북|강북|도봉|노원|은평|서대문|양천|동작|관악|강서)구?/
const AREAS: [RegExp, Sido][] = [
  [/가산|구디|구로디지털|을지로|명동|여의도|역삼|삼성동|선릉|상암|신길|문래|성수|마곡|가양|양재|충무로|광화문|시청역|서울역|잠실|대흥|매봉|신도림|논현|청담|숙대입구|남영|등촌|증미|삼성|종합운동장|수색|디지털미디어시티|석촌|몽촌토성|종각|둔촌|올림픽공원|가락시장|문정|봉은사|서울/, '서울'],
  [/판교|성남|분당|수내|정자|용인|기흥|수지|수원|광교|안양|평촌|과천|이천|김포|고양|일산|부천|광명|화성|동탄|평택|하남|의왕|군포|시흥|안산|파주|남양주|구리|오산|의정부|안성|야탑|이매/, '경기'],
  [/청라|송도|부평|영종|남동구|인천/, '인천'],
  [/해운대|센텀|부산/, '부산'],
  [/유성|둔산|대덕구|대전/, '대전'],
  [/광주/, '광주'],
  [/달성군|대구/, '대구'],
  [/아산|천안|당진|서산/, '충남'],
  [/청주|증평|음성|충주|진천/, '충북'],
  [/나주|여수|순천|목포/, '전남'],
  [/전주|익산|군산/, '전북'],
  [/포항|김천|구미|경주|안동/, '경북'],
  [/창원|김해|진주|거제|양산/, '경남'],
  [/춘천|원주|강릉/, '강원'],
  [/세종/, '세종'],
  [/울산/, '울산'],
  [/서귀포|제주/, '제주'],
]
const DISTRICT = /([가-힣]{1,4}(?:시|군|구))(?![가-힣])/

export interface ProjectPlace {
  region: string
  district: string | null
}

export function projectPlace(p: { location?: string | null; kind?: string }): ProjectPlace {
  const raw = (p.location ?? '').trim()
  if (!raw || /^(원격|재택|비대면|무관|협의)/.test(raw)) {
    return { region: p.kind === 'onsite' ? UNKNOWN_REGION : REMOTE, district: null }
  }
  const base = placeOf({ location: raw.replace(/^전남\s*(?=광주)/, '') })
  if (base.region !== UNKNOWN_REGION) return base
  const gu = SEOUL_GU.exec(raw)
  if (gu) return { region: '서울', district: `${gu[1]}구` }
  for (const [re, region] of AREAS) {
    if (re.test(raw)) {
      // 서울은 구 이름이 없으면 동네·역 이름뿐이라 구를 짐작하지 않는다('을지로입구' 의 '입구' 를 구로 읽던 것).
      const d = region === '서울' ? null : DISTRICT.exec(raw)
      return { region, district: d && !d[1].endsWith('입구') ? d[1] : null }
    }
  }
  if (/도쿄|오사카|뉴욕|런던|베를린|하노이|호치민|방콕|말레이시아|미국|일본/.test(raw)) return { region: OVERSEAS, district: null }
  return { region: UNKNOWN_REGION, district: null }
}

/** 지역별 건수 — 고르는 칸 순서대로, 0건은 뺀다. */
export function projectRegionCounts(projects: { location?: string | null; kind?: string }[]): [string, number][] {
  const c = new Map<string, number>()
  for (const p of projects) {
    const r = projectPlace(p).region
    c.set(r, (c.get(r) ?? 0) + 1)
  }
  return PROJECT_REGION_ORDER.filter((r) => c.has(r)).map((r) => [r, c.get(r) as number])
}

/** 시/도 하나 안의 시/군/구 건수(많은 순). */
export function projectDistrictCounts(
  projects: { location?: string | null; kind?: string }[],
  region: string,
): [string, number][] {
  const c = new Map<string, number>()
  for (const p of projects) {
    const pl = projectPlace(p)
    if (pl.region === region && pl.district) c.set(pl.district, (c.get(pl.district) ?? 0) + 1)
  }
  return [...c.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}
