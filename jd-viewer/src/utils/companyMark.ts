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
  '스마일게이트': 'smilegate.com', '컴투스': 'com2us.com', '더블유게임즈': 'doubleugames.com',
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
  // ── 메인 화면 회사 카드(2026-10)용 — 공식 도메인을 확인한 큰 회사만 ──
  '포티투닷': '42dot.ai', '한화에어로스페이스': 'hanwhaaerospace.com', 'LG에너지솔루션': 'lgensol.com',
  '현대오토에버': 'hyundai-autoever.com', '신세계I&C': 'shinsegae-inc.com', '신세계아이앤씨': 'shinsegae-inc.com',
  '한화그룹': 'hanwha.com', 'CJ올리브네트웍스': 'cjolivenetworks.co.kr', '엔에이치엔클라우드': 'nhncloud.com',
  'NHN Cloud': 'nhncloud.com', 'NHN클라우드': 'nhncloud.com', '네오플': 'neople.co.kr', 'LINE Plus': 'linecorp.com',
  '카카오헬스케어': 'kakaohealthcare.com', '하이브': 'hybecorp.com', '카카오게임즈': 'kakaogames.com',
  '토스플레이스': 'tossplace.com', '현대카드': 'hyundaicard.com', '미래에셋자산운용': 'miraeasset.com',
  '한화비전': 'hanwhavision.com', '롯데카드': 'lottecard.co.kr', '네이버웹툰': 'webtoon.com',
  'NAVER WEBTOON': 'webtoon.com', '네이버랩스': 'naverlabs.com', 'NAVER LABS': 'naverlabs.com',
  'NAVER Cloud': 'ncloud.com', 'NH투자증권': 'nhqv.com', '두산그룹': 'doosan.com', '롯데케미칼': 'lottechem.com',
  'SK브로드밴드': 'skbroadband.com', '두산에너빌리티': 'doosanenerbility.com', 'KB국민은행': 'kbstar.com',
  'CJ제일제당': 'cj.co.kr', '현대캐피탈': 'hyundaicapital.com', '한국투자증권': 'truefriend.com', '업스테이지': 'upstage.ai',
  '노타': 'nota.ai', '솔트룩스': 'saltlux.com', '레인보우로보틱스': 'rainbow-robotics.com', '그라비티': 'gravity.co.kr',
  '이스트소프트': 'estsoft.com', '스캐터랩': 'scatterlab.co.kr', '쏘카': 'socar.kr', '위메이드': 'wemade.com',
  '이글루코퍼레이션': 'igloo.co.kr', '팀스파르타': 'spartacodingclub.kr', '텔레칩스': 'telechips.com', '루닛': 'lunit.io',
  '리벨리온': 'rebellions.ai', '카페24': 'cafe24.com', '뷰노': 'vuno.co', '크몽': 'kmong.com',
  '사람인에이치에스': 'saramin.co.kr', '현대자동차그룹': 'hyundai.com', 'JYP엔터테인먼트': 'jype.com',
  '카카오페이증권': 'kakaopaysec.com', '토스인슈어런스': 'toss.im', '토스씨엑스': 'toss.im', '토스인컴': 'toss.im',
  '토스커뮤니티': 'toss.im', '당근페이': 'daangn.com', '넥슨커뮤니케이션즈': 'nexon.com', '넷마블컴퍼니': 'netmarble.com',
  '씨제이올리브영': 'oliveyoung.co.kr', '씨제이이엔엠': 'cjenm.com', 'CJ 4DPLEX': 'cj4dplex.com',
  'CJ포디플렉스': 'cj4dplex.com', '안진회계법인': 'deloitte.com', '한화시스템/ICT': 'hanwhasystems.com',
  '한화시스템/방산': 'hanwhasystems.com', '신한투자증권': 'shinhansec.com', '컬리 채용': 'kurly.com', '메가존': 'megazone.com',
  'LINE Financial Corp.': 'linecorp.com', 
  'NHN COMMERCE': 'nhn-commerce.com', 'NHN PAYCO': 'payco.com', '엔에이치엔페이코': 'payco.com',
  'SK(주) C&C': 'sk.com', 'SK(주) AX': 'sk.com', 'GS ITM': 'gsitm.com', 'KT 엔지니어링': 'kt.com',
  'kt alpha': 'kt.com', '롯데바이오로직스': 'lottebiologics.com', '에이플러스에셋어드바이저': 'aplusga.com',
  '유안타증권': 'myasset.com', '삼성서울병원': 'samsunghospital.com', '다우데이타': 'daoudata.co.kr',
  '지란지교소프트': 'jiransoft.co.kr', 
  // 해외 기업(해외 ATS 보드로 들어오는 글로벌 회사)
  'OpenAI': 'openai.com', 'SpaceX': 'spacex.com', 'Anthropic': 'anthropic.com',
  'Databricks': 'databricks.com', 'Okta': 'okta.com', 'Roblox': 'roblox.com', 'CoreWeave': 'coreweave.com',
  'Cerebras': 'cerebras.ai', 'Waymo': 'waymo.com', 'Stripe': 'stripe.com', 'Affirm': 'affirm.com',
  'Snowflake': 'snowflake.com', 'Coinbase': 'coinbase.com', 'Scale AI': 'scale.com',
  'Celonis': 'celonis.com', 'Reddit': 'reddit.com', 'Verkada': 'verkada.com', 'DoorDash': 'doordash.com',
  'Cloudflare': 'cloudflare.com', 'GitLab': 'gitlab.com', 'Robinhood': 'robinhood.com', 'Nuro': 'nuro.ai',
  'Cohere': 'cohere.com', 'Toast': 'toasttab.com', 'MongoDB': 'mongodb.com', 'Perplexity': 'perplexity.ai',
  'Sierra': 'sierra.ai', 'Pinterest': 'pinterest.com', 'Airbnb': 'airbnb.com', 'Harvey': 'harvey.ai',
  'Datadog': 'datadoghq.com', 'Samsara': 'samsara.com', 'Together AI': 'together.ai',
  'Lucid Motors': 'lucidmotors.com', 'Faire': 'faire.com', 'Chime': 'chime.com',
  'Kodiak Robotics': 'kodiak.ai', 'Motional': 'motional.com', 'Elastic': 'elastic.co',
  'Baseten': 'baseten.co', 'Ramp': 'ramp.com', 'Plaid': 'plaid.com', 'Spotify': 'spotify.com',
  'Block': 'block.xyz', 'Brex': 'brex.com', 'Justworks': 'justworks.com', 'Gusto': 'gusto.com',
  'Discord': 'discord.com', 'Lyft': 'lyft.com', 'Suno': 'suno.com', 'Deepgram': 'deepgram.com',
  'Figma': 'figma.com', 'Replit': 'replit.com', 'JetBrains': 'jetbrains.com', 'Asana': 'asana.com',
  'Match Group': 'mtch.com', 'Instacart': 'instacart.com', 'Docker': 'docker.com', 'Notion': 'notion.so',
  'Navan': 'navan.com', 'Fivetran': 'fivetran.com', 'Smartsheet': 'smartsheet.com', 'Twilio': 'twilio.com',
  'Scopely': 'scopely.com', 'Vanta': 'vanta.com', 'Gemini': 'gemini.com', 'Dragos': 'dragos.com',
  'Chainguard': 'chainguard.dev', 'N26': 'n26.com', 'Duolingo': 'duolingo.com', 'Flexport': 'flexport.com',
  'Anyscale': 'anyscale.com', 'Workato': 'workato.com', 'ElevenLabs': 'elevenlabs.io', 'Zopa': 'zopa.com',
  'LaunchDarkly': 'launchdarkly.com', 'Adyen': 'adyen.com', 'Mercury': 'mercury.com', 'Monzo': 'monzo.com',
  'Decagon': 'decagon.ai', '1Password': '1password.com', 'Gamma': 'gamma.app', 'Turing': 'turing.com',
  'Synthesia': 'synthesia.io', 'Character.AI': 'character.ai', '프렌들리에이아이': 'friendli.ai',
  'Censys': 'censys.com', 'Cognition': 'cognition.ai', 'Peloton': 'onepeloton.com', 'Factory': 'factory.ai',
  'Neo4j': 'neo4j.com', 'Recorded Future': 'recordedfuture.com', 'Starburst': 'starburst.io',
  'SeatGeek': 'seatgeek.com', 'Writer': 'writer.com', 'Cursor': 'cursor.com', 'Huntress': 'huntress.com',
  'Squarespace': 'squarespace.com', 'Bill.com': 'bill.com', 'KnowBe4': 'knowbe4.com',
  'Webflow': 'webflow.com', 'Qonto': 'qonto.com', 'Lambda': 'lambda.ai', 'Braintrust': 'braintrust.dev',
  'Calendly': 'calendly.com', 'Coursera': 'coursera.org', 'Dataiku': 'dataiku.com',
  'SingleStore': 'singlestore.com', 'Netradyne': 'netradyne.com', 'Udacity': 'udacity.com',
  'SoFi': 'sofi.com', 'Typeform': 'typeform.com', 'Axonius': 'axonius.com', 'Cribl': 'cribl.io',
  'JFrog': 'jfrog.com', 'Nextdoor': 'nextdoor.com', 'Mural': 'mural.co', 'Checkr': 'checkr.com',
  'Greenhouse': 'greenhouse.com', 'Buzzvil': 'buzzvil.com', 'Semgrep': 'semgrep.dev',
  'New Relic': 'newrelic.com', 'Carvana': 'carvana.com', 'Lightning AI': 'lightning.ai',
  'GoCardless': 'gocardless.com', 'ChargePoint': 'chargepoint.com', 'Paytm': 'paytm.com',
  'Astronomer': 'astronomer.io', 'Mindbody': 'mindbodyonline.com', 'Lemlist': 'lemlist.com',
  'Airbyte': 'airbyte.com', 'StockX': 'stockx.com', 'Synack': 'synack.com', 'ClassPass': 'classpass.com',
  'Krea': 'krea.ai', 'PostHog': 'posthog.com', 'CircleCI': 'circleci.com', 'Modal': 'modal.com',
  'Culture Amp': 'cultureamp.com', 'Photoroom': 'photoroom.com', 'Buildkite': 'buildkite.com',
  'Dropbox': 'dropbox.com', 'PagerDuty': 'pagerduty.com', 'Mixpanel': 'mixpanel.com', 'Fastly': 'fastly.com',
  'Dust': 'dust.tt', 'Planhat': 'planhat.com', 'Kavak': 'kavak.com', 'Twitch': 'twitch.tv',
  'Cybereason': 'cybereason.com', 'Recraft': 'recraft.ai', 'Lithic': 'lithic.com', 'Reka': 'reka.ai',
  'Gainsight': 'gainsight.com', 'Runway': 'runwayml.com', 'Jobandtalent': 'jobandtalent.com',
  'Yugabyte': 'yugabyte.com', 'Tavus': 'tavus.io', 'Bugcrowd': 'bugcrowd.com', 'Linear': 'linear.app',
  'Demandbase': 'demandbase.com', 'Mutiny': 'mutinyhq.com', 'OpusClip': 'opus.pro', 'Pika': 'pika.art',
  '스타트업': '', // 자리 표시 — 이름이 이렇게 들어오면 로고를 찾지 않는다
}

