"""당근알바 IT 공고 크롤러 → jd-viewer/public/alba.json (누적).

당근알바(jobs.daangn.com)에는 동네 단위의 짧은 일거리가 올라온다. 대부분 서빙·포장·청소지만
그 사이에 "홈페이지 수정해 주실 분", "엑셀 자동화 알려 주실 분", "유아 코딩 강사" 같은 IT 일감이
섞여 있다. 그것만 골라 모은다.

**IT 공고만, 요약과 링크만 둔다.** 당근알바 약관은 서비스 구성요소를 동의 없이 상업적으로
복제하는 것을 금한다. 그래서 crawl_freelance 의 SISM 처럼 화면에 필요한 최소한만 남긴다 —
공고 번호·제목·급여(금액·단위)·지역(시/도·시/군/구까지, 번지·도로명은 버린다)·고용 형태·
근무 시간·등록일·원문 주소·처음/마지막 본 시각·모집 상태·마감 시각·우리가 붙인 분류.
본문·사업자/작성자 이름·연락처·사진은 저장하지 않는다. 본문은 분류할 때 메모리에서만 읽는다.
작성자가 '웹 수집 허용 안 함'(webCrawlNotAllowed)을 켠 공고는 아예 싣지 않는다(이미 실었으면 지운다).
상세 내용과 지원은 원문에서 한다.

수집 경로 (2026-11-21 조사):
  robots.txt  : User-agent: * 허용. /api/·/me·/auth/·/job-posts/*/apply 등만 막는다 — /api/ 는 부르지 않는다.
  사이트맵    : /sitemap.xml → sitemaps/job-posts-N.xml (공고 4만여 건, <lastmod> 포함)
  공고 주소   : /job-posts/<제목 슬러그>-<12자 id>. 슬러그가 제목이라 사이트맵만으로 1차로 거른다.
  상세        : 페이지에 실린 공고 데이터(closed·closedAt·hidden·deleted·status·급여·근무 시간·
                workplaceRegion) — JSON-LD JobPosting 은 있는 공고만 있어서 없을 때의 보조로만 쓴다.
                JSON-LD 의 validThrough 는 유료 노출 끝나는 날이지 마감일이 아니다 — 쓰지 않는다.

거르는 법 (두 단계):
  1) 사이트맵 슬러그(= 제목)에 분류 규칙을 돌린다. 분류가 되거나, IT 냄새('컴퓨터'·'AI'·'엑셀'…)가
     나면서 서빙·포장 같은 현장 일 낱말이 없는 것만 후보다. 슬러그 끝의 id 는 떼고 본다 —
     무작위 12자에 'it'·'ai'·'gpt' 가 자주 들어 있다.
  2) 후보의 상세를 받아 진짜 제목으로 다시 분류한다. 제목만으로 모호하면(‘컴퓨터 잘하시는 분’)
     본문을 메모리에서 같이 본다. 아니라고 판정된 것은 var/alba/state.json 에 적어 다시 받지 않는다
     (제목이 바뀌어 슬러그가 달라지면 다시 본다).

마감 규칙:
  - 원본 데이터가 closed 이거나 closedAt 이 있거나 deleted·hidden·비공개(privatizedAt)거나
    status 가 ACCEPTED 가 아니면 마감. 404/410 이거나 다른 주소로 넘어가도 마감.
  - 사이트맵에서 사라진 모집중 공고는 그 회차에 바로 다시 묻는다(GONE_LIMIT).
    단 사이트맵이 직전보다 절반 넘게 줄었으면 사이트맵이 깨진 것으로 보고 '사라짐'을 보류한다.
  - 나머지 모집중 공고는 오래 안 물어본 것부터 회차당 RECHECK_LIMIT 건.
  - 사이트맵 lastmod 가 바뀐 공고(마감한 것 포함 — 다시 열 수 있다)도 먼저 묻는다.

사용:
    python -m crawlers.crawl_daangn_alba                 # 기본(신규 상세 NEW_LIMIT, 재확인 RECHECK_LIMIT)
    python -m crawlers.crawl_daangn_alba --new 800       # 처음 돌릴 때 — 후보를 더 많이 받는다
    python -m crawlers.crawl_daangn_alba --candidates    # 1차 후보만 출력(상세를 받지 않는다)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from core.paths import VAR_DIR, VIEWER_PUBLIC
from crawlers.jobs_common import USER_AGENT, jitter

BASE = "https://jobs.daangn.com"
SITEMAP_INDEX = f"{BASE}/sitemap.xml"
OUT_PATH = VIEWER_PUBLIC / "alba.json"
STATE_PATH = VAR_DIR / "alba" / "state.json"
# 회차 안(crawl_all)과 회차 사이(launchd com.jobseeker.albacheck) 두 곳에서 돈다. 둘 다 alba.json 을
# 통째로 읽고 쓰므로 겹치면 늦게 끝난 쪽이 먼저 끝난 쪽의 마감 판정을 지운다 — 못 잡은 쪽이 건너뛴다.
LOCK_PATH = VAR_DIR / "alba" / "alba.lock"
CHECK_LIMIT = 60          # 회차 사이 재확인 한 번에 묻는 수(사라진 것은 GONE_LIMIT 까지 따로)

NEW_LIMIT = 150            # 회차당 새로 받는 상세 수. 사이트맵 lastmod 최신순
RECHECK_LIMIT = 100        # 회차당 모집중 재확인 수(오래 안 물어본 것부터)
GONE_LIMIT = 300           # 사이트맵에서 사라진 공고는 따로 — 바로 묻는다
SITEMAP_MIN_RATIO = 0.5    # 사이트맵이 직전의 절반 밑이면 '사라짐'을 보류한다
SLEEP_MS = 1100            # 초당 한 번 정도
TIMEOUT = 25
HISTORY_MAX = 20
CONTENT_PEEK = 1500        # 분류에 쓰는 본문 앞부분(저장하지 않는다)

ID_RE = re.compile(r"^[0-9a-z]{12}$")


# ── 분류 ──────────────────────────────────────────────────────────────
# 우리 분류(당근의 업무 분류와 따로). 순서가 곧 우선순위다 — '코딩 가르쳐 주실 분'은 개발이 아니라 강사.
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
_CODING = r"(?<!레)코딩"   # '홈레코딩'

TEACH_TOPIC = re.compile(
    rf"{_CODING}|프로그래밍|파이썬|{_E}python{_Z}|{_E}java{_Z}|자바(?!칩|라)|c언어|{_E}c\+\+|스크래치|엔트리|아두이노|{_E}plc{_Z}|디지털\s*포렌식|"
    rf"{_E}unity{_Z}|유니티|{_E}ai{_Z}|인공지능|챗\s*gpt|{_E}gpt{_Z}|클로드|컴퓨터|컴활|엑셀|{_E}excel{_Z}|"
    rf"파워\s*포인트|{_E}ppt{_Z}|{_E}oa{_Z}|{_E}it{_Z}")
TEACH_ACT = re.compile(r"강사|선생님|쌤|과외|교사|가르쳐|가르치|가르칠|배우|배울|레슨|수업|(?<!평생)교육(?!청|원)|교습|튜터|멘토|알려\s*주|코칭|강의")

WEBAPP = re.compile(
    r"(?:홈\s*페이지|웹\s*사이트|사이트|웹\s*페이지|랜딩\s*페이지|웹|앱|어플|워드\s*프레스|아임웹|카페24|자사몰|쇼핑몰|플랫폼)"
    r"(?:을|를|의|좀)?\s*(?:제작|개발|만들|만드|구축|리뉴얼|수정|변경|퍼블리싱|코딩|외주)"
    r"|퍼블리셔|웹\s*퍼블")
DEV = re.compile(
    rf"개발자|프로그래머|프로그래밍|{_CODING}|파이썬|{_E}python{_Z}|자바\s*스크립트|{_E}javascript{_Z}|"
    rf"{_E}java{_Z}|자바(?!칩|라)|{_E}react{_Z}|리액트|(?<!팅)플러터|{_E}flutter{_Z}|{_E}unity{_Z}|유니티|언리얼|"
    rf"백엔드|프론트\s*엔드|서버\s*개발|{_E}aws{_Z}|클라우드|크롤링|크롤러|스크래핑|{_E}api{_Z}|매크로|"
    rf"{_E}sw{_Z}|소프트웨어\s*개발|임베디드|펌웨어|아두이노|라즈베리|졸업\s*작품|프로그램\s*(?:개발|제작|만들)|"
    rf"게임\s*개발|{_E}it\s*개발|데이터\s*베이스|{_E}sql{_Z}|챗봇|{_E}ai\s*(?:개발|에이전트|모델)|"
    rf"머신\s*러닝|딥\s*러닝|{_E}rag{_Z}|개발\s*(?:알바|외주|프리랜서)")
DESIGN = re.compile(
    rf"웹\s*디자인|웹디|{_E}ui{_Z}|{_E}ux{_Z}|피그마|{_E}figma{_Z}|포토샵|포샵|포샾|일러스트레이터|상세\s*페이지|썸네일|"
    rf"배너\s*디자인|(?<!신문)편집자|프리미어\s*프로|어도비|애프터\s*이펙트|캡컷|모션\s*그래픽|{_E}3d{_Z}|블렌더|"
    rf"(?:웹|{_E}ui|{_E}ux|그래픽|편집|시각|영상|콘텐츠|컨텐츠|상세|쇼핑몰|온라인)\s*디자이너|"
    rf"(?:영상|유튜브|유트브|쇼츠|숏폼|릴스|동영상|컷)\S*\s*(?:\S+\s+){{0,3}}?\S*편집|"
    rf"(?:영상|숏츠|쇼츠|{_E}shorts{_Z}|숏폼)\s*(?:제작|만들|만드|작업)")
OPS = re.compile(
    r"(?:홈\s*페이지|블로그|스마트\s*스토어|쇼핑몰|자사몰|오픈\s*마켓|네이버\s*스토어|카페24|아마존|쇼피|큐텐|플레이오토|사방넷)"
    r"[^\n]{0,20}?(?:관리|운영|등록|업로드|올리|세팅|셋팅|사용|{seo}|상위\s*노출)".replace("{seo}", rf"{_E}seo{_Z}"))
DATA = re.compile(
    rf"(?:엑셀|{_E}excel{_Z}|스프레드\s*시트|구글\s*시트)\s*\S{{0,3}}?\s*(?:작업|정리|자동화|함수|매크로|데이터|문서|입력|만들|작성)|"
    rf"{_E}vba{_Z}|업무\s*자동화|사무\s*자동화|자동화\s*(?:{_E}ai{_Z}|프로그램)|"
    rf"(?:{_E}ai|{_E}gpt|챗\s*gpt|클로드)\s*(?:활용|자동화)|데이터\s*(?:입력|정리|수집|라벨링|분석|작업|파일)|"
    rf"라벨링|라벨러|전산\s*입력|노션|{_E}ppt\s*제작|파워\s*포인트\s*제작")
PC = re.compile(
    rf"(?:컴퓨터|컴터|{_E}pc{_Z}|노트북|맥북|공유기|와이파이|{_E}wifi{_Z}|네트워크|인터넷|{_E}cctv{_Z}|프린터|모니터|윈도우|"
    rf"{_E}nas{_Z}|하드|갤럭시|아이폰|스마트폰|태블릿)"
    rf"[^\n]{{0,12}}?(?:조립|수리|설치|연결|세팅|셋팅|교체|선\s*정리|{_E}as{_Z}|포맷|복구|업그레이드|문제|해결|견적|깔아|"
    rf"봐\s*주|잘\s*(?:하시|아시|다루)|점검|고쳐|고치|복원|백업|옮기|설정|배선|살려)|데이터\s*복구")

# 현장 일 — 제목에 있으면 IT 공고가 아니다(쇼핑몰 '포장' 알바, 자동화 '설비', 웹툰 '모델'…).
NON_IT = re.compile(
    rf"서빙|써빙|홀\s*(?:직원|알바|파트|매니저)|주방|설거지|조리|택배|포장|물류|창고|피킹|패킹|입출고|재고|배달|"
    rf"청소|미화|지게차|생산직|공장|설비|조립\s*(?:원|인원|직원)|기구\s*조립|부품|판매|매장\s*(?:관리|직원)|"
    rf"{_E}cs{_Z}|상담|콜센터|{_E}md{_Z}|모델|출연|마케터|마케팅|영업|홍보|체험단|참가자|운전|배송|진열|스팀|"
    rf"경리|회계|세무|간호|요양|보육|시터|화물|현장|라이더|식당|매장|고객\s*응대|춤|댄스|엑셀\s*방송|"
    rf"(?<=[가-힣a-z])pc{_Z}|pc\s*(?:방|카페|아레나)|피시방|자동화\s*(?:설비|장비|레일|set)")
# 이건 STRONG 이 있어도 IT 공고가 아니다 — 차량 '코딩'(BMW·카플레이 설정)은 소프트웨어 일이 아니다.
HARD_NON_IT = re.compile(r"{b}bmw|벤츠|아우디|클럽맨|카플레이|안드로이드\s*오토|차량|자동차".replace("{b}", _E))
# 현장 일 낱말이 있어도 IT 일이 분명한 것(‘쇼핑몰 MD 겸 웹디자이너’, ‘유튜브 촬영 및 편집’).
STRONG = re.compile(
    rf"개발자|프로그래머|{_CODING}|웹\s*디자이너|웹디|홈\s*페이지\s*(?:제작|개발)|웹\s*사이트\s*제작|앱\s*개발|"
    rf"영상\s*편집|편집자|컴퓨터\s*(?:수리|조립)")
# 촬영만 하는 일은 IT 가 아니다 — 편집이 같이 있으면 STRONG/DESIGN 이 건진다.
SHOOT_ONLY = re.compile(r"촬영(?!.*편집)")
# 제목만으로 모호한 것 — 이게 있으면 상세 본문까지 보고 판정한다.
# 온라인·인터넷·디지털·전산·프로그램은 뺐다 — '온라인 쇼핑몰 정직원', '약국 전산업무', '시니어 프로그램 강사'처럼
# 본문까지 봐도 IT 일이 아닌 것이 대부분이었다(2026-11-21 첫 수집).
WEAK = re.compile(
    rf"컴퓨터|{_E}(?:it|ai|pc|sns){_Z}|엑셀|유튜브|데이터|자동화|웹(?!소설|툰)|앱|코딩|홈\s*페이지")

_RULES = [
    ("코딩·IT 강사", lambda t: bool(TEACH_TOPIC.search(t) and TEACH_ACT.search(t))),
    ("웹·앱 제작", lambda t: bool(WEBAPP.search(t)) and not re.search(r"상세\s*페이지", t)),
    ("개발·프로그래밍", lambda t: bool(DEV.search(t))),
    ("디자인·영상", lambda t: bool(DESIGN.search(t))),
    ("홈페이지·쇼핑몰 운영", lambda t: bool(OPS.search(t))),
    ("데이터·사무자동화", lambda t: bool(DATA.search(t))),
    ("PC·기기 지원", lambda t: bool(PC.search(t))),
]


def norm(text: str) -> str:
    """소문자, 하이픈·문장부호는 띄어쓰기로. 슬러그('홈페이지-제작')와 제목을 같은 규칙으로 본다."""
    t = (text or "").lower().replace("&amp;", " ")
    t = re.sub(r"[-_/|·,()\[\]{}!?~★☆♥※*\"'“”‘’:;.]+", " ", t)
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


def classify(title: str, content: str = "") -> str | None:
    """우리 분류 하나, IT 공고가 아니면 None. 본문은 제목이 모호할 때만 보고 저장하지 않는다."""
    t = norm(title)
    if _vetoed(t):
        return None
    cat = _rules(t)
    if cat or not content or not WEAK.search(t):
        return cat
    # 본문에서는 '강사' 판정을 하지 않는다 — '교육'·'선생님'은 어느 공고 본문에나 있다.
    return _rules(norm(content[:CONTENT_PEEK]), skip=("코딩·IT 강사",))


def is_candidate(slug_title: str) -> bool:
    """1차(사이트맵 슬러그만) — 상세를 받아 볼 만한가."""
    t = norm(slug_title)
    if _vetoed(t):
        return False
    return bool(_rules(t) or WEAK.search(t))


# ── 사이트맵 ──────────────────────────────────────────────────────────
SM_ITEM_RE = re.compile(r"<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?")


def split_loc(loc: str) -> tuple[str, str] | None:
    """'…/job-posts/<슬러그>-<id>' → (id, 슬러그 제목). 모양이 다르면 None."""
    tail = urllib.parse.unquote(loc.rstrip("/").rsplit("/", 1)[-1])
    if "/job-posts/" not in loc or "-" not in tail:
        return None
    slug, pid = tail.rsplit("-", 1)
    return (pid, slug) if ID_RE.match(pid) else None


def parse_sitemap(xml: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for loc, lastmod in SM_ITEM_RE.findall(xml):
        loc = loc.strip().replace("&amp;", "&")
        sp = split_loc(loc)
        if sp:
            out[sp[0]] = {"url": loc, "slug": sp[1], "lastmod": (lastmod or "").strip()}
    return out


def fetch_sitemap() -> dict[str, dict]:
    index = _get(SITEMAP_INDEX)[2]
    maps = [u for u in re.findall(r"<loc>([^<]+)</loc>", index) if re.search(r"/job-posts-\d+\.xml", u)]
    if not maps:
        raise RuntimeError("사이트맵 색인에 job-posts-N.xml 이 없다")
    entries: dict[str, dict] = {}
    for u in maps:
        entries.update(parse_sitemap(_get(u.strip())[2]))
        _sleep()
    return entries


# ── 상세 ──────────────────────────────────────────────────────────────
class Gone(Exception):
    """원본에서 내려간 공고(404/410·다른 주소로 넘어감)."""


def _get(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "text/html,application/xml;q=0.9",
        "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.geturl(), resp.read().decode("utf-8", "replace")


def _sleep() -> None:
    time.sleep(jitter(SLEEP_MS) / 1000)


_JS_STR = r'"((?:[^"\\]|\\.)*)"'
POST_START = re.compile(r"jobPost:\$R\[\d+\]=\{")


def _js_str(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def _scalar(seg: str, name: str):
    m = re.search(r"[{,]" + name + r":(?:" + _JS_STR + r"|(!0|!1|null|-?\d+(?:\.\d+)?))", seg)
    if not m:
        return None
    if m.group(1) is not None:
        return _js_str(m.group(1))
    v = m.group(2)
    return {"!0": True, "!1": False, "null": None}.get(v, None) if not re.match(r"-?\d", v) else (
        float(v) if "." in v else int(v))


def _array(seg: str, name: str) -> list[str]:
    m = re.search(r"[{,]" + name + r":\$R\[\d+\]=\[([^\]]*)\]", seg)
    return re.findall(_JS_STR, m.group(1)) if m else []


def _segment(html: str) -> str | None:
    m = POST_START.search(html)
    if not m:
        return None
    end = html.find("__fragments:", m.end())
    return html[m.end(): end if end > 0 else m.end() + 20000]


def _ld_posting(html: str) -> dict | None:
    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for x in d if isinstance(d, list) else [d]:
            if isinstance(x, dict) and x.get("@type") == "JobPosting":
                return x
    return None


PAY_UNIT = {"HOURLY": "시급", "DAILY": "일급", "WEEKLY": "주급", "MONTHLY": "월급",
            "YEARLY": "연봉", "PER_CASE": "건당"}
EMPLOYMENT = {"PART_TIME_JOB": "알바", "PART_TIME": "알바", "STAFF": "정직원", "FULL_TIME": "정직원",
              "CONTRACT": "계약직", "CONTRACTOR": "계약직", "FREELANCER": "프리랜서", "INTERN": "인턴"}
DAYS = {"MON": "월", "TUE": "화", "WED": "수", "THU": "목", "FRI": "금", "SAT": "토", "SUN": "일"}
SIDO = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
    "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원도": "강원",
    "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남", "전남광주통합특별시": "광주·전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}


def _hours(days: list[str], start, end, negotiable) -> str:
    d = "·".join(DAYS.get(x, x) for x in days)
    t = f"{start}~{end}" if start and end and (start, end) != ("00:00", "23:30") else ""
    s = " ".join(x for x in (d, t) if x)
    if negotiable and s:
        s += " (협의)"
    return s or ("시간 협의" if negotiable else "")


def parse_detail(html: str) -> dict | None:
    """상세 페이지 → 저장할 요약 칸 + 판정에 쓰는 것(content·opt_out·closed_reason).

    content 는 분류에만 쓰고 호출부가 버린다. 공고 데이터가 없으면 None.
    """
    seg = _segment(html)
    ld = _ld_posting(html)
    if seg is None and ld is None:
        return None
    if seg is None:                                   # 보조 — JSON-LD 만 있는 화면
        addr = ((ld.get("jobLocation") or {}).get("address") or {})
        sal = ld.get("baseSalary") or {}
        val = sal.get("value") if isinstance(sal.get("value"), (int, float)) else (sal.get("value") or {}).get("value")
        return {"title": ld.get("title") or "", "content": ld.get("description") or "",
                "pay": {"amount": val, "unit": {"HOUR": "시급", "DAY": "일급", "MONTH": "월급", "YEAR": "연봉"}.get(
                    (sal.get("value") or {}).get("unitText") if isinstance(sal.get("value"), dict) else sal.get("unitText"), ""),
                        "text": ""} if val else None,
                "sido": SIDO.get(addr.get("addressRegion") or "", addr.get("addressRegion") or ""),
                "sigungu": addr.get("addressLocality") or "",
                "employment": EMPLOYMENT.get(str(ld.get("employmentType") or ""), str(ld.get("employmentType") or "")),
                "hours": str(ld.get("workHours") or ""), "posted_at": ld.get("datePosted"),
                "opt_out": False, "closed_reason": None}

    closed_reason = None
    status = _scalar(seg, "status")
    if _scalar(seg, "deleted"):
        closed_reason = "원본 삭제"
    elif _scalar(seg, "closed") or _scalar(seg, "closedAt"):
        closed_reason = "원본 확인: 모집 마감"
    elif _scalar(seg, "hidden") or _scalar(seg, "privatizedAt"):
        closed_reason = "원본 확인: 숨김·비공개"
    elif status and status != "ACCEPTED":
        closed_reason = f"원본 상태 {status}"
    salary, stype = _scalar(seg, "salary"), _scalar(seg, "salaryType")
    region = seg[seg.find("workplaceRegion:"):] if "workplaceRegion:" in seg else ""
    name1, name2 = _scalar(region, "name1") or "", _scalar(region, "name2") or ""
    etype = _scalar(seg, "employmentType") or ""
    return {
        "title": _scalar(seg, "title") or "",
        "content": _scalar(seg, "content") or "",
        "pay": {"amount": salary, "unit": PAY_UNIT.get(stype or "", stype or ""),
                "text": _scalar(seg, "stringifiedSalary") or ""} if salary else None,
        "sido": SIDO.get(name1, name1), "sigungu": name2,
        "employment": EMPLOYMENT.get(etype, etype),
        "hours": _hours(_array(seg, "workDays"), _scalar(seg, "workTimeStart"), _scalar(seg, "workTimeEnd"),
                        _scalar(seg, "isWorkTimeNegotiable")),
        "posted_at": _scalar(seg, "publishedAt") or _scalar(seg, "createdAt") or (ld or {}).get("datePosted"),
        "opt_out": bool(re.search(r"webCrawlNotAllowed:!0", seg)),
        "closed_reason": closed_reason,
        "closed_at": _scalar(seg, "closedAt"),
    }


def fetch_detail(url: str, pid: str) -> dict | None:
    """원본을 받아 parse_detail. 내려간 공고는 Gone. 모양을 못 읽으면 None."""
    try:
        status, final, html = _get(url)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise Gone(f"원본 삭제(HTTP {e.code})") from None
        raise
    if pid not in urllib.parse.unquote(final):
        raise Gone("원본에서 내려감(다른 주소로 넘어감)")
    return parse_detail(html)


# ── 누적 ──────────────────────────────────────────────────────────────
KEEP = ("title", "pay", "sido", "sigungu", "employment", "hours", "posted_at")


def make_post(pid: str, url: str, d: dict, category: str, now: str) -> dict:
    p = {"id": pid, "url": url, "category": category, "status": "open",
         "first_seen_at": now, "last_seen_at": now, "checked_at": now}
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
        p["category"] = classify(p["title"], d.get("content") or "") or p.get("category")
    if reason:
        if p.get("status") != "closed":
            p["status"], p["closed_reason"] = "closed", reason
            p["closed_at"] = (d or {}).get("closed_at") or now
        _push_history(p, now)
        return "closed"
    if p.get("status") == "closed":          # 다시 열렸다
        p["status"] = "open"
        p.pop("closed_at", None)
        p.pop("closed_reason", None)
    _push_history(p, now)
    return "open"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def plan_recheck(posts: dict[str, dict], entries: dict[str, dict], seen_lastmod: dict[str, str],
                 sitemap_ok: bool, skip: set[str], limit: int = RECHECK_LIMIT) -> list[str]:
    """이번 회차에 원본에 다시 물을 공고 id. 사라진 것 → lastmod 바뀐 것 → 오래 안 물어본 모집중 순."""
    gone, changed, rest = [], [], []
    for pid, p in posts.items():
        if pid in skip:
            continue
        e = entries.get(pid)
        if p.get("status") == "open" and e is None:
            if sitemap_ok:
                gone.append(pid)
            continue
        if e and e.get("lastmod") and seen_lastmod.get(pid) and e["lastmod"] != seen_lastmod[pid]:
            changed.append(pid)
        elif p.get("status") == "open":
            rest.append(pid)
    rest.sort(key=lambda i: posts[i].get("checked_at") or "")
    budget = max(0, limit - len(changed))
    return gone[:GONE_LIMIT] + changed[:limit] + rest[:budget]


def _try_lock(fh) -> bool:
    """비차단 잠금. 이미 누가 잡고 있으면 False(close_check 와 같은 방식)."""
    try:
        if _sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def run(new_limit: int = NEW_LIMIT, recheck_limit: int = RECHECK_LIMIT) -> dict:
    """한 회차. 잠금을 못 잡으면(다른 쪽이 도는 중) 건너뛴다 — 다음 주기에 다시 온다."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as fh:
        if not _try_lock(fh):
            print("[alba] 다른 회차가 alba.json 을 쓰는 중 — 이번엔 건너뜀", flush=True)
            return {"ok": True, "skipped": True, "total": None, "open": None, "new": 0, "closed_now": 0}
        return _run(new_limit, recheck_limit)


