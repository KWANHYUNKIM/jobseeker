// 회사 → 로고를 가져올 도메인.
//
// 공고에 나오는 회사는 2천 곳 가까이 되는데 크롤 데이터에는 로고도 홈페이지도
// 없다. 그래서 두 단계로 간다.
//   1) 여기 적힌 회사는 실제 로고를 파비콘에서 가져온다.
//   2) 나머지는 이름 첫 글자로 만든 마크를 쓴다 — 색은 이름에서 뽑으므로
//      같은 회사는 어디서 보든 같은 색이다.
//
// 이 표는 손으로 늘린다. 회사명이 공고마다 조금씩 다르게 적히므로(주식회사,
// (주), 영문 병기) 비교 전에 normalize() 로 껍데기를 벗긴다.
const DOMAIN: Record<string, string> = {
  '네이버': 'naver.com', 'NAVER': 'naver.com', '네이버클라우드': 'ncloud.com',
  '카카오': 'kakaocorp.com', '카카오페이': 'kakaopay.com', '카카오뱅크': 'kakaobank.com',
  '카카오엔터프라이즈': 'kakaoenterprise.com', '카카오모빌리티': 'kakaomobility.com',
  '쿠팡': 'coupang.com', '쿠팡페이': 'coupang.com', '토스': 'toss.im',
  '비바리퍼블리카': 'toss.im', '토스페이먼츠': 'tosspayments.com', '토스뱅크': 'tossbank.com',
  '우아한형제들': 'woowahan.com', '배달의민족': 'baemin.com',
  '당근': 'daangn.com', '당근마켓': 'daangn.com', '무신사': 'musinsa.com',
  '라인': 'linecorp.com', 'LINE': 'linecorp.com', '라인플러스': 'linecorp.com',
  '넥슨': 'nexon.com', '넥슨코리아': 'nexon.com', '엔씨소프트': 'ncsoft.com',
  '넷마블': 'netmarble.com', '크래프톤': 'krafton.com', '펄어비스': 'pearlabyss.com',
  '스마일게이트': 'smilegate.com', '컴투스': 'com2us.com', '더블유게임즈': 'doublegames.com',
  '삼성전자': 'samsung.com', '삼성SDS': 'samsungsds.com', '삼성물산': 'samsungcnt.com',
  'LG전자': 'lge.co.kr', 'LG유플러스': 'lguplus.com', 'LG CNS': 'lgcns.com',
  'SK텔레콤': 'sktelecom.com', 'SK하이닉스': 'skhynix.com', 'SK플래닛': 'skplanet.com',
  'KT': 'kt.com', 'KT DS': 'ktds.co.kr', '현대자동차': 'hyundai.com',
  '기아': 'kia.com', '포스코': 'posco.co.kr', '한화시스템': 'hanwhasystems.com',
  'CJ올리브영': 'oliveyoung.co.kr', 'CJ대한통운': 'cjlogistics.com', 'CJ ENM': 'cjenm.com',
  '11번가': '11st.co.kr', 'G마켓': 'gmarket.co.kr', '이베이코리아': 'gmarket.co.kr',
  '위메프': 'wemakeprice.com', '티몬': 'tmon.co.kr', 'SSG닷컴': 'ssg.com',
  '마켓컬리': 'kurly.com', '컬리': 'kurly.com', '오늘의집': 'ohou.se',
  '버킷플레이스': 'ohou.se', '야놀자': 'yanolja.com', '여기어때': 'goodchoice.kr',
  '직방': 'zigbang.com', '다방': 'dabangapp.com', '리디': 'ridi.com',
  '왓챠': 'watcha.com', '뱅크샐러드': 'banksalad.com', '핀다': 'finda.co.kr',
  '두나무': 'dunamu.com', '업비트': 'upbit.com', '빗썸': 'bithumb.com',
  '코인원': 'coinone.co.kr', '네이버페이': 'naverpay.com', '엔에이치엔': 'nhn.com',
  'NHN': 'nhn.com', '한글과컴퓨터': 'hancom.com', '안랩': 'ahnlab.com',
  '메가존클라우드': 'megazone.com', '베스핀글로벌': 'bespinglobal.com',
  '삼성증권': 'samsungpop.com', '미래에셋증권': 'miraeasset.com', '넥스트증권': 'nextsecurities.co.kr',
  '신한은행': 'shinhan.com', '국민은행': 'kbstar.com', '하나은행': 'kebhana.com',
  '토스증권': 'tossinvest.com', '카카오스타일': 'kakaostyle.com', '지그재그': 'zigzag.kr',
  '스타트업': '', // 자리 표시 — 이름이 이렇게 들어오면 로고를 찾지 않는다
}

/** 회사명에서 법인 표기·공백을 걷어낸다 — 같은 회사가 여러 표기로 들어오기 때문. */
export function normalizeCompany(name: string): string {
  return name
    .replace(/\((주|유|재|사)\)/g, '')
    .replace(/(주식회사|유한회사|주식회사)/g, '')
    .replace(/\s*\([^)]*\)\s*/g, '')
    .replace(/\s+/g, '')
    .trim()
}

const NORM: Record<string, string> = {}
for (const [k, v] of Object.entries(DOMAIN)) if (v) NORM[normalizeCompany(k)] = v

/** 그 회사의 로고 URL. 표에 없으면 null — 부르는 쪽이 글자 마크를 그린다. */
export function companyLogoUrl(name: string): string | null {
  const dom = NORM[normalizeCompany(name)]
  return dom ? `https://www.google.com/s2/favicons?domain=${dom}&sz=64` : null
}

// 이름에서 색을 뽑는다. 같은 회사는 어느 화면에서든 같은 색이라 눈이 기억한다.
const HUES = [210, 160, 275, 25, 340, 190, 45, 300, 130, 15]

export function companyMarkColor(name: string): string {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return `oklch(0.62 0.13 ${HUES[h % HUES.length]})`
}

/** 마크에 쓸 글자 — 한글은 첫 글자, 영문은 첫 글자를 대문자로. */
export function companyInitial(name: string): string {
  const n = normalizeCompany(name) || name
  return n.slice(0, 1).toUpperCase()
}
