"""인스타 합격·스펙 카드 수집 — 사용자 계정으로 로그인해 둔 전용 크롬을 이어받아 읽기만 한다.

    python -m careers.instagram [--posts 30] [--tags 개발자합격,부트캠프수료]

- 크롬: var/careers/ig-chrome 프로필, --remote-debugging-port=9333 (start-careers 와 별개로 띄운다)
- 읽기만 한다: 좋아요·팔로우·댓글·DM 없음. 게시물 사이 6~12초, 회차당 게시물 수 상한.
- 작성자 계정은 남기지 않는다 — 게시물 주소(/p/<코드>/)와 캡션(@멘션 지움), 카드 이미지만
  inbox/<시각>-ig-<코드>/ 에 두면 다음 회차 run_inbox 가 그래픽카드 OCR 로 글로 바꾼다.
"""
from __future__ import annotations

import argparse
import random
import re
import time
from datetime import datetime
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from . import checks, store

CDP = "http://127.0.0.1:9333"
TAGS = ["개발자합격", "개발자취업", "개발자이직", "신입개발자", "개발자취준", "부트캠프수료", "코딩부트캠프",
        "백엔드개발자", "프론트엔드개발자", "개발자합격후기", "개발자취업후기", "코딩테스트", "싸피", "우테코",
        "비전공개발자", "개발자커리어", "it취업", "네카라쿠배", "개발자대기업합격", "개발자공채합격"]
# 검색어는 전부 IT 낱말을 단다 — '합격후기'·'이력서' 만으로는 입시·공무원·체대 글이 대부분이다(2026-11, #합격자명단 → 체대입시 명단)
DOC_TAGS = ["개발자포트폴리오", "개발자이력서", "개발자자소서", "it자소서", "개발자서류합격", "개발자이력서피드백"]
EXP_TAGS = ["개발자경력직", "개발자이직준비", "개발자이직성공", "개발자이직후기", "개발자이직", "개발자면접", "개발자연봉협상",
            "시니어개발자", "주니어개발자", "년차개발자", "개발자연봉", "테크리드", "개발자브이로그"]   # 경력직 — 회차마다 둘은 여기서
AGE_TAGS = ["늦은나이개발자", "30대개발자취업", "30대개발자", "30대비전공개발자", "늦깎이개발자", "나이많은신입개발자", "개발자취업합격",
            "개발자최종합격", "it취업후기", "40대개발자", "30대개발자이직"]   # 나이가 같이 나오는 합격 글
REVIEW_TAGS = ["개발자합격후기", "개발자취업후기", "개발자면접후기", "코테후기", "코딩테스트후기", "개발자서류합격", "개발자최종합격후기",
               "부트캠프후기", "it국비지원후기", "부트캠프수료후기", "싸피후기", "개발자이직후기", "개발자인턴후기", "개발자후기"]
SEEN = store.DIR / "ig_seen.json"
_HANDLE = re.compile(r"@[\w.]+")


CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = store.DIR / "ig-chrome"


def _ensure_chrome() -> None:
    """전용 크롬이 꺼져 있으면 띄운다(로그인은 프로필에 남아 있다)."""
    import subprocess
    import urllib.request
    def up():
        try:
            urllib.request.urlopen(CDP + "/json/version", timeout=2)
            return True
        except Exception:
            return False
    if up():
        return
    subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", "--remote-debugging-port=9333",
                      "--remote-debugging-address=127.0.0.1", "--no-first-run", "--start-minimized",
                      "https://www.instagram.com/"], creationflags=0x00000008 | 0x00000200)  # DETACHED | NEW_GROUP
    for _ in range(20):
        time.sleep(1)
        if up():
            return
    raise SystemExit("전용 크롬을 못 띄웠어요")


def it_tag(tag: str) -> str:
    """IT 낱말이 없는 태그에는 '개발자' 를 붙인다(it·sw 로 시작하는 소문자 태그는 그대로)."""
    t = tag.strip().lstrip("#")
    return t if (checks.is_it(t) or re.match(r"(it|sw)", t, re.I)) else "개발자" + t


def _pause(a=6.0, b=12.0):
    time.sleep(random.uniform(a, b))