def check(limit: int = CHECK_LIMIT) -> dict:
    """회차 사이 재확인 — 새 공고는 받지 않고 마감만 본다(launchd albacheck 가 부른다).

    사람을 구하면 당근에서 공고가 닫히는데, 크롤 회차(1시간)만 기다리면 그만큼 늦게 닫힌다.
    결과는 뷰어 API(viewer_doc)에도 바로 옮긴다 — 회차 끝의 문서 동기화를 기다리지 않게.
    """
    stats = run(new_limit=0, recheck_limit=limit)
    if stats.get("ok") and not stats.get("skipped"):
        try:
            from store.ingest.docs import sync
            sync()
        except Exception as e:                                   # noqa: BLE001 — DB 가 없어도 파일은 이미 갱신됐다
            print(f"[alba] 뷰어 문서 동기화 건너뜀: {str(e)[:120]}", flush=True)
    try:
        from automation import orchestration as orch
        orch.emit("alba_check", **stats)
    except Exception:                                            # noqa: BLE001
        pass
    return stats


def _run(new_limit: int, recheck_limit: int) -> dict:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    doc = _load_json(OUT_PATH, {"posts": []})
    state = _load_json(STATE_PATH, {})
    posts: dict[str, dict] = {p["id"]: p for p in doc.get("posts") or []}
    rejected: dict[str, str] = state.get("rejected") or {}       # id → 판정했을 때의 슬러그
    seen_lastmod: dict[str, str] = state.get("lastmod") or {}    # 싣고 있는 공고의 사이트맵 lastmod
    report = {"ok": False, "at": now}
    t0 = time.time()
    try:
        entries = fetch_sitemap()
    except Exception as e:                                       # noqa: BLE001
        print(f"[alba] 사이트맵 실패: {e}", flush=True)
        report["error"] = str(e)[:200]
        doc["source"] = report
        doc["updated_at"] = now
        _write_json(OUT_PATH, {**doc, "posts": list(posts.values())})
        return {"ok": False, "total": len(posts), "open": sum(p["status"] == "open" for p in posts.values()),
                "new": 0, "closed_now": 0}
    prev = state.get("sitemap_count") or 0
    sitemap_ok = not prev or len(entries) >= prev * SITEMAP_MIN_RATIO
    if not sitemap_ok:
        print(f"[alba] 사이트맵 {len(entries)}건 — 직전 {prev}건의 절반 밑이라 '사라짐' 판정을 보류한다", flush=True)
    for pid in entries.keys() & posts.keys():
        posts[pid]["last_seen_at"] = now

    # 1차 후보 — 이미 싣고 있거나, 같은 슬러그로 아니라고 판정한 것은 뺀다.
    cands = [(pid, e) for pid, e in entries.items()
             if pid not in posts and rejected.get(pid) != e["slug"] and is_candidate(e["slug"])]
    cands.sort(key=lambda x: x[1]["lastmod"], reverse=True)
    fetched = new = closed_now = failed = 0
    for pid, e in cands[:new_limit]:
        try:
            d = fetch_detail(e["url"], pid)
        except Gone:
            rejected[pid] = e["slug"]
            continue
        except Exception as ex:                                  # noqa: BLE001
            failed += 1
            print(f"  [alba] {pid} 실패: {str(ex)[:80]}", flush=True)
            _sleep()
            continue
        finally:
            fetched += 1
        _sleep()
        if d is None:
            failed += 1
            continue
        cat = None if (d["opt_out"] or d["closed_reason"]) else classify(d["title"], d["content"])
        if not cat:
            rejected[pid] = e["slug"]
            continue
        posts[pid] = make_post(pid, e["url"], d, cat, now)
        seen_lastmod[pid] = e["lastmod"]
        new += 1

    # 재확인 — 사라진 것은 바로, 나머지 모집중은 오래 안 물어본 것부터.
    todo = plan_recheck(posts, entries, seen_lastmod, sitemap_ok,
                        skip={p for p in posts if posts[p].get("first_seen_at") == now}, limit=recheck_limit)
    for pid in todo:
        p = posts[pid]
        e = entries.get(pid)
        gone = d = None
        try:
            d = fetch_detail(e["url"] if e else p["url"], pid)
        except Gone as g:
            gone = str(g)
        except Exception as ex:                                  # noqa: BLE001
            print(f"  [alba] 재확인 {pid} 실패: {str(ex)[:80]}", flush=True)
        _sleep()
        was = p.get("status")
        res = apply_check(p, d, gone, now)
        if res == "drop":                                        # 작성자가 수집을 막았다 — 지운다
            posts.pop(pid)
            seen_lastmod.pop(pid, None)
            rejected[pid] = (e or {}).get("slug", "")
            continue
        if e:
            p["url"] = e["url"]
            seen_lastmod[pid] = e["lastmod"]
        if res == "closed" and was != "closed":
            closed_now += 1

    # 사이트맵에서 빠진 id 는 판정 기록에서도 지운다(다시 올라오면 새로 본다).
    rejected = {k: v for k, v in rejected.items() if k in entries}
    seen_lastmod = {k: v for k, v in seen_lastmod.items() if k in posts}
    rows = sorted(posts.values(), key=lambda p: p.get("posted_at") or p.get("first_seen_at") or "", reverse=True)
    report.update({"ok": True, "sitemap": len(entries), "candidates": len(cands), "fetched": fetched,
                   "failed": failed, "new": new, "rechecked": len(todo), "closed_now": closed_now,
                   "elapsed": round(time.time() - t0, 1)})
    out = {"updated_at": now, "started_at": doc.get("started_at") or now, "source": report,
           "categories": CATEGORIES, "posts": rows}
    _write_json(OUT_PATH, out)
    _write_json(STATE_PATH, {"rejected": rejected, "lastmod": seen_lastmod, "sitemap_count": len(entries)})
    open_n = sum(p["status"] == "open" for p in rows)
    print(f"[alba] 사이트맵 {len(entries)}건 · 후보 {len(cands)} · 상세 {fetched}(실패 {failed}) · 신규 {new} · "
          f"재확인 {len(todo)} → 마감 {closed_now} · 누적 {len(rows)}건(모집중 {open_n}) → {OUT_PATH}", flush=True)
    return {"ok": True, "total": len(rows), "open": open_n, "new": new, "closed_now": closed_now}


def main() -> None:
    args = _sys.argv[1:]
    if "--candidates" in args:
        entries = fetch_sitemap()
        for pid, e in sorted(entries.items(), key=lambda x: x[1]["lastmod"], reverse=True):
            if is_candidate(e["slug"]):
                print(pid, e["lastmod"][:10], e["slug"])
        return
    recheck = int(args[args.index("--recheck") + 1]) if "--recheck" in args else None
    if "--check" in args:                                        # 회차 사이 재확인(launchd albacheck)
        stats = check(recheck or CHECK_LIMIT)
        _sys.exit(0 if stats["ok"] else 1)
    new_limit = int(args[args.index("--new") + 1]) if "--new" in args else NEW_LIMIT
    stats = run(new_limit, recheck or RECHECK_LIMIT)
    _sys.exit(0 if stats["ok"] else 1)


if __name__ == "__main__":
    main()
