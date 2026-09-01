// 회사 주소 슬러그 — 한글 회사 이름을 ASCII 주소로.
//
// 왜 .js 인가: 이 규칙을 브라우저(앱 라우팅)와 Node(scripts/prerender.mjs)가 똑같이
// 써야 한다. 둘 중 하나만 어긋나면 프리렌더한 주소와 앱이 만드는 주소가 갈라져
// 정적 HTML 이 통째로 안 잡힌다. 타입은 JSDoc 으로 붙여 TS 쪽에서도 그대로 읽힌다.
//
// 규칙은 셋, 위에서부터 먼저 맞는 것을 쓴다.
//  1. BRAND_SLUGS — 사람이 아는 영문 브랜드명. 로마자 변환은 브랜드명을 못 맞힌다
//     (쿠팡의 로마자는 kupang 이지만 회사가 쓰는 이름은 coupang 이다).
//  2. 한글 뒤에 영문 별칭이 붙은 norm(`엑스에이아이xai`, `포티투닷42dot`) → 영문 쪽.
//     company_stacks 가 `이름+영문별칭` 으로 norm 을 만들 때 생기는 형태다.
//  3. 국어의 로마자 표기법으로 음절을 그대로 옮긴다. 예쁘진 않지만 유일하고 안정적이다.

/**
 * 공고가 많은 회사부터 실제로 쓰는 영문 이름을 적어 둔다. 여기 없는 회사는 3번 규칙으로
 * 떨어진다 — 주소가 조금 투박해질 뿐 동작에는 문제가 없으니, 눈에 걸리는 회사가 생기면
 * 한 줄씩 추가하면 된다. 키는 company_stacks.json 의 `norm` 값 그대로.
 * @type {Record<string, string>}
 */
export const BRAND_SLUGS = {
  쿠팡: 'coupang',
  네이버: 'naver',
  네이버클라우드: 'naver-cloud',
  카카오: 'kakao',
  카카오뱅크: 'kakaobank',
  카카오페이: 'kakaopay',
  카카오모빌리티: 'kakaomobility',
  카카오헬스케어: 'kakao-healthcare',
  라인플러스: 'lineplus',
  우아한형제들: 'woowahan',
  당근마켓: 'daangn',
  비바리퍼블리카: 'toss',
  토스뱅크: 'tossbank',
  두나무: 'dunamu',
  빗썸: 'bithumb',
  핀다: 'finda',
  뱅크샐러드: 'banksalad',
  컬리: 'kurly',
  무신사: 'musinsa',
  야놀자: 'yanolja',
  직방: 'zigbang',
  버킷플레이스: 'bucketplace',
  쏘카: 'socar',
  리디: 'ridi',
  왓챠: 'watcha',
  사람인: 'saramin',
  잡코리아: 'jobkorea',
  원티드랩: 'wantedlab',
  넥슨: 'nexon',
  넷마블: 'netmarble',
  엔씨소프트: 'ncsoft',
  크래프톤: 'krafton',
  스마일게이트: 'smilegate',
  펄어비스: 'pearlabyss',
  컴투스: 'com2us',
  데브시스터즈: 'devsisters',
  삼성전자: 'samsung-electronics',
  현대자동차: 'hyundai-motor',
  lg유플러스: 'lg-uplus',
  한화에어로스페이스: 'hanwha-aerospace',
  한화시스템: 'hanwha-systems',
  메가존클라우드: 'megazonecloud',
  미리디: 'miridih',
  넛지헬스케어: 'nudge-healthcare',
  비상교육: 'visang',
  씨제이올리브영cj올리브영: 'cj-oliveyoung',
  업스테이지: 'upstage',
  커넥트웨이브: 'connectwave',
  솔트룩스: 'saltlux',
  이노션: 'innocean',
  티맵모빌리티: 'tmap-mobility',
  하이퍼커넥트: 'hyperconnect',
  몰로코: 'moloco',
  센드버드: 'sendbird',
  스포카: 'spoqa',
  엘리스: 'elice',
  애자일소다: 'agilesoda',
  플래티어: 'plateer',
  파이오링크: 'piolink',
  소만사: 'somansa',
  이지케어텍: 'ezcaretech',
  구글google: 'google',
}

// 국어의 roman 표기 — 초성·중성·종성 표.
// 음운 변화(자음 동화 등)는 반영하지 않는다. 주소는 읽히기만 하면 되고, 규칙이 단순할수록
// 같은 이름이 언제나 같은 주소로 떨어진다.
const CHO = ['g','kk','n','d','tt','r','m','b','pp','s','ss','','j','jj','ch','k','t','p','h']
const JUNG = ['a','ae','ya','yae','eo','e','yeo','ye','o','wa','wae','oe','yo','u','wo','we','wi','yu','eu','ui','i']
const JONG = ['','k','k','k','n','n','n','t','l','k','m','p','l','l','l','l','m','p','p','t','t','ng','t','t','k','t','p','t']

/**
 * 한글 음절을 로마자로 옮긴다. 한글이 아닌 글자는 그대로 흘려보낸다.
 * @param {string} text
 * @returns {string}
 */
export function romanize(text) {
  let out = ''
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0
    if (code >= 0xac00 && code <= 0xd7a3) {
      const i = code - 0xac00
      out += CHO[Math.floor(i / 588)] + JUNG[Math.floor((i % 588) / 28)] + JONG[i % 28]
    } else {
      out += ch
    }
  }
  return out
}

/** 주소에 쓸 수 있는 형태로 다듬는다(소문자 + [a-z0-9-]). */
function clean(s) {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

/**
 * 충돌 처리 전의 슬러그. 같은 이름은 언제나 같은 값이 나온다.
 * @param {string} norm company_stacks.json 의 norm
 * @returns {string}
 */
export function baseSlug(norm) {
  const brand = BRAND_SLUGS[norm]
  if (brand) return brand
  // `엑스에이아이xai` 처럼 한글 이름 뒤에 영문 별칭이 붙은 형태면 영문 쪽만 쓴다.
  const alias = /^[^a-z0-9]+([a-z0-9][a-z0-9]{2,})$/.exec(norm)
  if (alias) return clean(alias[1])
  return clean(romanize(norm)) || 'company'
}

/**
 * 회사 목록 전체에서 norm ↔ slug 대응을 만든다.
 *
 * 슬러그가 겹치면 뒤에 -2, -3 을 붙인다. 어느 쪽이 번호를 받는지가 데이터 순서에 따라
 * 흔들리면 주소가 배포마다 바뀌므로, 이름을 정렬해 놓고 앞에서부터 배정한다.
 * @param {string[]} norms
 * @returns {{ byNorm: Map<string, string>, bySlug: Map<string, string> }}
 */
export function buildCompanySlugs(norms) {
  const byNorm = new Map()
  const bySlug = new Map()
  for (const norm of [...norms].sort()) {
    const base = baseSlug(norm)
    let slug = base
    for (let n = 2; bySlug.has(slug); n++) slug = `${base}-${n}`
    byNorm.set(norm, slug)
    bySlug.set(slug, norm)
  }
  return { byNorm, bySlug }
}
