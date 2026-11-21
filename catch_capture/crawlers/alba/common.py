"""컴퓨터 알바 모음 — 출처들이 같이 쓰는 것: 분류 규칙·지역/급여 정리·공고 누적·마감 반영·잠금.

출처마다 다른 것(목록을 어디서 받나, 상세를 어떻게 읽나, 원본이 무엇을 마감이라 하나)은
출처 모듈(daangn·albacheonguk·albamon·saramin·jobkorea)에 있고, 여기 `Source` 를 이어받는다.
한 회차를 도는 순서는 `run_source` 하나로 같다 — 목록 → 1차 후보(제목) → 상세로 2차 판정 →
재확인(목록에서 사라진 것 → lastmod 바뀐 것 → 오래 안 물어본 모집중).

**요약과 링크만 싣는다.** 처음 당근알바(약관상 상업적 복제 금지)에서 정한 규칙을 출처 전부에
똑같이 쓴다 — 제목·급여·시/도·시/군/구·고용 형태·근무 시간·등록일·마감일·원문 주소·우리 분류.
본문·상호·담당자·연락처·번지는 저장하지 않는다(본문은 분류할 때 메모리에서만 읽는다).
알바몬 목록에는 담당자 휴대폰 번호가 그대로 실려 오는데, `make_post` 가 KEEP 칸만 옮기므로
닿을 길이 없다(tests/test_alba_sources.py 가 지킨다).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from core.paths import VAR_DIR, VIEWER_PUBLIC
from crawlers.jobs_common import USER_AGENT, jitter

OUT_PATH = VIEWER_PUBLIC / "alba.json"
STATE_PATH = VAR_DIR / "alba" / "state.json"
# 회차 안(crawl_all)과 회차 사이(launchd com.jobseeker.albacheck) 두 곳에서 돈다. 둘 다 alba.json 을
# 통째로 읽고 쓰므로 겹치면 늦게 끝난 쪽이 먼저 끝난 쪽의 마감 판정을 지운다 — 못 잡은 쪽이 건너뛴다.
LOCK_PATH = VAR_DIR / "alba" / "alba.lock"

# 분류 규칙을 넓히면 올린다 — 판이 바뀌면 출처마다 '아니다' 판정 기록(rejected)을 비우고 다시 본다.
# 2: 디자인(로고·편집·CAD·3D·보정·웹툰)·문서 작업까지(2026-11-21)
# 3: 채용 보드 제목(알바천국·알바몬·사람인·잡코리아)에 맞춰 QA·테스터·웹디·영상편집자 등을 더하고,
#    보드가 붙인 직종(프로그래머·웹디자인…)을 보조 신호로 쓴다(2026-11-21)
# 4: 맨 '디자이너'는 모호한 쪽(WEAK)으로 — 당근에서는 거의 헤어 디자이너였다. 헤어·미용·수선은 막는다.
#    판이 바뀌면 이미 실은 공고 중 제목이 이제 막히는 것은 지운다(run_source)(2026-11-21)
RULES_VERSION = 4
TIMEOUT = 25
HISTORY_MAX = 20
CONTENT_PEEK = 1500        # 분류에 쓰는 본문 앞부분(저장하지 않는다)
LISTING_MIN_RATIO = 0.5    # 끝까지 본 목록이 직전의 절반 밑이면 '사라짐'을 보류한다
GONE_LIMIT = 300           # 목록에서 사라진 공고는 따로 — 바로 묻는다
REJECTED_MAX = 20000       # 끝까지 못 보는 목록의 '아니다' 기록은 최근 것만 남긴다


# ── 분류 ──────────────────────────────────────────────────────────────
# 우리 분류(출처마다 다른 업직종 분류와 따로). 순서가 곧 우선순위다 — '코딩 가르쳐 주실 분'은 개발이 아니라 강사.
CATEGORIES = [
    "코딩·IT 강사",
    "웹·앱 제작",
    "개발·프로그래밍",
    "디자인·영상",
    "홈페이지·쇼핑몰 운영",
    "데이터·사무자동화",
    "PC·기기 지원",
]

_E = r"(?<![a-z])"        # 영어 낱말 경계(한글 옆에 붙어 있어도 된다)
_Z = r"(?![a-z])"
_CODING = r"(?<![레인])코딩"   # '홈레코딩'·'인코딩'

TEACH_TOPIC = re.compile(
    rf"{_CODING}|프로그래밍|파이썬|{_E}python{_Z}|{_E}java{_Z}|자바(?!칩|라)|c언어|{_E}c\+\+|스크래치|엔트리|아두이노|{_E}plc{_Z}|디지털\s*포렌식|"
    rf"{_E}unity{_Z}|유니티|{_E}ai{_Z}|인공지능|챗\s*gpt|{_E}gpt{_Z}|클로드|컴퓨터|컴활|엑셀|{_E}excel{_Z}|"
    rf"파워\s*포인트|{_E}ppt{_Z}|{_E}oa{_Z}|{_E}it{_Z}|"
    rf"{_E}cad{_Z}|캐드|스케치업|라이노|포토샵|일러스트레이터|프리미어|{_E}3d{_Z}|모델링|클립\s*스튜디오|캔바|디지털\s*드로잉|"
    rf"사진\s*(?:편집|보정)|영상\s*편집|{_E}gtq{_Z}")
# 3판: '교육'·'강의'·'수업'만으로는 강사로 보지 않는다 — 보드 제목에는 회사명('디딤돌교육')·'강의 영상 편집'·
# '수업 모니터링'·'교육기관 컴퓨터 유지보수'가 흔했다. '수업 해 주실'처럼 가르치는 일일 때만 센다.
TEACH_ACT = re.compile(r"강사|선생님|쌤|과외|교사|가르쳐|가르치|가르칠|배우|배울|레슨|교습|튜터|멘토|알려\s*주|코칭|"
                       r"(?:수업|강의|교육)\s*(?:해|진행|하실|가능|맡)")

WEBAPP = re.compile(
    r"(?:홈\s*페이지|웹\s*사이트|사이트|웹\s*페이지|랜딩\s*페이지|웹|앱|어플|워드\s*프레스|아임웹|카페24|자사몰|쇼핑몰|플랫폼)"
    r"(?:을|를|의|좀)?\s*(?:제작|개발|만들|만드|구축|리뉴얼|수정|변경|퍼블리싱|코딩|외주)"
    r"|퍼블리셔|웹\s*퍼블")
DEV = re.compile(
    rf"개발자|프로그래머|프로그래밍|{_CODING}|파이썬|{_E}python{_Z}|자바\s*스크립트|{_E}javascript{_Z}|"
    rf"{_E}java{_Z}|자바(?!칩|라)|{_E}react{_Z}|리액트|(?<!팅)플러터|{_E}flutter{_Z}|{_E}unity{_Z}|유니티|언리얼|"
    rf"백엔드|프론트\s*엔드|서버\s*개발|{_E}aws{_Z}|클라우드|크롤링|크롤러|스크래핑|{_E}api{_Z}|매크로|"
    rf"{_E}sw{_Z}|소프트웨어\s*개발|임베디드|펌웨어|아두이노|라즈베리|졸업\s*작품|프로그램\s*(?:개발|제작|만들|설정|수정)|"
    rf"게임\s*개발|{_E}it\s*개발|데이터\s*베이스|{_E}sql{_Z}|챗봇|{_E}ai\s*(?:개발|에이전트|모델)|"
    rf"머신\s*러닝|딥\s*러닝|{_E}rag{_Z}|개발\s*(?:알바|외주|프리랜서|보조)|"
    # 3판 — 보드 공고는 제목이 직무명이다('웹개발', 'PHP 개발자', '소프트웨어 기능 테스트(QA)').
    rf"(?:웹|앱|시스템|소프트웨어|{_E}sw|게임)\s*개발|{_E}php{_Z}|{_E}asp{_Z}|풀\s*스택|"
    rf"{_E}qa{_Z}|테스터|(?:소프트웨어|{_E}sw|앱|어플|모바일|게임|기능)\s*\S{{0,6}}?테스트|"
    rf"{_E}db\s*(?:검수|구축|관리)|{_E}dba{_Z}|정보\s*보안|보안\s*관제|네트워크\s*엔지니어|{_E}it\s*헬프\s*데스크|헬프\s*데스크|{_E}help\s*desk|"
    rf"{_E}it\s*(?:엔지니어|engineer|경력|cabling|케이블링|지원|운영|인프라|총무)|서버\s*(?:구축|관리|운영|엔지니어)")
DESIGN = re.compile(
    rf"웹\s*디자인|웹디|{_E}ui{_Z}|{_E}ux{_Z}|ux\s*ui|ui\s*ux|{_E}cg{_Z}|피그마|{_E}figma{_Z}|포토샵|포샵|포샾|일러스트레이터|상세\s*페이지|썸네일|"
    rf"배너\s*디자인|(?<!신문)편집자|프리미어\s*프로|어도비|애프터\s*이펙트|캡컷|모션\s*그래픽|{_E}3d{_Z}(?!\s*(?:세그멘테이션|데이터|라벨))|블렌더|"
    rf"(?:웹|{_E}ui|{_E}ux|그래픽|편집|시각|영상|콘텐츠|컨텐츠|상세|쇼핑몰|온라인|브랜드|디지털)\s*디자이너|"
    rf"(?:영상|유튜브|유트브|쇼츠|숏폼|릴스|동영상|컷)\S*\s*(?:\S+\s+){{0,3}}?\S*편집|"
    rf"(?:영상|숏츠|쇼츠|{_E}shorts{_Z}|숏폼|클립)\s*(?:제작|만들|만드|작업)|(?:영상|유튜브)\s*(?:콘텐츠\s*)?pd|"
    rf"(?:강의|교육|이러닝)\s*(?:영상\s*)?편집|인코딩|"
    rf"로고\s*(?:디자인|제작|작업|만들)|(?:그래픽|편집|시각|브랜드|패키지|포스터|전단지?|명함|카드\s*뉴스|인스타|{_E}sns|"
    rf"배너|현수막|메뉴판|굿즈|브로셔|리플렛|책자|표지|피피티|{_E}ppt|콘텐츠|컨텐츠|모바일|{_E}pop|출판|시안|광고|간판|홍보물|인쇄물?|제품|북)\s*디자인|카드\s*뉴스|캔바|{_E}canva{_Z}|미리\s*캔버스|"
    rf"{_E}cad{_Z}|캐드|오토\s*캐드|스케치업|라이노|{_E}rhino{_Z}|3d\s*(?:모델링|프린팅|스캔|작업)|모델링\s*(?:작업|외주|리소스)|렌더링|"
    rf"사진\s*(?:보정|리터칭|편집)|리터칭|누끼|웹툰\s*(?:어시|채색|배경|작업)|클립\s*스튜디오|인디자인|"
    rf"디지털\s*(?:드로잉|일러스트|작화)|일러스트\s*(?:작업|외주|제작|그려)|자막\s*(?:작업|제작|번역)|"
    # 3판 — 보드에는 '디자인 아르바이트'처럼 직무만 적은 제목이 많다. 헤어·인테리어·패션처럼 컴퓨터 일이 아닌
    # 것은 NON_IT 가 먼저 막는다. 맨 '디자이너 모집'은 4판부터 WEAK — 당근에서는 거의 헤어 디자이너였다.
    # 보드는 직종(그래픽·편집디자인…)이나 본문으로 다시 건진다.
    rf"(?:광고|모션|일러스트|산업|패키지|인쇄물?|사인물|출판|옥외\s*광고)\s*\S{{0,3}}?디자이너|"
    rf"디자인\s*(?:보조|알바|아르바이트|업무|작업|직원|팀|담당|채용|모집|외주|전문가|어시)")
OPS = re.compile(
    r"(?:홈\s*페이지|블로그|스마트\s*스토어|쇼핑몰|자사몰|오픈\s*마켓|네이버\s*스토어|카페24|아마존|쇼피|큐텐|플레이오토|사방넷|"
    r"웹\s*사이트|사이트|어플|앱)"
    r"[^\n]{0,20}?(?:관리|운영|등록|업로드|올리|세팅|셋팅|사용|{seo}|상위\s*노출)".replace("{seo}", rf"{_E}seo{_Z}"))
DATA = re.compile(
    rf"(?:엑셀|{_E}excel{_Z}|스프레드\s*시트|구글\s*시트)\s*\S{{0,3}}?\s*(?:작업|정리|자동화|함수|매크로|데이터|문서|입력|만들|작성)|"
    rf"{_E}vba{_Z}|업무\s*자동화|사무\s*자동화|자동화\s*(?:{_E}ai{_Z}|프로그램)|"
    rf"(?:{_E}ai|{_E}gpt|챗\s*gpt|클로드)\s*(?:활용|자동화)|데이터\s*(?:입력|정리|수집|라벨링|분석|작업|파일|가공|검수)|"
    rf"라벨링|라벨러|전산\s*입력|노션|{_E}ppt\s*제작|파워\s*포인트\s*제작|"
    rf"타이핑|문서\s*(?:작업|작성|편집)|한글\s*(?:문서|파일|편집)|바운딩\s*박스|어노테이션|어노테이터|{_E}annotation|{_E}hwp{_Z}|{_E}pdf\s*(?:편집|변환|작업)|녹취\s*(?:록|작업)?|"
    rf"디지털화|{_E}db\s*입력")
PC = re.compile(
    rf"(?:컴퓨터|컴터|{_E}pc{_Z}|노트북|맥북|공유기|와이파이|{_E}wifi{_Z}|네트워크|인터넷|{_E}cctv{_Z}|프린터|모니터|윈도우|"
    rf"{_E}nas{_Z}|하드|갤럭시|아이폰|스마트폰|태블릿|전산\s*장비)"
    rf"[^\n]{{0,12}}?(?:조립|수리|설치|연결|세팅|셋팅|교체|선\s*정리|{_E}as{_Z}|포맷|복구|업그레이드|문제|해결|견적|깔아|"
    rf"봐\s*주|잘\s*(?:하시|아시|다루)|점검|고쳐|고치|복원|백업|옮기|설정|배선|살려|유지\s*보수|장애|오류)|데이터\s*복구")

# 현장 일 — 제목에 있으면 IT 공고가 아니다(쇼핑몰 '포장' 알바, 자동화 '설비', 웹툰 '모델'…).
NON_IT = re.compile(
    rf"서빙|써빙|홀\s*(?:직원|알바|파트|매니저)|주방|설거지|조리|택배|포장|물류|창고|피킹|패킹|입출고|재고|배달|"
    rf"청소|미화|지게차|생산직|공장|설비|조립\s*(?:원|인원|직원)|기구\s*조립|부품|판매|매장\s*(?:관리|직원)|"
    rf"{_E}cs{_Z}|상담|콜센터|{_E}md{_Z}|모델(?!링)|출연|마케터|마케팅|영업|홍보|체험단|참가자|운전|배송|진열|스팀|"
    rf"경리|회계|세무|간호|요양|보육|시터|화물|현장|라이더|식당|매장|고객\s*응대|춤|댄스|엑셀\s*방송|"
    rf"(?<=[가-힣a-z])pc{_Z}|pc\s*(?:방|카페|아레나)|피시방|자동화\s*(?:설비|장비|레일|set)|"
    # 3판 — 보드 IT 분류에 섞여 오는 광고·교육생 모집·현장 일(국비 과정, 로봇 데이터수집, 반도체 장비).
    rf"국비|교육생|수강생|훈련생|취업\s*연계|무료\s*교육|로봇|모션\s*캡[쳐처]|반도체|육안\s*점검|검사원|"
    rf"사무\s*보조|전화\s*안내|안내\s*데스크|리셉션|{_E}bj{_Z}|크리에이터\s*(?:신규|모집)|인테리어\s*(?:디자이너|시공)|"
    rf"(?:의류|패션|니트|가방|무대\s*의상|의상|잡화|섬유|헤어|네일|플라워|메이크업|속눈썹|두피|웨딩|가구|조경|"
    rf"주얼리|공간|실내|인테리어|건축|미용|무대|세트)\s*(?:\S{{0,4}}\s*)?디자(?:인|이너)|실사\s*출력|시공|가죽|공예|"
    rf"대리점|사진관|헤어|미용실|네일|왁싱|속눈썹|반영구|콘택트\s*렌즈|안경|리폼|수선|재봉|미싱|인턴\s*디자이너|"
    rf"단순\s*데이터\s*수집|데이터\s*수집\s*(?:보조|어시스턴트|오퍼레이터|야간)|참여자|신체|상차|하차|철수|운반|"
    rf"전화\s*(?:아르바이트|알바|업무|상담)|텔레마케팅|아웃바운드|인바운드|생산\s*(?:직|계약직|사원|관리)|제조|"
    rf"품질\s*(?:관리|검사)|{_E}haccp{_Z}|해썹|"
    rf"피팅|세공|공방|원데이\s*클래스|미술\s*학원|부업|재택\s*부업|투잡|바이럴|{_E}sns\s*(?:관리|마케팅|운영)|"
    rf"오퍼레이터|기능공|기사님")
# 이건 STRONG 이 있어도 IT 공고가 아니다 — 차량 '코딩'(BMW·카플레이 설정)은 소프트웨어 일이 아니다.
# 국비 과정·교육생 모집은 '개발자'가 제목에 있어도 일자리가 아니라 학원 광고다.
HARD_NON_IT = re.compile(
    r"{b}bmw|벤츠|아우디|클럽맨|카플레이|안드로이드\s*오토|(?:차량|자동차)\s*\S{0,4}?(?:코딩|정비|수리|세차|부품|탁송|도장)|"
    r"국비|교육생|수강생|훈련생|취업\s*연계\s*(?:교육|과정)|입학\s*상담|양성\s*과정|부트\s*캠프".replace("{b}", _E))
# 현장 일 낱말이 있어도 IT 일이 분명한 것(‘쇼핑몰 MD 겸 웹디자이너’, ‘유튜브 촬영 및 편집’).
STRONG = re.compile(
    rf"개발자|프로그래머|{_CODING}|웹\s*디자이너|웹디|홈\s*페이지\s*(?:제작|개발)|웹\s*사이트\s*제작|앱\s*개발|"
    rf"영상\s*편집|편집자|컴퓨터\s*(?:수리|조립)|3d\s*모델링|모델링\s*(?:작업|외주)|{_E}cad{_Z}|캐드|스케치업|"
    rf"로고\s*디자인|사진\s*(?:보정|리터칭)|웹툰\s*(?:어시|채색)|상세\s*페이지\s*(?:제작|디자인|작업|편집|디자이너)|포토샵|일러스트레이터")
# 촬영만 하는 일은 IT 가 아니다 — 편집이 같이 있으면 STRONG/DESIGN 이 건진다.
SHOOT_ONLY = re.compile(r"촬영(?!.*편집)")
# 제목만으로 모호한 것 — 이게 있으면 상세 본문까지 보고 판정한다.
# 온라인·인터넷·디지털·전산·프로그램은 뺐다 — '온라인 쇼핑몰 정직원', '약국 전산업무', '시니어 프로그램 강사'처럼
# 본문까지 봐도 IT 일이 아닌 것이 대부분이었다(2026-11-21 첫 수집).
WEAK = re.compile(
    rf"컴퓨터|{_E}(?:it|ai|pc|sns){_Z}|엑셀|유튜브|데이터|자동화|웹(?!소설|툰)|앱|코딩|홈\s*페이지|디자인|디자이너")

_RULES = [
    ("코딩·IT 강사", lambda t: bool(TEACH_TOPIC.search(t) and TEACH_ACT.search(t))),
    ("웹·앱 제작", lambda t: bool(WEBAPP.search(t)) and not re.search(r"상세\s*페이지", t)),
    ("개발·프로그래밍", lambda t: bool(DEV.search(t))),
    ("디자인·영상", lambda t: bool(DESIGN.search(t))),
    ("홈페이지·쇼핑몰 운영", lambda t: bool(OPS.search(t))),
    ("데이터·사무자동화", lambda t: bool(DATA.search(t))),
    ("PC·기기 지원", lambda t: bool(PC.search(t))),
]

# 보드가 붙인 직종(알바몬 parts·알바천국 모집직종·사람인 직무 태그). 제목 규칙이 못 정했을 때만 쓴다.
# 공고가 단 직종이 **전부** 이 표 안에 있고, 그중 하나라도 '강한' 것(값이 있는 것)일 때만 그 분류로 정한다 —
# 보드 IT 분류에는 상담·사무 공고가 '사이트관리'만 달고 섞여 온다(2026-11-21 알바천국 IT·인터넷 목록).
# 표의 순서가 우선순위다 — 'HTML코딩'은 보안 관제·QA 공고에도 덤으로 붙어 와서 뒤에 둔다.
BOARD_PARTS: dict[str, str | None] = {
    "프로그래머": "개발·프로그래밍", "QA·테스터·검증": "개발·프로그래밍", "시스템·네트워크·보안": "개발·프로그래밍",
    "웹·모바일디자인": "디자인·영상", "캐릭터·애니메이션디자인": "디자인·영상", "HTML코딩": "웹·앱 제작",
    "PC·디지털기기 설치·관리": "PC·기기 지원",
    "웹·모바일 기획": None, "웹·콘텐츠기획": None, "사이트관리·기술지원": None, "사이트·쇼핑몰운영": None,
    "그래픽·영상·편집디자인": "디자인·영상", "동영상촬영·편집": None, "데이터수집·가공": None,
    "CAD·CAM·인테리어디자인": None, "컴퓨터·정보통신": None, "IT·인터넷 기타": None,
}


def norm(text: str) -> str:
    """소문자, 하이픈·문장부호는 띄어쓰기로. 슬러그('홈페이지-제작')와 제목을 같은 규칙으로 본다."""
    t = (text or "").lower().replace("&amp;", " ")
    t = re.sub(r"[-_/|·,()\[\]{}!?~★☆♥※*\"'“”‘’:;.#<>【】「」『』ㅣ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _rules(t: str, skip: tuple[str, ...] = ()) -> str | None:
    for name, ok in _RULES:
        if name not in skip and ok(t):
            return name
    return None


def _vetoed(t: str) -> bool:
    if HARD_NON_IT.search(t):
        return True
    return bool((NON_IT.search(t) or SHOOT_ONLY.search(t)) and not STRONG.search(t))


def _board(parts) -> str | None:
    parts = [p for p in (parts or ()) if p]
    if not parts or any(p not in BOARD_PARTS for p in parts):
        return None
    return next((cat for name, cat in BOARD_PARTS.items() if cat and name in parts), None)


def classify(title: str, content: str = "", parts=()) -> str | None:
    """우리 분류 하나, 컴퓨터 일이 아니면 None. 본문은 제목이 모호할 때만 보고 저장하지 않는다.

    parts 는 보드가 붙인 직종 이름들 — 제목이 못 정하면 `_board` 규칙으로 한 번 더 본다.
    """
    t = norm(title)
    if _vetoed(t):
        return None
    cat = _rules(t) or _board(parts)
    if cat or not content or not WEAK.search(t):
        return cat
    # 본문에서는 '강사' 판정을 하지 않는다 — '교육'·'선생님'은 어느 공고 본문에나 있다.
    return _rules(norm(content[:CONTENT_PEEK]), skip=("코딩·IT 강사",))


def is_candidate(title: str, parts=()) -> bool:
    """1차(목록 제목만) — 상세를 받아 볼 만한가."""
    t = norm(title)
    if _vetoed(t):
        return False
    return bool(_rules(t) or _board(parts) or WEAK.search(t))


# ── 지역·급여 ─────────────────────────────────────────────────────────
SIDO = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
    "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원도": "강원",
    "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남", "전남광주통합특별시": "광주·전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
    # 보드 표기(줄임·통합시 표기)
    "전남광주": "광주·전남", "세종시": "세종", "제주도": "제주",
}
SHORT_SIDO = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남",
              "전북", "전남", "경북", "경남", "제주"}


def sido_name(raw: str) -> str:
    raw = (raw or "").strip()
    return SIDO.get(raw, raw)


def split_region(addr: str) -> tuple[str, str]:
    """'경기 화성시 만세구 …' → ('경기', '화성시 만세구'). 번지·도로명은 버린다(시/군/구까지만).

    시/도를 못 알아보면 ('', '').
    """
    toks = (addr or "").replace(",", " ").split()
    if not toks:
        return "", ""
    sido = sido_name(toks[0])
    if sido not in SHORT_SIDO and sido != "광주·전남":
        return "", ""
    out = []
    for tok in toks[1:3]:
        if re.fullmatch(r"[가-힣]+(?:시|군|구)", tok) and tok not in ("전체",):
            out.append(tok)
            if not tok.endswith("시"):          # 'OO시 OO구' 까지만 붙인다
                break
        else:
            break
    return sido, " ".join(out)


PAY_UNIT_EN = {"HOUR": "시급", "DAY": "일급", "WEEK": "주급", "MONTH": "월급", "YEAR": "연봉"}


def pay_obj(amount, unit: str, text: str = "") -> dict | None:
    """급여 칸 하나의 모양 — 금액이 없으면 None(화면이 '급여 협의'나 '원문 확인'으로 보인다)."""
    try:
        amount = int(float(str(amount).replace(",", ""))) if amount not in (None, "") else None
    except ValueError:
        amount = None
    if not amount:
        return None
    return {"amount": amount, "unit": unit or "", "text": text or f"{unit} {amount:,}원".strip()}


# ── 원본 요청 ─────────────────────────────────────────────────────────
class Gone(Exception):
    """원본에서 내려간 공고(404/410·삭제 안내·다른 주소로 넘어감)."""


class Fetcher:
    """출처 하나의 요청기 — 그 호스트에는 초당 한 번 정도만 간다(앞 요청과의 간격을 지킨다).

    출처들은 따로 도는 스레드라 호스트끼리는 서로 기다리지 않는다. 브라우저 UA(jobs_common)를 쓴다 —
    알바몬·잡코리아 robots 는 AI 학습 수집기(ClaudeBot·GPTBot…)와 Scrapy 를 통째로 막는데, 이 크롤러는
    그런 수집기가 아니라 다른 채용 크롤러와 같은 일반 수집기로서 `User-agent: *` 규칙을 따른다.
    """

    def __init__(self, sleep_ms: int = 1100):
        self.sleep_ms = sleep_ms
        self._last = 0.0

    def wait(self) -> None:
        gap = jitter(self.sleep_ms) / 1000 - (time.time() - self._last)
        if gap > 0:
            time.sleep(gap)

    def get(self, url: str, referer: str | None = None, accept: str = "text/html,application/xml;q=0.9"
            ) -> tuple[int, str, str]:
        """(HTTP 상태, 최종 주소, 본문). 4xx/5xx 는 urllib.error.HTTPError 로 올린다.

        읽기 시간 초과·연결 끊김은 한 번만 쉬었다 다시 묻는다 — 알바몬 목록 85쪽 중 한 쪽이 가끔 늦어
        목록 전체를 잃던 것(2026-11-21 첫 수집). HTTP 오류(404·429 등)는 다시 묻지 않는다.
        """
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "ko-KR,ko;q=0.9"}
        if referer:
            headers["Referer"] = referer
        for attempt in (0, 1):
            self.wait()
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return resp.status, resp.geturl(), resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError:
                raise
            except (TimeoutError, urllib.error.URLError, ConnectionError):
                if attempt:
                    raise
                time.sleep(5)
            finally:
                self._last = time.time()
        raise RuntimeError("unreachable")


class Robots:
    """robots.txt 의 `User-agent: *` 묶음을 **가장 긴 규칙이 이기는** 방식(RFC 9309·구글)으로 읽는다.

    표준 라이브러리 robotparser 는 위에서부터 처음 맞는 줄을 쓴다. 알바천국처럼 `Disallow: /` 를 먼저
    깔고 아래에 `Allow: /job/` 을 여는 파일은 그 방식이면 전부 막힌 것으로 읽힌다 — 원본의 뜻과 반대다.
    `*`(아무 글자)·`$`(끝)를 지원한다. 같은 길이면 Allow 가 이긴다.
    """

    def __init__(self, text: str):
        self.rules: list[tuple[int, bool, re.Pattern]] = []
        groups: list[tuple[list[str], list[tuple[str, str]]]] = []
        agents: list[str] = []
        lines: list[tuple[str, str]] = []
        last_was_agent = False
        for raw in (text or "").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            k = k.lower()
            if k == "user-agent":
                if not last_was_agent and agents:
                    groups.append((agents, lines))
                    agents, lines = [], []
                agents.append(v.lower())
                last_was_agent = True
            elif k in ("allow", "disallow"):
                lines.append((k, v))
                last_was_agent = False
        if agents:
            groups.append((agents, lines))
        for ags, ls in groups:
            if "*" not in ags:
                continue
            for k, v in ls:
                if not v:
                    continue
                pat = "".join(".*" if c == "*" else ("$" if c == "$" and i == len(v) - 1 else re.escape(c))
                              for i, c in enumerate(v))
                self.rules.append((len(v), k == "allow", re.compile(pat)))

    def allowed(self, url: str) -> bool:
        u = urllib.parse.urlsplit(url)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        best = None
        for n, allow, pat in self.rules:
            if pat.match(path) and (best is None or n > best[0] or (n == best[0] and allow)):
                best = (n, allow)
        return True if best is None else best[1]


def ld_posting(html: str) -> dict | None:
    """페이지의 schema.org JobPosting 하나(없으면 None)."""
    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(raw, strict=False)          # 본문에 날 줄바꿈이 섞여 온다
        except json.JSONDecodeError:
            continue
        for x in d if isinstance(d, list) else [d]:
            if isinstance(x, dict) and x.get("@type") == "JobPosting":
                return x
    return None


def strip_tags(html: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</li>", "\n", html or "")
    t = re.sub(r"<[^>]+>", " ", t).replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").replace("&nbsp;", " ")
    return re.sub(r"[ \t]+", " ", t).strip()


# ── 누적 ──────────────────────────────────────────────────────────────
# 저장하는 칸은 이것뿐이다. deadline 은 원본이 준 마감일(당근은 없다 — validThrough 가 유료 노출 끝이라).
KEEP = ("title", "pay", "sido", "sigungu", "employment", "hours", "posted_at", "deadline")


def post_id(source: str, pid: str) -> str:
    return f"{source}-{pid}"


def make_post(source: str, pid: str, url: str, d: dict, category: str, now: str) -> dict:
    p = {"id": post_id(source, pid), "source": source, "pid": str(pid), "url": url, "category": category,
         "status": "open", "first_seen_at": now, "last_seen_at": now, "checked_at": now}
    p.update({k: d.get(k) for k in KEEP})
    p["history"] = [_snap(p, now)]
    return p


def _snap(p: dict, at: str) -> dict:
    return {"at": at, "status": p.get("status"), "pay": (p.get("pay") or {}).get("text") or None}


def _push_history(p: dict, now: str) -> None:
    hist = list(p.get("history") or [])
    last = hist[-1] if hist else {}
    snap = _snap(p, now)
    if last.get("status") != snap["status"] or last.get("pay") != snap["pay"]:
        hist.append(snap)
    p["history"] = hist[-HISTORY_MAX:]


def _close(p: dict, reason: str, at: str) -> None:
    if p.get("status") != "closed":
        p["status"], p["closed_reason"], p["closed_at"] = "closed", reason, at


def apply_check(p: dict, d: dict | None, gone: str | None, now: str) -> str:
    """재확인 결과를 공고에 반영한다. 돌려주는 값: 'closed'·'open'·'drop'(수집 거부)·'unknown'."""
    p["checked_at"] = now
    if gone:
        reason = gone
    elif d is None:
        return "unknown"
    elif d.get("opt_out"):
        return "drop"
    else:
        reason = d.get("closed_reason")
        for k in KEEP:                       # 제목·급여가 바뀌었을 수 있다
            if d.get(k) not in (None, ""):
                p[k] = d[k]
        if d.get("title"):
            cat = classify(p["title"], d.get("content") or "", d.get("parts") or ())
            if cat is None and "content" in d:
                return "drop"                # 본문까지 받아 다시 봤는데 이제 컴퓨터 일이 아니다(규칙이 좁아졌거나 제목이 바뀌었다)
            p["category"] = cat or p.get("category")
    if reason:
        _close(p, reason, (d or {}).get("closed_at") or now)
        _push_history(p, now)
        return "closed"
    if p.get("status") == "closed":          # 다시 열렸다
        p["status"] = "open"
        p.pop("closed_at", None)
        p.pop("closed_reason", None)
    _push_history(p, now)
    return "open"


def expire_by_deadline(p: dict, today: str, now: str) -> bool:
    """원본이 준 마감일이 지난 모집중 공고는 묻지 않고 닫는다(그날까지는 연다)."""
    dl = (p.get("deadline") or "")[:10]
    if p.get("status") == "open" and dl and dl < today:
        _close(p, f"마감일 경과({dl})", now)
        _push_history(p, now)
        return True
    return False


def dup_key(p: dict) -> str:
    """같은 공고로 볼 열쇠 — 제목(문장부호·괄호 머리말을 떼고) + 시/도 + 시/군/구 첫 낱말."""
    t = norm(re.sub(r"^\s*[\[(【][^\])】]{0,30}[\])】]\s*", "", p.get("title") or ""))
    return "|".join((t, p.get("sido") or "", (p.get("sigungu") or "").split(" ")[0]))


SOURCE_ORDER = ("daangn", "albacheonguk", "albamon", "saramin", "jobkorea")


def mark_dups(posts: list[dict]) -> int:
    """제목+지역이 같은 공고에 `dup_of`(대표 id)를 단다. 지우지 않는다 — 둘 다 목록에 남는다.

    대표는 모집중 → 출처 순서(SOURCE_ORDER) → 먼저 본 것. 같은 출처 안에서 같은 공고를 여러 번
    올린 것(알바천국에 같은 제목 8건)도 같은 규칙으로 묶인다. 돌려주는 값은 dup_of 가 붙은 수.
    """
    groups: dict[str, list[dict]] = {}
    for p in posts:
        p.pop("dup_of", None)
        k = dup_key(p)
        if k.split("|", 1)[0]:
            groups.setdefault(k, []).append(p)
    n = 0
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=lambda p: (p.get("status") != "open",
                              SOURCE_ORDER.index(p["source"]) if p.get("source") in SOURCE_ORDER else 99,
                              p.get("first_seen_at") or ""))
        for p in g[1:]:
            p["dup_of"] = g[0]["id"]
            n += 1
    return n


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def try_lock(fh) -> bool:
    """비차단 잠금. 이미 누가 잡고 있으면 False(close_check 와 같은 방식)."""
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def today_kst() -> str:
    return datetime.now().astimezone().date().isoformat()


def md_date(text: str, today: date) -> str | None:
    """'~12.20(일)' → 올해/내년 중 가까운 쪽 ISO(사람인 목록 표기). 연도가 없다."""
    m = re.search(r"(\d{1,2})\s*[./]\s*(\d{1,2})", text or "")
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    cands = []
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            cands.append(date(y, mm, dd))
        except ValueError:
            pass
    return min(cands, key=lambda c: abs((c - today).days)).isoformat() if cands else None


# ── 출처 ──────────────────────────────────────────────────────────────
class Source:
    """출처 하나. 이어받는 쪽이 listing·detail·recheck 를 채운다.

    listing() → {pid: entry}. entry 는 {"url", "title", "lastmod"?, "parts"?, ...} — 목록이 준 것.
    complete  : listing 이 그 출처의 우리 범위를 **끝까지** 본 것인가. 그래야 '목록에서 사라짐'을
                마감 신호로 쓴다(당근 사이트맵·알바천국/알바몬 분류 목록 전체). 검색 앞 몇 쪽만 보는
                사람인·잡코리아는 False — 안 보였다고 내려간 게 아니라서 원본에 묻는다.
    detail(pid, entry) → 요약 칸 dict(분류용 content·parts·opt_out·closed_reason 포함) 또는 None. Gone 을 올릴 수 있다.
    recheck(post) → detail 과 같은 모양. 기본은 detail(post.pid, {"url": post.url}).
    """
    name = ""
    label = ""
    sleep_ms = 1100
    new_limit = 150
    recheck_limit = 100
    check_limit = 60
    check_uses_listing = False     # --check 에서도 목록을 받나(당근 사이트맵만 — 나머지는 재확인만)
    listing_open_only = False      # 목록에 모집중만 실리나(알바천국·알바몬) — 목록에 다시 보인 마감 공고는 다시 묻는다

    def __init__(self):
        self.http = Fetcher(self.sleep_ms)
        self.complete = False

    def listing(self) -> dict[str, dict]:
        raise NotImplementedError

    def candidate(self, e: dict) -> bool:
        return is_candidate(e.get("title") or "", e.get("parts") or ())

    def signature(self, e: dict) -> str:
        """'아니다' 판정을 기억할 때의 열쇠 — 이게 바뀌면(제목 수정) 다시 본다."""
        return e.get("slug") or e.get("title") or ""

    def detail(self, pid: str, e: dict) -> dict | None:
        raise NotImplementedError

    def recheck(self, p: dict) -> dict | None:
        return self.detail(p["pid"], {"url": p["url"], "title": p.get("title")})


def plan_recheck(posts: dict[str, dict], entries: dict[str, dict], seen_lastmod: dict[str, str],
                 listing_ok: bool, skip: set[str], limit: int, open_only: bool = False) -> list[str]:
    """이번 회차에 원본에 다시 물을 pid. 사라진 것 → lastmod 바뀐 것 → 오래 안 물어본 모집중 순.

    posts 는 이 출처의 공고(pid → 공고). listing_ok 가 False 면(목록을 끝까지 못 봤거나 크게 줄었다)
    '사라짐'으로 묻지 않는다. open_only 면 모집중만 싣는 목록에 다시 보인 마감 공고(마감일이 늘어났다)도
    '바뀐 것'으로 묻는다 — 마감일 경과로 닫은 공고가 다시 열릴 길이다.
    """
    gone, changed, rest = [], [], []
    for pid, p in posts.items():
        if pid in skip:
            continue
        e = entries.get(pid)
        if p.get("status") == "open" and e is None:
            if listing_ok:
                gone.append(pid)
                continue
        if e and e.get("lastmod") and seen_lastmod.get(pid) and e["lastmod"] != seen_lastmod[pid]:
            changed.append(pid)
        elif e and open_only and p.get("status") == "closed":
            changed.append(pid)
        elif p.get("status") == "open":
            rest.append(pid)
    rest.sort(key=lambda i: posts[i].get("checked_at") or "")
    budget = max(0, limit - len(changed))
    return gone[:GONE_LIMIT] + changed[:limit] + rest[:budget]


def run_source(src: Source, posts: dict[str, dict], st: dict, now: str,
               new_limit: int, recheck_limit: int, use_listing: bool = True) -> dict:
    """출처 하나의 한 회차. posts(pid → 공고)와 st(그 출처의 상태)를 그 자리에서 고친다.

    실패는 여기서 끝난다 — 목록이 실패해도 재확인은 하고, 공고 하나가 실패해도 다음으로 간다.
    """
    t0 = time.time()
    rep: dict = {"ok": True}
    rejected: dict[str, str] = st.get("rejected") or {}
    purged = 0
    if st.get("rules_version") != RULES_VERSION:
        rejected = {}                                            # 규칙이 바뀌었다 — 버린 것도 다시 본다
        # 실은 것 중 제목이 이제 막히는 것(헤어 '디자이너' 같은)은 지운다. 막힘은 제목만으로 정해져서
        # 본문 없이도 확실하다. 막히지 않았지만 모호한 것은 재확인 때 apply_check 가 본문으로 다시 본다.
        for pid in [k for k, p in posts.items() if _vetoed(norm(p.get("title") or ""))]:
            posts.pop(pid)
            purged += 1
        if purged:
            print(f"[alba:{src.name}] 규칙 {RULES_VERSION}판 — 제목이 이제 막히는 공고 {purged}건을 지웠다", flush=True)
    seen_lastmod: dict[str, str] = st.get("lastmod") or {}
    entries: dict[str, dict] = {}
    listing_ok = False
    if use_listing:
        try:
            entries = src.listing()
            prev = st.get("listing_count") or 0
            listing_ok = src.complete and (not prev or len(entries) >= prev * LISTING_MIN_RATIO)
            if src.complete and not listing_ok:
                print(f"[alba:{src.name}] 목록 {len(entries)}건 — 직전 {prev}건의 절반 밑이라 '사라짐' 판정을 보류한다",
                      flush=True)
            if src.complete:
                st["listing_count"] = len(entries)
            rep["listed"] = len(entries)
        except Exception as e:                                   # noqa: BLE001 — 출처 하나의 실패
            print(f"[alba:{src.name}] 목록 실패: {str(e)[:160]}", flush=True)
            rep.update(ok=False, error=str(e)[:200])
    for pid in entries.keys() & posts.keys():
        posts[pid]["last_seen_at"] = now

    # 1차 후보 — 이미 싣고 있거나, 같은 제목으로 아니라고 판정한 것은 뺀다.
    cands = [(pid, e) for pid, e in entries.items()
             if pid not in posts and rejected.get(pid) != src.signature(e) and src.candidate(e)]
    cands.sort(key=lambda x: x[1].get("lastmod") or x[1].get("sort") or "", reverse=True)
    fetched = new = failed = 0
    for pid, e in cands[:new_limit]:
        fetched += 1
        try:
            d = src.detail(pid, e)
        except Gone:
            rejected[pid] = src.signature(e)
            continue
        except Exception as ex:                                  # noqa: BLE001
            failed += 1
            print(f"  [alba:{src.name}] {pid} 실패: {str(ex)[:80]}", flush=True)
            continue
        if d is None:
            failed += 1
            continue
        cat = None if (d.get("opt_out") or d.get("closed_reason")) else classify(
            d.get("title") or e.get("title") or "", d.get("content") or "", d.get("parts") or e.get("parts") or ())
        if not cat:
            rejected[pid] = src.signature(e)
            continue
        posts[pid] = make_post(src.name, pid, d.get("url") or e["url"], {**d, "title": d.get("title") or e.get("title")},
                               cat, now)
        if e.get("lastmod"):
            seen_lastmod[pid] = e["lastmod"]
        new += 1

    # 마감일이 지난 것은 묻지 않고 닫는다.
    today = now[:10]
    closed_now = sum(expire_by_deadline(p, today, now) for p in posts.values())

    # 재확인 — 사라진 것은 바로, 나머지 모집중은 오래 안 물어본 것부터.
    todo = plan_recheck(posts, entries, seen_lastmod, listing_ok,
                        skip={k for k, p in posts.items() if p.get("first_seen_at") == now}, limit=recheck_limit,
                        open_only=src.listing_open_only and listing_ok)
    for pid in todo:
        p = posts[pid]
        e = entries.get(pid)
        gone = d = None
        try:
            d = src.recheck({**p, "url": (e or {}).get("url") or p["url"]})
        except Gone as g:
            gone = str(g) or "원본에서 내려감"
        except Exception as ex:                                  # noqa: BLE001
            print(f"  [alba:{src.name}] 재확인 {pid} 실패: {str(ex)[:80]}", flush=True)
        was = p.get("status")
        res = apply_check(p, d, gone, now)
        if res == "drop":                                        # 작성자가 수집을 막았다 — 지운다
            posts.pop(pid)
            seen_lastmod.pop(pid, None)
            rejected[pid] = src.signature(e or {"title": p.get("title")})
            continue
        if e:
            p["url"] = e["url"]
            if e.get("lastmod"):
                seen_lastmod[pid] = e["lastmod"]
        if res == "closed" and was != "closed":
            closed_now += 1

    # 끝까지 본 목록이면 거기서 빠진 id 는 판정 기록에서도 지운다(다시 올라오면 새로 본다).
    # 아니면 최근 것만 남긴다 — 검색 결과에서 밀려난 id 를 영원히 들고 있지 않게.
    if listing_ok:
        rejected = {k: v for k, v in rejected.items() if k in entries}
    elif len(rejected) > REJECTED_MAX:
        rejected = dict(list(rejected.items())[-REJECTED_MAX:])
    st.update(rejected=rejected, lastmod={k: v for k, v in seen_lastmod.items() if k in posts},
              rules_version=RULES_VERSION)
    rep.update({"purged": purged, "candidates": len(cands), "fetched": fetched, "failed": failed, "new": new,
                "rechecked": len(todo), "closed_now": closed_now, "elapsed": round(time.time() - t0, 1),
                "total": len(posts), "open": sum(p.get("status") == "open" for p in posts.values())})
    return rep
