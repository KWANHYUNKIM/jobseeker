"""IT·디자인 공모전 크롤러 → jd-viewer/public/contests.json (누적).

컴퓨터로 하는 공모전만 모은다 — 개발·AI·데이터·해커톤·앱·게임, 그리고 컴퓨터로 만드는 디자인
(UI·UX·웹툰·일러스트·포스터·캐릭터)과 영상. 손으로 그리는 미술대회·건축·공간·조경·패션 같은
'디자인'은 뺀다(분류 규칙의 PHYSICAL).

**요약과 링크만 둔다.** 씽굿 약관 제24조가 영리 목적의 복제를 동의 없이 금한다. 그래서 세 곳 모두
같은 칸만 남긴다 — 제목·주최(기관 이름)·우리 분류·상금(짧게)·접수 시작/마감·참가 대상(짧게)·원문
주소·처음/마지막 본 시각·상태·마감 시각·이력. 요강 본문·포스터 이미지·담당자 이름·연락처·이메일은
받아도 버린다(씽굿 목록 JSON 에는 담당자 연락처와 요강 HTML 이 같이 오는데 한 칸도 옮기지 않는다).
자세한 요강과 접수는 원문에서 한다.

수집 경로 (2026-11-21 조사, robots.txt 를 다시 읽고 따른다):
  씽굿 thinkcontest.com   : robots 허용(로그인·파일·jsessionid 만 막는다). 공모전 목록 화면이 부르는
                            /thinkgood/user/contest/subList.do (POST JSON, 쪽당 10건) 를 분야
                            게임/소프트웨어·디자인·만화/캐릭터·영상/UCC × 접수중·접수예정으로 끝까지 읽는다.
                            상세는 view.do?contest_pk=N — 없는 글이면 '없는 게시글이거나 이미 삭제된' alert.
  위비티 wevity.com       : robots 전부 허용. 목록 ?c=find&gub=1&cidx=N&mode=ing|future (서버 렌더) —
                            20 웹/모바일/IT · 21 게임/소프트웨어 · 19 디자인/캐릭터/웹툰 · 10 영상/UCC/사진.
                            목록에는 마감 D-day 만 있어 새 공모전은 상세(gbn=view&ix=N)에서 기간·상금·대상을 읽는다.
                            지운 글은 '이미 삭제된 데이터' alert.
  콘테스트코리아           : robots 전부 허용, 약관에 수집 조항 없음. 목록 /sub/list.php 를 분야
  contestkorea.com          학문·과학·IT(030310001)·미술·디자인·웹툰(030610001)·사진·영상(031210001)에서
                            접수 마감 가까운 순(a.str_aedate asc)으로 읽는다. 상세 view.php?str_no=N,
                            없는 글은 '자료가 존재하지 않습니다' alert.

마감 규칙 (마감한 공모전도 지우지 않고 '마감'으로 남긴다 — 사용자 결정 2026-11-21):
  - 접수 마감일이 오늘(KST)보다 앞이면 마감. 네트워크 없이 매번 계산한다.
  - 원문이 지워졌으면(위 alert·404/410) 마감.
  - 그 출처 목록을 끝까지 읽었는데 안 보인 모집중 공모전은 상세를 다시 묻는다(GONE_LIMIT).
    출처 목록이 직전의 절반 밑으로 줄었으면 파서가 깨진 것으로 보고 그 출처의 '안 보임'을 보류한다.
  - 마감일이 미뤄지면(목록에 새 마감일) 다시 연다.

중복: 세 곳에 같은 공모전이 자주 같이 올라온다. 제목을 정규화(괄호·회차·연도·문장부호 제거)하고
마감일이 같으면 같은 공모전으로 보고 나중 것에 dup_of 를 단다 — 둘 다 남긴다(출처마다 원문 링크가 다르다).

하루 한 번이면 충분하다. 크롤 회차는 한 시간마다 돌지만 직전 성공이 MIN_INTERVAL_H 안이면 건너뛴다
(--force 로 무시). --check 는 목록을 안 읽고 마감만 다시 본다.

사용:
    python -m crawlers.crawl_contests              # 하루 한 번(12시간 안에 받았으면 건너뜀)
    python -m crawlers.crawl_contests --force      # 지금 받는다
    python -m crawlers.crawl_contests --check      # 목록 없이 마감 확인만(--recheck N)
    python -m crawlers.crawl_contests --dry        # 받아서 분류만 출력(파일을 안 쓴다)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import html as _html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.paths import VAR_DIR, VIEWER_PUBLIC
from crawlers.jobs_common import USER_AGENT, jitter

OUT_PATH = VIEWER_PUBLIC / "contests.json"
STATE_PATH = VAR_DIR / "contests" / "state.json"
# 회차 안(crawl_all)과 손으로 돌린 --check 가 겹치면 늦게 끝난 쪽이 먼저 끝난 쪽의 판정을 지운다.
LOCK_PATH = VAR_DIR / "contests" / "contests.lock"

MIN_INTERVAL_H = 12        # 직전 성공이 이 안이면 회차에서 건너뛴다(공모전은 하루 단위로 바뀐다)
DETAIL_LIMIT = 200         # 한 번에 받는 새 상세 수(위비티·콘테스트코리아)
GONE_LIMIT = 100           # 목록에서 안 보인 모집중 공모전 재확인 수
CHECK_LIMIT = 60           # --check 한 번에 묻는 수
LIST_MAX_PAGES = 25        # 출처·분야마다 목록 쪽 상한(파서가 깨져 끝없이 넘기지 않게)
LIST_MIN_RATIO = 0.5       # 출처 목록이 직전의 절반 밑이면 '안 보임'을 보류한다
SLEEP_MS = 1500
TIMEOUT = 25
HISTORY_MAX = 20
PRIZE_MAX = 40             # 상금 표기 길이 상한(요강 문장을 옮기지 않게)
TARGET_MAX = 40
KST = timezone(timedelta(hours=9))

SOURCES = {"thinkcontest": "씽굿", "wevity": "위비티", "contestkorea": "콘테스트코리아"}
SOURCE_ORDER = list(SOURCES)   # 중복이면 앞의 것이 대표

CATEGORIES = ["개발·AI·데이터", "해커톤", "앱·게임", "디자인·UI", "영상·콘텐츠", "기타 IT"]


# ── 분류 ──────────────────────────────────────────────────────────────
_E = r"(?<![a-z])"        # 영어 낱말 경계(한글 옆에 붙어 있어도 된다)
_Z = r"(?![a-z])"

HACK = re.compile(rf"해커톤|해카톤|{_E}hackathon|프롬프톤|{_E}promptathon|데이터톤|{_E}datathon|코드톤|메이커톤|{_E}ctf{_Z}")
APPGAME = re.compile(
    rf"게임(?!\s*체인저)|{_E}games?{_Z}|(?<![가-힣])앱(?!솔)|어플|애플리케이션|어플리케이션|모바일|메타버스|로블록스|"
    rf"마인크래프트|제페토|유니티|{_E}unity{_Z}|언리얼|{_E}roblox{_Z}")
VIDEO = re.compile(
    rf"영상|{_E}ucc{_Z}|숏폼|쇼츠|숏츠|{_E}shorts?{_Z}|릴스|유튜브|뮤직\s*비디오|뮤비|{_E}video{_Z}|애니메이션|모션\s*그래픽|"
    rf"(?:단편\s*)?영화(?!관)|{_E}films?{_Z}|드라마|미디어\s*(?:아트|작품|콘텐츠)|브이로그|{_E}vlog{_Z}|{_E}cf{_Z}")
# 디자인 낱말 중 '무엇을 만드는지'가 분명한 것. '디자인'·'굿즈'·'브랜딩'만 있으면 건축·제품일 수 있다.
SPECIFIC_DESIGN = (
    rf"{_E}ui{_Z}|{_E}ux{_Z}|캐릭터|이모티콘|웹툰|만화|일러스트|포스터|로고|엠블럼|심볼|마스코트|폰트|타이포|레터링|"
    rf"인포그래픽|카드\s*뉴스|썸네일|배너\s*디자인|그래픽|이미지|{_E}(?:bi|ci){_Z}|{_E}3d{_Z}")
DESIGN = re.compile(rf"{SPECIFIC_DESIGN}|디자인|굿즈|브랜딩|{_E}design{_Z}")
SPECIFIC_DESIGN = re.compile(SPECIFIC_DESIGN)
DEV = re.compile(
    rf"{_E}ai{_Z}|인공\s*지능|생성형|챗\s*gpt|{_E}gpt{_Z}|{_E}llm{_Z}|프롬프트|데이터|{_E}sw{_Z}|소프트웨어|코딩|"
    rf"프로그래밍|알고리즘|(?:{_E}sw|{_E}ai|서비스|프로그램|웹|앱|소프트웨어|시스템)\s*개발|개발자|{_E}ict{_Z}|{_E}it{_Z}|"
    rf"정보\s*(?:보호|보안|올림피아드)|사이버\s*보안|해킹|클라우드|블록\s*체인|챗봇|로봇|로보틱스|{_E}robotics{_Z}|"
    rf"자율\s*주행|{_E}iot{_Z}|사물\s*인터넷|디지털\s*트윈|머신\s*러닝|딥\s*러닝|컴퓨터|(?<![가-힣])웹(?!툰|소설|진)|"
    rf"{_E}web{_Z}|에이전트|{_E}(?:dx|ax){_Z}|디지털\s*(?:전환|혁신|서비스)|바이브\s*코딩|아두이노|라즈베리")

# 컴퓨터로 하지 않는 '디자인'·창작 — 디자인으로 잡혔는데 이게 있으면 IT 낱말(STRONG_IT)이 없는 한 뺀다.
# 영상·게임·해커톤에는 걸지 않는다('수목원·정원 숏폼 영상'은 영상 공모전이다).
PHYSICAL = re.compile(
    r"건축|공간\s*디자인|인테리어|조경|정원|가든|경관|간판|한옥|패션|의상|한복|공예|도자|가구|미술\s*(?:대전|대회|공모전)|"
    r"미술관|서예|사생|(?<![가-힣])그림(?!\s*책)|그리기|손\s*글씨|캘리|조각|설치\s*미술|업사이클|인형|뜨개|요리|헤어|"
    r"네일|메이크업|플로리스트|꽃꽂이|사진\s*(?:공모전|대회|콘테스트|전)")
# 공모전이 아닌 것(대외활동·교육 모집·지원 사업)과 게임을 '하는' 대회(e스포츠 — 만드는 공모전이 아니다).
NOT_CONTEST = re.compile(
    rf"서포터즈|기자단|홍보\s*대사|체험단|봉사단|원정대|교육생|수강생|부트\s*캠프|평가단|모니터링단|지원\s*사업|"
    rf"(?:유튜버|크리에이터)\s*모집|e\s*스포츠|{_E}e\s*sports?{_Z}|{_E}esports?{_Z}")
STRONG_IT = re.compile(rf"{_E}ai{_Z}|인공\s*지능|생성형|코딩|소프트웨어|{_E}sw{_Z}|해커톤|데이터|(?<![가-힣])앱|게임|메타버스|웹툰|{_E}3d{_Z}|{_E}ui{_Z}|{_E}ux{_Z}")
# 출처 분야가 IT 면 제목에 낱말이 없어도 '기타 IT' 로 둔다(위비티 웹/모바일/IT·게임/SW, 씽굿 게임/SW).
IT_FIELD = re.compile(r"웹/모바일|게임/소프트웨어")
ARCH_FIELD = re.compile(r"건축")

_RULES = [
    ("해커톤", HACK),
    ("앱·게임", APPGAME),
    ("영상·콘텐츠", VIDEO),
    ("디자인·UI", DESIGN),
    ("개발·AI·데이터", DEV),
]


def norm(text: str) -> str:
    t = _html.unescape(text or "").lower()
    t = re.sub(r"[-_/|·•,()\[\]{}<>!?~★☆♥※*\"'“”‘’「」『』:;.]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(title: str, fields: str = "") -> str | None:
    """우리 분류 하나, 컴퓨터로 하는 공모전이 아니면 None. fields 는 출처의 분야 표기(판정 보조)."""
    t = norm(title)
    if NOT_CONTEST.search(t):
        return None
    physical = bool(PHYSICAL.search(t)) and not STRONG_IT.search(t)
    for name, rx in _RULES:
        if rx.search(t):
            if name == "디자인·UI" and (physical or (ARCH_FIELD.search(fields) and not SPECIFIC_DESIGN.search(t))):
                return None
            return name
    if physical:
        return None
    if IT_FIELD.search(fields):
        return "기타 IT"
    if fields.strip() == "영상/UCC":      # 씽굿에서 분야가 영상/UCC 하나뿐인 것('콘텐츠 공모전' 같은 제목)
        return "영상·콘텐츠"
    return None


# ── 공통 ──────────────────────────────────────────────────────────────
class Gone(Exception):
    """원문이 지워졌다(alert·404/410)."""


def _today() -> date:
    return datetime.now(KST).date()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sleep() -> None:
    time.sleep(jitter(SLEEP_MS) / 1000)


def _get(url: str, data: bytes | None = None, json_body: bool = False) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9",
               "Accept": "application/json" if json_body else "text/html,application/xhtml+xml"}
    if json_body:
        headers["Content-Type"] = "application/json; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise Gone(f"원본 삭제(HTTP {e.code})") from None
        raise
    return raw.decode("utf-8", "replace")


def _text(fragment: str) -> str:
    """태그를 걷어 낸 한 줄."""
    t = re.sub(r"<!--.*?-->", " ", fragment or "", flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", _html.unescape(t)).strip()


def short(text: str | None, limit: int) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip(" ,:")
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def short_target(items: list[str]) -> str:
    """참가 대상 표기 — '제한 없음' 이 있으면 그것 하나, 아니면 앞의 넷 + '외'."""
    xs = [re.sub(r"\s+", " ", x).strip() for x in items if x and x.strip()]
    if any(x in ("제한 없음", "제한없음", "누구나") for x in xs):
        return "제한 없음"
    out = "·".join(xs[:4]) + (" 외" if len(xs) > 4 else "")
    return short(out, TARGET_MAX)


def _ymd(s: str | None) -> str | None:
    m = re.search(r"(20\d\d)[.\-/](\d{1,2})[.\-/](\d{1,2})", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def period(s: str | None) -> tuple[str | None, str | None]:
    """'2026-11-16 ~ 2026-12-11' · '2026.10.21 ~ 2026.12.20' → (시작, 마감)."""
    parts = re.split(r"~", s or "", maxsplit=1)
    if len(parts) == 2:
        return _ymd(parts[0]), _ymd(parts[1])
    return None, _ymd(s)


def dday_end(dday: str | None, today: date) -> str | None:
    """목록의 'D-23' → 마감일. 'D-day'·'D-0' 은 오늘."""
    m = re.search(r"D\s*-\s*(\d+)", dday or "", re.I)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    if re.search(r"D\s*-?\s*day", dday or "", re.I):
        return today.isoformat()
    return None


def prize_text(*cands: str | None) -> str:
    for c in cands:
        t = short(_text(c or ""), PRIZE_MAX)
        if t and t not in ("-", "없음"):
            return t
    return ""


# ── 씽굿 ──────────────────────────────────────────────────────────────
TC_BASE = "https://www.thinkcontest.com"
TC_LIST = f"{TC_BASE}/thinkgood/user/contest/subList.do"
TC_FIELDS = "CCFD002|CCFD009|CCFD010|CCFD014"     # 게임/소프트웨어·디자인·만화/캐릭터·영상/UCC
TC_PROCESSES = ("ING", "YET")                     # 접수중(마감임박 포함)·접수예정
TC_GONE = "없는 게시글이거나 이미 삭제된 게시글"


def tc_url(pk) -> str:
    return f"{TC_BASE}/thinkgood/user/contest/view.do?contest_pk={pk}"


def tc_parse_list(raw: str) -> tuple[list[dict], int, int]:
    """subList.do 응답 → (요약 행들, 전체 건수, 쪽당 건수). 연락처·요강은 여기서 버린다."""
    d = json.loads(raw)
    if str(d.get("status")) != "1":
        raise RuntimeError(f"씽굿 목록 응답 실패: {str(d.get('msg'))[:60]}")
    rows = []
    for x in d.get("listJsonData") or []:
        pk = x.get("contest_pk")
        title = _text(x.get("program_nm") or "")
        if not pk or not title:
            continue
        start, end = _ymd(x.get("accept_dt")), _ymd(x.get("finish_dt"))
        if not end:
            start, end = period(x.get("receive_period"))
        rows.append({
            "sid": str(pk), "title": title, "url": tc_url(pk),
            "host": short(_text(x.get("host_company") or ""), 60),
            "fields": x.get("contest_field_nm") or "",
            "prize": prize_text(x.get("prize_money")),
            "target": short_target((x.get("enter_qualified_nm") or "").split(",")),
            "period_start": start, "period_end": end,
        })
    return rows, int(d.get("totalcnt") or 0), int(d.get("recordsPerPage") or 10)


def tc_list() -> list[dict]:
    out: dict[str, dict] = {}
    for proc in TC_PROCESSES:
        page = 1
        while page <= LIST_MAX_PAGES:
            body = {"searchProcess": proc, "recordsPerPage": 10, "currentPageNo": page,
                    "contest_field": TC_FIELDS, "host_organ": "", "enter_qualified": "", "award_size": "",
                    "searchStatus": "Y", "sidx": "d_day", "sord": "ASC"}
            rows, total, per = tc_parse_list(_get(TC_LIST, json.dumps(body).encode(), json_body=True))
            _sleep()
            for r in rows:
                out.setdefault(r["sid"], r)
            if not rows or page * max(per, 1) >= total:
                break
            page += 1
    return list(out.values())


def tc_parse_detail(page: str) -> dict:
    if TC_GONE in page:
        raise Gone("원본 삭제(없는 게시글)")
    raw = dict(re.findall(r'<div class="tit">([^<]+)</div>\s*<div class="txt">(.*?)</div>\s*</div>', page, re.S))
    raw = {k.strip(): v for k, v in raw.items()}
    lis = lambda k: [_text(x) for x in re.findall(r"<li>(.*?)</li>", raw.get(k) or "", re.S)]  # noqa: E731
    info = {k: _text(v) for k, v in raw.items()}
    t = re.search(r'name="sns_program_nm" value="([^"]*)"', page)
    if not t and not info:
        raise ValueError("씽굿 상세 모양이 다르다")
    start, end = period(info.get("접수기간"))
    return {"title": _html.unescape(t.group(1)).strip() if t else "", "host": short(info.get("주최") or "", 60),
            "fields": ", ".join(lis("응모분야")), "prize": prize_text(info.get("시상금(1등)"), info.get("총상금")),
            "target": short_target(lis("참가자격")), "period_start": start, "period_end": end}


# ── 위비티 ────────────────────────────────────────────────────────────
WV_BASE = "https://www.wevity.com/"
WV_CIDX = (20, 21, 19, 10)
WV_MODES = ("ing", "future")
WV_GONE = "이미 삭제된 데이터"


def wv_url(ix) -> str:
    return f"{WV_BASE}?c=find&s=1&gbn=view&ix={ix}"


def wv_parse_list(page: str) -> tuple[list[dict], list[int]]:
    """목록 → (행들, 이어지는 쪽 번호들). 행에는 마감 D-day 만 있고 날짜는 상세에서 읽는다."""
    m = re.search(r'<ul class="list">(.*?)</ul>\s*(?:<div class=.list-navi.>(.*?)</div>)?', page, re.S)
    if not m:
        return [], []
    rows = []
    for li in re.split(r"<li\b", m.group(1))[1:]:
        a = re.search(r'<div class="tit">\s*<a href="([^"]*ix=(\d+)[^"]*)">(.*?)</a>', li, re.S)
        if not a:
            continue
        title = _text(re.sub(r"<span class='stat[^']*'>.*?</span>", "", a.group(3)))
        fields = _text(re.search(r'<div class="sub-tit">(.*?)</div>', li, re.S).group(1)) if 'sub-tit' in li else ""
        organ = re.search(r'<div class="organ">(.*?)</div>', li, re.S)
        day = re.search(r'<div class="day">(.*?)</div>', li, re.S)
        st = re.search(r'class="dday (\w+)"', li)
        rows.append({"sid": a.group(2), "title": title, "url": wv_url(a.group(2)),
                     "fields": re.sub(r"^분야\s*:\s*", "", fields),
                     "host": short(_text(organ.group(1)) if organ else "", 60),
                     "dday": _text(day.group(1)) if day else "", "state": st.group(1) if st else ""})
    pages = sorted({int(x) for x in re.findall(r"gp=(\d+)", page[m.end(1):m.end(1) + 6000])})
    return rows, pages


def wv_list() -> list[dict]:
    out: dict[str, dict] = {}
    for cidx in WV_CIDX:
        for mode in WV_MODES:
            gp, seen_pages = 1, set()
            while gp and gp <= LIST_MAX_PAGES and gp not in seen_pages:
                seen_pages.add(gp)
                rows, pages = wv_parse_list(_get(f"{WV_BASE}?c=find&s=1&gub=1&cidx={cidx}&mode={mode}&gp={gp}"))
                _sleep()
                for r in rows:
                    if r["state"] != "end":
                        out.setdefault(r["sid"], r)
                nxt = [p for p in pages if p > gp]
                gp = nxt[0] if rows and nxt else 0
    return list(out.values())


def wv_parse_detail(page: str) -> dict:
    if WV_GONE in page:
        raise Gone("원본 삭제(이미 삭제된 데이터)")
    t = re.search(r'<h6 class="tit">(.*?)</h6>', page, re.S)
    ul = re.search(r'<ul class="cd-info-list">(.*?)</ul>', page, re.S)
    if not t or not ul:
        raise ValueError("위비티 상세 모양이 다르다")
    info = {}
    body = re.sub(r"<!--.*?-->", "", ul.group(1), flags=re.S)       # 주석 처리된 칸(<!--li>참가조건</li-->)
    for name, val in re.findall(r'<span class="tit">([^<]*)</span>(.*?)</li>', body, re.S):
        info[name.strip()] = _text(re.sub(r'<span class="cil-dday">.*?</span>', "", val, flags=re.S))
    start, end = period(info.get("접수기간"))
    return {"title": _text(t.group(1)), "host": short(info.get("주최/주관") or "", 60),
            "fields": info.get("분야") or "", "prize": prize_text(info.get("총 상금"), info.get("1등 상금")),
            "target": short_target((info.get("응모대상") or "").split(",")),
            "period_start": start, "period_end": end}


# ── 콘테스트코리아 ────────────────────────────────────────────────────
CK_BASE = "https://www.contestkorea.com/sub/"
CK_BCODES = ("030310001", "030610001", "031210001")   # 학문·과학·IT · 미술·디자인·웹툰 · 사진·영상·영화제
CK_GONE = "자료가 존재하지 않습니다"
CK_FIELD = {"030310001": "학문•과학•IT", "030610001": "미술•디자인•웹툰", "031210001": "사진•영상•영화제"}


def ck_url(no, bcode: str = "") -> str:
    b = f"&Txt_bcode={bcode}" if bcode else ""
    return f"{CK_BASE}view.php?int_gbn=1{b}&str_no={no}"


def ck_parse_list(page: str) -> tuple[list[dict], int]:
    """목록 → (행들, 마지막 쪽). 접수 기간은 연도가 없어서 마감일은 D-day 로 센다(상세에서 고친다)."""
    i = page.find('<div class="list_style_2">')
    if i < 0:
        return [], 0
    seg = page[i:]
    rows = []
    for li in seg.split('<div class="title">')[1:]:
        a = re.search(r'href="(?:/sub/)?view\.php\?int_gbn=1&(?:amp;)?Txt_bcode=(\d+)&(?:amp;)?str_no=(\d+)"', li)
        t = re.search(r'<span class="txt">(.*?)</span>', li, re.S)
        if not a or not t:
            continue
        host = re.search(r'<li class="icon_1"><strong>주최</strong>\s*\.(.*?)</li>', li, re.S)
        target = re.search(r'<li class="icon_2"><strong>대상</strong>\s*\.(.*?)</li>', li, re.S)
        day = re.search(r'<span class="day"[^>]*>([^<]*)</span>', li)
        cond = re.search(r'<span class="condition"[^>]*>([^<]*)</span>', li)
        rows.append({"sid": a.group(2), "title": _text(t.group(1)), "url": ck_url(a.group(2), a.group(1)),
                     "host": short(_text(host.group(1)) if host else "", 60),
                     "target": short_target(_text(target.group(1)).split(",")) if target else "",
                     "fields": CK_FIELD.get(a.group(1), a.group(1)), "dday": day.group(1).strip() if day else "",
                     "state": cond.group(1).strip() if cond else ""})
    last = max([int(x) for x in re.findall(r"page=(\d+)'><img src='/img/common/page_arrow_4", seg)] or [1])
    return rows, last


def ck_list() -> list[dict]:
    out: dict[str, dict] = {}
    for b in CK_BCODES:
        page, last = 1, 1
        while page <= min(last, LIST_MAX_PAGES):
            rows, last = ck_parse_list(_get(
                f"{CK_BASE}list.php?displayrow=12&int_gbn=1&Txt_bcode={b}&Txt_sortkey=a.str_aedate"
                f"&Txt_sortword=asc&page={page}"))
            _sleep()
            live = [r for r in rows if r["state"] in ("접수중", "접수예정", "마감임박")]
            for r in live:
                out.setdefault(r["sid"], r)
            if not live:                    # 마감순으로 접수중이 다 지나갔다
                break
            page += 1
    return list(out.values())


def ck_parse_detail(page: str) -> dict:
    if CK_GONE in page:
        raise Gone("원본 삭제(자료가 존재하지 않음)")
    t = re.search(r'<div class="view_top_area clfx">\s*<h1>(.*?)</h1>', page, re.S)
    if not t:
        raise ValueError("콘테스트코리아 상세 모양이 다르다")
    info = {}
    for name, val in re.findall(r'<th scope="row">([^<]*)</th>\s*<td>(.*?)</td>', page, re.S):
        info.setdefault(re.sub(r"\s+", " ", name).strip(), _text(val))
    start, end = period(info.get("접수기간"))
    prize = re.sub(r"^기타\s*:\s*", "", info.get("시상내역") or "")
    return {"title": _text(t.group(1)), "host": short(info.get("주최 . 주관") or "", 60),
            "fields": info.get("대표분야") or "", "prize": prize_text(prize),
            "target": short_target((info.get("참가대상") or "").split(",")),
            "period_start": start, "period_end": end}


LISTERS = {"thinkcontest": tc_list, "wevity": wv_list, "contestkorea": ck_list}
DETAIL = {"thinkcontest": tc_parse_detail, "wevity": wv_parse_detail, "contestkorea": ck_parse_detail}
# 목록만으로 저장 칸이 다 차는 곳(씽굿 목록 JSON 에는 기간·상금·대상이 다 있다).
LIST_COMPLETE = {"thinkcontest"}


def fetch_detail(source: str, url: str) -> dict:
    return DETAIL[source](_get(url))


# ── 누적·판정 ─────────────────────────────────────────────────────────
KEEP = ("title", "host", "prize", "target", "period_start", "period_end")


def make_contest(source: str, row: dict, d: dict, category: str, now: str) -> dict:
    c = {"id": f"{source}-{row['sid']}", "source": source, "url": row["url"], "category": category,
         "status": "open", "first_seen_at": now, "last_seen_at": now, "checked_at": now}
    for k in KEEP:                       # 상세 값이 우선, 없으면 목록 값
        v = d.get(k) if d.get(k) not in (None, "") else row.get(k)
        c[k] = v if v not in (None, "") else (None if k.startswith("period_") else "")
    c["history"] = [_snap(c, now)]
    return c


def _snap(c: dict, at: str) -> dict:
    return {"at": at, "status": c.get("status"), "period_end": c.get("period_end"), "prize": c.get("prize") or None}


def _push_history(c: dict, now: str) -> None:
    hist = list(c.get("history") or [])
    last = hist[-1] if hist else {}
    snap = _snap(c, now)
    if any(last.get(k) != snap[k] for k in ("status", "period_end", "prize")):
        hist.append(snap)
    c["history"] = hist[-HISTORY_MAX:]


def _close(c: dict, reason: str, at: str) -> bool:
    if c.get("status") == "closed":
        return False
    c["status"], c["closed_reason"], c["closed_at"] = "closed", reason, at
    return True


def _reopen(c: dict) -> None:
    c["status"] = "open"
    c.pop("closed_at", None)
    c.pop("closed_reason", None)


def apply_deadline(c: dict, today: date, now: str) -> bool:
    """마감일이 지났으면 닫는다(네트워크 없음). 마감일이 미뤄져 다시 살아났으면 연다. 닫았으면 True."""
    end = c.get("period_end")
    if c.get("status") == "closed" and c.get("closed_reason") == "접수 마감" and end and end >= today.isoformat():
        _reopen(c)
        _push_history(c, now)
        return False
    if c.get("status") == "open" and end and end < today.isoformat():
        _close(c, "접수 마감", f"{end}T23:59:59+09:00")
        _push_history(c, now)
        return True
    return False


def apply_check(c: dict, d: dict | None, gone: str | None, now: str) -> str:
    """상세 재확인 결과 반영. 'closed'·'open'·'unknown'."""
    c["checked_at"] = now
    if gone:
        _close(c, gone, now)
        _push_history(c, now)
        return "closed"
    if d is None:
        return "unknown"
    for k in KEEP:
        if d.get(k) not in (None, ""):
            c[k] = d[k]
    if c.get("status") == "closed" and c.get("closed_reason", "").startswith("원본 삭제"):
        _reopen(c)                       # 지웠다가 다시 올렸다
    _push_history(c, now)
    return "open"


def dedupe_key(title: str) -> str:
    """회차·연도·'공모전'·'참가자 모집' 같은 꼬리말을 떼고 글자만 남긴다. 괄호 안(주최 표기·말머리)은
    남긴다 — 제목 전체가 괄호인 곳이 있다('[2026 서울관광 프롬프톤] 참가자모집'). 앞뒤 수식어 차이는
    mark_dups 가 '한쪽이 다른 쪽을 품는가'로 본다."""
    t = re.sub(r"제?\s*\d+\s*회|20\d\d\s*년?|공모전|경진\s*대회|대회|챌린지|콘테스트|공모|"
               r"(?:참가\s*(?:자|팀)?\s*)?모집|공고|내용\s*수정", " ", norm(title))
    return re.sub(r"[^0-9a-z가-힣]+", "", t)


def mark_dups(contests: list[dict]) -> int:
    """정규화 제목 + 마감일이 같으면 같은 공모전. 출처 순서(씽굿→위비티→콘테스트코리아)가 앞인 것이 대표.
    한쪽 제목이 다른 쪽을 품어도(앞뒤 수식어 차이) 마감일이 같으면 같다고 본다."""
    order = {s: i for i, s in enumerate(SOURCE_ORDER)}
    rows = sorted(contests, key=lambda c: (order.get(c["source"], 9), c.get("first_seen_at") or ""))
    by_end: dict[str, list[tuple[str, dict]]] = {}
    n = 0
    for c in rows:
        c.pop("dup_of", None)
        end, key = c.get("period_end"), dedupe_key(c.get("title") or "")
        if not end or len(key) < 4:
            continue
        for k2, rep in by_end.get(end, []):
            if rep["source"] != c["source"] and (k2 == key or (min(len(k2), len(key)) >= 6 and (k2 in key or key in k2))):
                c["dup_of"] = rep["id"]
                n += 1
                break
        else:
            by_end.setdefault(end, []).append((key, c))
    return n


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


def _try_lock(fh) -> bool:
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


def due(state: dict, now: datetime | None = None, hours: float = MIN_INTERVAL_H) -> bool:
    """직전 성공이 hours 안이면 False — 회차마다 세 사이트를 두드리지 않게."""
    last = state.get("last_ok_at")
    if not last:
        return True
    try:
        then = datetime.fromisoformat(last)
    except ValueError:
        return True
    now = now or datetime.now().astimezone()
    return (now - then) >= timedelta(hours=hours)


def _stats(rows: list[dict], **extra) -> dict:
    by_source = {s: sum(c["source"] == s for c in rows) for s in SOURCES}
    return {"total": len(rows), "open": sum(c["status"] == "open" for c in rows),
            "by_source": by_source, **extra}


def _output(doc: dict, contests: dict[str, dict], report: dict, now: str) -> list[dict]:
    rows = list(contests.values())
    mark_dups(rows)
    rows.sort(key=lambda c: (c["status"] != "open", c.get("period_end") or "9999", c["id"]))
    _write_json(OUT_PATH, {"updated_at": now, "started_at": doc.get("started_at") or now, "source": report,
                           "sources": SOURCES, "categories": CATEGORIES, "contests": rows})
    return rows


def run(force: bool = False, detail_limit: int = DETAIL_LIMIT, gone_limit: int = GONE_LIMIT,
        dry: bool = False) -> dict:
    """한 번. 잠금을 못 잡으면 건너뛰고, 직전 성공이 12시간 안이면(force 가 아니면) 마감일 계산만 한다."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as fh:
        if not _try_lock(fh):
            print("[contests] 다른 쪽이 contests.json 을 쓰는 중 — 이번엔 건너뜀", flush=True)
            return {"ok": True, "skipped": True, "reason": "locked", "new": 0, "closed_now": 0}
        state = _load_json(STATE_PATH, {})
        if not force and not dry and not due(state):
            return _deadline_only(state)
        return _run(state, detail_limit, gone_limit, dry)