/**
 * 회사명에서 법인 표기·공백을 걷어낸다 — 같은 회사가 여러 표기로 들어오기 때문.
 *
 * NFKC 를 먼저 거는 것이 중요하다. `㈜`(U+321C)는 한 글자로 합쳐진 호환 문자라
 * 아래의 `(주)` 세 글자 규칙에 걸리지 않는다. 그래서 `㈜와탭랩스` 는 정규화해도
 * `㈜와탭랩스` 로 남고, 그 회사의 취업 브리핑과 로고가 화면에서 조용히 사라졌다.
 * NFKC 가 하는 일이 정확히 `㈜`→`(주)`, 전각→반각 같은 호환 문자의 통일이다.
 */
export function normalizeCompany(name: string): string {
  return name
    .normalize('NFKC')
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

/**
 * 바깥에서 긁어 온 로고 주소 중 화면에 띄워도 되는 것만 — https 이고 로고를 주는 걸 확인한 호스트.
 * DB(company.logo_url)는 수집기가 이미 거르지만, 화면도 한 번 더 막는다(수집기가 바뀌거나 DB 가
 * 손으로 고쳐져도 엉뚱한 주소가 <img> 로 가지 않게). 수집기의 허용 목록(crawl_logos.LOGO_HOSTS)과 같다.
 */
const LOGO_HOSTS = new Set(['board.catch.co.kr', 'cdn.jumpit.co.kr', 'static.wanted.co.kr'])

export function safeLogoUrl(url: string | null | undefined): string | null {
  if (!url || url.length > 500) return null
  try {
    const u = new URL(url)
    return u.protocol === 'https:' && LOGO_HOSTS.has(u.hostname) ? u.href : null
  } catch {
    return null
  }
}