def _links(page, tag: str, want: int) -> list[str]:
    page.goto(f"https://www.instagram.com/explore/search/keyword/?q={quote('#' + tag)}", wait_until="domcontentloaded")
    _pause(4, 7)
    found: list[str] = []
    for _ in range(4):
        for h in page.eval_on_selector_all('a[href*="/p/"]', "els => els.map(e => e.getAttribute('href'))"):
            m = re.search(r"/p/([\w-]+)/", h or "")
            if m and m.group(1) not in found:
                found.append(m.group(1))
        if len(found) >= want:
            break
        page.mouse.wheel(0, 2500)
        _pause(3, 6)
    return found[:want]


_OWN_IMGS = """els => els.filter(e => !e.closest('a') && e.naturalWidth >= 400
    && !/프로필|profile/i.test(e.alt || '')).map(e => e.currentSrc || e.src)"""


def _post(page, code: str) -> tuple[list[str], str]:
    page.goto(f"https://www.instagram.com/p/{code}/", wait_until="domcontentloaded")
    _pause(4, 7)
    srcs: list[str] = []
    for _ in range(20):          # 캐러셀은 20장까지 — 링크 안 이미지(아래 '더 보기' 썸네일)는 뺀다
        for s in page.eval_on_selector_all("main img", _OWN_IMGS):
            if s and s not in srcs:
                srcs.append(s)
        nxt = page.query_selector('main button[aria-label="다음"], main button[aria-label="Next"]')
        if not nxt:
            break
        nxt.click()
        time.sleep(random.uniform(1.2, 2.5))
    meta = page.evaluate("""() => ({
        d: (document.querySelector('meta[property="og:description"]') || {}).content || '',
        t: (document.querySelector('main time[datetime]') || {getAttribute: () => ''}).getAttribute('datetime') || ''})""")
    m = re.search(r':\s*["“](.*)["”]\s*\.?\s*$', meta["d"], re.S)      # "좋아요 N개 - 계정, 날짜: "캡션"" → 캡션만
    cap = _HANDLE.sub("", m.group(1) if m else "").strip()
    date = (meta["t"] or "")[:10]
    return srcs, (f"게시일 {date}\n" if date else "") + cap


def run(posts: int = 30, tags: list[str] | None = None, dest=None) -> int:
    store.ensure()
    seen = set(store.load_json(SEEN, []))
    tags = tags or random.sample(EXP_TAGS, 2) + random.sample(DOC_TAGS, 1) + random.sample(AGE_TAGS, 1) + random.sample(REVIEW_TAGS, 2) + random.sample(TAGS, 1)
    tags = list(dict.fromkeys(it_tag(t) for t in tags))
    got = 0
    _ensure_chrome()
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        if not any(c["name"] == "sessionid" for c in ctx.cookies("https://www.instagram.com")):
            raise SystemExit("인스타 로그인이 안 돼 있어요 — 전용 크롬 창에서 로그인해 주세요")
        page = ctx.new_page()
        try:
            for tag in tags:
                if got >= posts:
                    break
                codes = [c for c in _links(page, tag, 24) if c not in seen]
                print(f"#{tag}: 새 게시물 {len(codes)}")
                for code in codes:
                    if got >= posts:
                        break
                    seen.add(code)
                    srcs, cap = _post(page, code)
                    if not srcs:
                        continue
                    d = (dest or store.INBOX) / f"{datetime.now():%Y%m%d-%H%M%S}-ig-{code}"
                    d.mkdir(parents=True, exist_ok=True)
                    for i, s in enumerate(srcs[:20]):
                        r = ctx.request.get(s)
                        if r.ok:
                            (d / f"{i:02d}.jpg").write_bytes(r.body())
                    (d / "url.txt").write_text(f"https://www.instagram.com/p/{code}/\n#{tag}\n{cap}", encoding="utf-8")
                    got += 1
                    print(f"  {code}: {len(srcs)}장")
                    store.save_json(SEEN, sorted(seen))
                    _pause()
        finally:
            store.save_json(SEEN, sorted(seen))
            page.close()
    print(f"인스타: 게시물 {got}개 → inbox (다음 회차에 글로 바뀜)")
    return got


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--posts", type=int, default=30)
    ap.add_argument("--tags", default="")
    a = ap.parse_args()
    run(a.posts, [t.strip().lstrip("#") for t in a.tags.split(",") if t.strip()] or None)