def _deadline_only(state: dict) -> dict:
    """받지 않는 회차 — 마감일 지난 것만 닫아 둔다(네트워크 없음)."""
    now, today = _now(), _today()
    doc = _load_json(OUT_PATH, {"contests": []})
    contests = {c["id"]: c for c in doc.get("contests") or []}
    closed_now = sum(apply_deadline(c, today, now) for c in contests.values())
    if closed_now:
        rows = _output(doc, contests, {**(doc.get("source") or {}), "deadline_at": now}, doc.get("updated_at") or now)
    else:
        rows = list(contests.values())
    print(f"[contests] 직전 수집 {state.get('last_ok_at')} — {MIN_INTERVAL_H}시간 안이라 건너뜀"
          f"(마감일 지나 닫은 것 {closed_now}건)", flush=True)
    return {"ok": True, "skipped": True, "reason": "fresh", "new": 0, "closed_now": closed_now, **_stats(rows)}


def _run(state: dict, detail_limit: int, gone_limit: int, dry: bool) -> dict:
    now, today = _now(), _today()
    doc = _load_json(OUT_PATH, {"contests": []})
    contests: dict[str, dict] = {c["id"]: c for c in doc.get("contests") or []}
    rejected: dict[str, str] = state.get("rejected") or {}       # id → 아니라고 본 제목(제목이 바뀌면 다시 본다)
    prev_counts: dict[str, int] = state.get("list_counts") or {}
    t0 = time.time()
    report: dict = {"ok": False, "at": now, "sources": {}}
    seen: dict[str, set[str]] = {}
    counts: dict[str, int] = {}
    new = failed = fetched = closed_now = 0
    new_by_source = {s: 0 for s in SOURCES}

    for source, lister in LISTERS.items():
        try:
            rows = lister()
        except Exception as e:                                   # noqa: BLE001 — 한 곳이 깨져도 나머지는 받는다
            print(f"[contests] {SOURCES[source]} 목록 실패: {str(e)[:120]}", flush=True)
            report["sources"][source] = {"ok": False, "error": str(e)[:200]}
            continue
        counts[source] = len(rows)
        prev = prev_counts.get(source) or 0
        list_ok = not prev or len(rows) >= prev * LIST_MIN_RATIO
        if not list_ok:
            print(f"[contests] {SOURCES[source]} 목록 {len(rows)}건 — 직전 {prev}건의 절반 밑이라 '안 보임'을 보류", flush=True)
        else:
            seen[source] = set()
        src_new = 0
        for r in rows:
            cid = f"{source}-{r['sid']}"
            if source in seen:
                seen[source].add(cid)
            c = contests.get(cid)
            if c:
                c["last_seen_at"] = now
                end = r.get("period_end") or dday_end(r.get("dday"), today)
                if source in LIST_COMPLETE:
                    apply_check(c, r, None, now)
                elif end and end != c.get("period_end") and fetched < detail_limit:
                    # 마감일이 달라졌다(연장·조기 마감) — 상세에서 정확한 날짜를 다시 읽는다.
                    try:
                        apply_check(c, fetch_detail(source, c["url"]), None, now)
                    except Gone as g:
                        apply_check(c, None, str(g), now)
                    except Exception as ex:                      # noqa: BLE001
                        print(f"  [contests] {cid} 상세 실패: {str(ex)[:80]}", flush=True)
                    fetched += 1
                    _sleep()
                continue
            title = r["title"]
            if rejected.get(cid) == title:
                continue
            cat = classify(title, r.get("fields") or "")
            if not cat:
                rejected[cid] = title
                continue
            if source in LIST_COMPLETE:
                d = r
            else:
                if fetched >= detail_limit:
                    continue
                fetched += 1
                try:
                    d = fetch_detail(source, r["url"])
                except Gone:
                    continue
                except Exception as ex:                          # noqa: BLE001
                    failed += 1
                    print(f"  [contests] {cid} 상세 실패: {str(ex)[:80]}", flush=True)
                    _sleep()
                    continue
                _sleep()
                if not d.get("period_end"):
                    d["period_end"] = dday_end(r.get("dday"), today)
                cat = classify(d.get("title") or title, d.get("fields") or r.get("fields") or "") or cat
            contests[cid] = make_contest(source, r, d, cat, now)
            new += 1
            src_new += 1
        new_by_source[source] = src_new
        report["sources"][source] = {"ok": True, "listed": len(rows), "new": src_new, "list_ok": list_ok}

    # 목록을 끝까지 읽은 출처에서 안 보인 모집중 공모전 — 원문에 다시 묻는다(지워졌으면 마감).
    gone_todo = [c for c in contests.values()
                 if c["status"] == "open" and c["source"] in seen and c["id"] not in seen[c["source"]]
                 and not (c.get("period_end") and c["period_end"] < today.isoformat())]
    gone_todo.sort(key=lambda c: c.get("checked_at") or "")
    rechecked = 0
    for c in gone_todo[:gone_limit]:
        res = _recheck(c, now)
        rechecked += 1
        closed_now += res == "closed"
    closed_now += sum(apply_deadline(c, today, now) for c in contests.values())

    rejected = {k: v for k, v in rejected.items() if any(k in s for s in seen.values()) or k.split("-")[0] not in seen}
    ok = any(v.get("ok") for v in report["sources"].values())
    report.update({"ok": ok, "fetched": fetched, "failed": failed, "new": new, "rechecked": rechecked,
                   "closed_now": closed_now, "elapsed": round(time.time() - t0, 1)})
    if dry:
        for c in sorted(contests.values(), key=lambda c: (c["category"], c["id"])):
            if c.get("first_seen_at") == now:
                print(f"  {c['category']:<10} {c['id']:<26} {c.get('period_end')} {c['title'][:60]}")
        rows = list(contests.values())
        mark_dups(rows)
        return {"ok": ok, **_stats(rows), "new": new, "closed_now": closed_now}
    rows = _output(doc, contests, report, now)
    new_state = {"rejected": rejected, "list_counts": {**prev_counts, **counts},
                 "last_ok_at": now if ok else state.get("last_ok_at"), "last_run_at": now}
    _write_json(STATE_PATH, new_state)
    st = _stats(rows, new=new, closed_now=closed_now, new_by_source=new_by_source,
                dups=sum(1 for c in rows if c.get("dup_of")))
    print(f"[contests] 목록 {counts} · 상세 {fetched}(실패 {failed}) · 신규 {new} · 재확인 {rechecked} → 마감 {closed_now} · "
          f"누적 {st['total']}건(모집중 {st['open']}, 중복 {st['dups']}) → {OUT_PATH}", flush=True)
    return {"ok": ok, **st}


def _recheck(c: dict, now: str) -> str:
    gone = d = None
    try:
        d = fetch_detail(c["source"], c["url"])
    except Gone as g:
        gone = str(g)
    except Exception as ex:                                      # noqa: BLE001
        print(f"  [contests] 재확인 {c['id']} 실패: {str(ex)[:80]}", flush=True)
    _sleep()
    was = c["status"]
    res = apply_check(c, d, gone, now)
    return "closed" if res == "closed" and was != "closed" else res


def check(limit: int = CHECK_LIMIT) -> dict:
    """목록을 안 읽고 마감만 — 마감일 계산 + 오래 안 물어본 모집중 공모전 limit 건을 원문에 묻는다."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as fh:
        if not _try_lock(fh):
            print("[contests] 다른 쪽이 도는 중 — 마감 확인 건너뜀", flush=True)
            stats = {"ok": True, "skipped": True, "closed_now": 0}
        else:
            now, today = _now(), _today()
            doc = _load_json(OUT_PATH, {"contests": []})
            contests = {c["id"]: c for c in doc.get("contests") or []}
            closed_now = sum(apply_deadline(c, today, now) for c in contests.values())
            todo = sorted((c for c in contests.values() if c["status"] == "open"),
                          key=lambda c: c.get("checked_at") or "")[:limit]
            for c in todo:
                closed_now += _recheck(c, now) == "closed"
            rows = _output(doc, contests, {**(doc.get("source") or {}), "checked_at": now}, doc.get("updated_at") or now)
            stats = {"ok": True, **_stats(rows), "rechecked": len(todo), "closed_now": closed_now}
            print(f"[contests] 마감 확인 {len(todo)}건 → 마감 {closed_now} · 모집중 {stats['open']}", flush=True)
            try:
                from store.ingest.docs import sync
                sync()
            except Exception as e:                               # noqa: BLE001 — DB 가 없어도 파일은 이미 갱신됐다
                print(f"[contests] 뷰어 문서 동기화 건너뜀: {str(e)[:120]}", flush=True)
    try:
        from automation import orchestration as orch
        orch.emit("contests_check", **{k: v for k, v in stats.items() if k != "by_source"})
    except Exception:                                            # noqa: BLE001
        pass
    return stats


def main() -> None:
    args = _sys.argv[1:]
    if "--check" in args:
        n = int(args[args.index("--recheck") + 1]) if "--recheck" in args else CHECK_LIMIT
        _sys.exit(0 if check(n)["ok"] else 1)
    stats = run(force="--force" in args, dry="--dry" in args)
    print(json.dumps(stats, ensure_ascii=False))
    _sys.exit(0 if stats["ok"] else 1)


if __name__ == "__main__":
    main()
