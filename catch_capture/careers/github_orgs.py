"""회사의 공개 GitHub 조직 → 쓰는 언어·주제·대표 저장소·활동량. 회사 단위만 본다(직원 개인 계정은 보지 않는다).

  python -m careers.github_orgs                # 아직 없거나 30일 지난 조직부터, 회차당 --limit 개
  python -m careers.github_orgs --limit 40
  python -m careers.github_orgs --only 토스,네이버

GitHub REST API(공개 데이터). 토큰 없이 시간당 60회라 회차당 몇 곳씩만 돈다 — `GITHUB_TOKEN`
(공개 읽기 권한만 있는 fine-grained 토큰)을 주면 시간당 5000회로 전부 돈다.

회사 → 조직 연결은 두 길이다: ① SEED(알려진 조직 login + 회사 도메인 단서) ② 영문 이름이 있는 회사는
조직 검색. 어느 쪽이든 조직 프로필의 blog/이름이 회사 단서와 맞을 때만 verified 로 쓴다 —
같은 이름의 남의 조직을 회사로 착각하지 않게.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

from careers import store
from core.normalize import company as norm

OUT = store.DIR / "github_orgs.json"
API = "https://api.github.com"
REFRESH_DAYS = 30
# 회사 표시명 → (조직 login 후보, 회사 도메인·이름 단서). 단서가 조직 blog/name 에 있어야 verified.
SEED = {
    "토스": (["toss"], ["toss"]), "비바리퍼블리카": (["toss"], ["toss"]), "네이버": (["naver", "navercorp"], ["naver"]),
    "카카오": (["kakao"], ["kakao"]), "카카오페이": (["kakaopay"], ["kakaopay"]), "카카오뱅크": (["kakaobank"], ["kakaobank"]),
    "카카오엔터프라이즈": (["kakaoenterprise"], ["kakao"]), "카카오모빌리티": (["kakaomobility"], ["kakaomobility"]),
    "라인": (["line"], ["line"]), "LINE": (["line"], ["line"]), "당근마켓": (["daangn"], ["daangn", "karrot"]),
    "당근": (["daangn"], ["daangn", "karrot"]), "우아한형제들": (["woowabros", "woowahan"], ["woowa", "baemin"]),
    "엔씨소프트": (["ncsoft"], ["ncsoft"]), "NHN": (["nhn"], ["nhn"]), "데브시스터즈": (["devsisters"], ["devsisters"]),
    "하이퍼커넥트": (["hyperconnect"], ["hyperconnect", "hpcnt"]), "센드버드": (["sendbird"], ["sendbird"]),
    "리디": (["ridi"], ["ridi"]), "뱅크샐러드": (["banksalad"], ["banksalad"]), "버즈빌": (["buzzvil"], ["buzzvil"]),
    "마이리얼트립": (["myrealtrip"], ["myrealtrip"]), "뤼이드": (["riiid"], ["riiid"]), "업스테이지": (["UpstageAI"], ["upstage"]),
    "쏘카": (["socar-inc"], ["socar"]), "컬리": (["thefarmersfront"], ["kurly"]), "쿠팡": (["coupang"], ["coupang"]),
    "넷마블": (["netmarble"], ["netmarble"]), "넥슨": (["nexon"], ["nexon"]), "크래프톤": (["krafton-ai", "KRAFTON"], ["krafton"]),
    "클래스101": (["class101"], ["class101"]), "왓챠": (["watcha-inc", "frograms"], ["watcha"]), "야놀자": (["yanolja"], ["yanolja"]),
    "직방": (["zigbang"], ["zigbang"]), "무신사": (["musinsa"], ["musinsa"]), "29CM": (["29cm"], ["29cm"]),
    "삼성전자": (["Samsung"], ["samsung"]), "SK텔레콤": (["sktelecom", "SKTBrain"], ["sk"]), "KT": (["kt-ai", "KT-AI"], ["kt"]),
    "LG전자": (["LGE", "lge"], ["lg"]), "몰로코": (["moloco"], ["moloco"]), "스캐터랩": (["scatterlab"], ["scatterlab"]),
    "토스뱅크": (["toss"], ["toss"]), "토스증권": (["toss"], ["toss"]), "오늘의집": (["bucketplace"], ["bucketplace", "ohou"]),
    "버킷플레이스": (["bucketplace"], ["bucketplace", "ohou"]), "에이블리": (["ably-dev", "ablycorp"], ["a-bly", "ably"]),
    "번개장터": (["bunjang"], ["bunjang"]), "여기어때": (["gccompany", "goodchoice"], ["gccompany", "goodchoice", "yeogi"]),
}


SEED_EXTRA = store.DIR / "github_seed.json"   # 루프가 더하는 연결: {"회사 표시명": [["login", ...], ["단서", ...]]}


def seeds() -> dict:
    return {**SEED, **{k: tuple(v) for k, v in store.load_json(SEED_EXTRA, {}).items()}}


def _token() -> None:
    """환경변수가 없으면 var/careers/github_token.txt 에서 읽는다(루프를 다시 띄우지 않아도 붙게)."""
    f = store.DIR / "github_token.txt"
    if not os.environ.get("GITHUB_TOKEN") and f.exists():
        os.environ["GITHUB_TOKEN"] = f.read_text(encoding="utf-8").strip()


def _get(path: str, params: dict | None = None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "jobseeker-careers"}
    _token()
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            left = int(r.headers.get("X-RateLimit-Remaining", "1"))
            return json.load(r), left
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise RuntimeError("rate-limit") from e
        return None, 1


def _matches(org: dict, hints: list[str]) -> bool:
    hay = " ".join(str(org.get(k) or "") for k in ("blog", "name", "login", "description", "email")).lower()
    return any(h.lower() in hay for h in hints)


def _latin(name: str) -> str | None:
    s = re.sub(r"\(.*?\)|주식회사|㈜", "", name).strip()
    return s if re.fullmatch(r"[A-Za-z0-9 .&-]{2,40}", s) else None


def resolve(name: str) -> tuple[dict | None, list[str]]:
    """회사 → 확인된 조직 프로필. 못 찾으면 (None, 시도한 login)."""
    tried = []
    logins, hints = seeds().get(name, ([], []))
    if not logins and (lat := _latin(name)):
        hits, _ = _get("/search/users", {"q": f"{lat} type:org", "per_page": 3})
        logins = [h["login"] for h in (hits or {}).get("items", [])]
        hints = [lat.lower().replace(" ", ""), lat.lower().split()[0]]
        time.sleep(6)                                       # 검색 API 는 분당 10회
    for lg in logins:
        tried.append(lg)
        org, _ = _get(f"/orgs/{lg}")
        if org and _matches(org, hints):
            return org, tried
    return None, tried


MEMBERS_MAX = 40          # 조직 공개 멤버 중 표본 — 멤버 하나에 호출 한 번
_KINDS = [("알고리즘·코테", r"baekjoon|boj|leetcode|programmers|algorithm|coding-?test|알고리즘|코테"),
          ("공부·TIL", r"\btil\b|study|스터디|learn|tutorial|강의|book"),
          ("블로그·포트폴리오", r"github\.io|blog|portfolio|resume|이력서"),
          ("설정·도구", r"dotfiles|config|vim|zsh|cli|tool|script"),
          ("라이브러리·오픈소스", r"lib|sdk|plugin|framework|-js$|-py$|package")]


def members(org: str) -> dict | None:
    """조직에 공개로 등록된 멤버들이 개인 저장소에서 하는 일 — **회사 단위 숫자로만** 남긴다.
    누가 누구인지(로그인·이름·저장소 이름)는 저장하지 않는다. 토큰이 없으면 표본을 12명으로 줄인다(시간당 60회)."""
    _token()
    cap = MEMBERS_MAX if os.environ.get("GITHUB_TOKEN") else 12
    ms, _ = _get(f"/orgs/{org}/public_members", {"per_page": 100})
    ms = ms or []
    year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    lang, topics, kinds = Counter(), Counter(), Counter()
    active = sampled = repos_n = 0
    for m in random.sample(ms, min(cap, len(ms))):      # 앞쪽(가나다순)만 보지 않게 고루 뽑는다
        rs, _ = _get(f"/users/{m['login']}/repos", {"per_page": 50, "sort": "pushed", "type": "owner"})
        own = [r for r in (rs or []) if not r.get("fork")]
        sampled += 1
        repos_n += len(own)
        if any(r.get("pushed_at") and datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) > year_ago for r in own):
            active += 1
        for l in {r["language"] for r in own if r.get("language")}:
            lang[l] += 1                                   # 그 언어를 쓰는 멤버 수
        for t in {t for r in own for t in (r.get("topics") or [])}:
            topics[t] += 1
        for k in {next((k for k, rx in _KINDS if re.search(rx, (r["name"] + " " + (r.get("description") or "")), re.I)), "개인 프로젝트")
                  for r in own}:
            kinds[k] += 1
    return {"public_members": len(ms), "sampled": sampled, "active_12m": active,
            "avg_repos": round(repos_n / sampled, 1) if sampled else 0,
            "languages": [[k, v] for k, v in lang.most_common(10)],
            "topics": [[k, v] for k, v in topics.most_common(15)],
            "kinds": [[k, v] for k, v in kinds.most_common()]}


def profile(org: dict) -> dict:
    repos = []
    for page in (1, 2, 3):
        got, _ = _get(f"/orgs/{org['login']}/repos", {"per_page": 100, "page": page, "sort": "pushed", "type": "public"})
        repos += got or []
        if not got or len(got) < 100:
            break
    own = [r for r in repos if not r.get("fork") and not r.get("archived")]
    year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    active = [r for r in own if r.get("pushed_at") and datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) > year_ago]
    lang = Counter()
    for r in own:
        if r.get("language"):
            lang[r["language"]] += 1 + min(r.get("stargazers_count", 0), 2000) ** 0.5
    topics = Counter(t for r in own for t in (r.get("topics") or []))
    top = sorted(own, key=lambda r: -r.get("stargazers_count", 0))[:10]
    return {
        "login": org["login"], "name": org.get("name"), "blog": org.get("blog"), "url": org.get("html_url"),
        "public_repos": len(own), "active_12m": len(active),
        "languages": [[k, round(v)] for k, v in lang.most_common(10)],
        "topics": [[k, v] for k, v in topics.most_common(15)],
        "top_repos": [{"name": r["name"], "desc": (r.get("description") or "")[:160], "lang": r.get("language"),
                       "stars": r.get("stargazers_count", 0), "pushed": (r.get("pushed_at") or "")[:10],
                       "topics": (r.get("topics") or [])[:6], "url": r.get("html_url")} for r in top],
        "recent": [{"name": r["name"], "desc": (r.get("description") or "")[:120], "lang": r.get("language"),
                    "pushed": (r.get("pushed_at") or "")[:10]} for r in active[:8]],
        "members": members(org["login"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    run(a.limit, a.only)


def run(limit: int = 15, only: str = "") -> None:
    class a:  # noqa: N801 — 인자 묶음
        pass
    a.limit, a.only = limit, only
    data = store.load_json(OUT, {})
    now = datetime.now(timezone.utc)
    sd = seeds()
    names = [n for n in a.only.split(",") if n] or [*sd, *store.companies()]
    seen, todo = set(), []
    for n in names:
        k = norm(n)
        if k in seen:
            continue
        seen.add(k)
        cur = data.get(k)
        if cur and datetime.fromisoformat(cur["checked_at"]) > now - timedelta(days=REFRESH_DAYS) and not a.only \
                and not (cur.get("verified") and "members" not in cur):   # 멤버 집계 전인 곳은 다시 본다
            continue
        if cur is None and n not in sd and not _latin(n) and not a.only:
            continue                                         # 한글 이름뿐인 회사는 SEED 에 넣어야 찾는다
        todo.append(n)
    print(f"GitHub 조직: 대상 {len(todo)}곳 중 {min(len(todo), a.limit)}곳", flush=True)
    done = 0
    for n in todo[: a.limit]:
        try:
            org, tried = resolve(n)
            rec = {"company": n, "checked_at": now.isoformat(timespec="seconds"), "tried": tried}
            if org:
                rec.update(verified=True, **profile(org))
            else:
                rec.update(verified=False)
            data[norm(n)] = rec
            done += 1
            print(f"  {n}: {'✓ ' + org['login'] if org else '— 없음'}", flush=True)
        except RuntimeError:
            print("  호출 한도에 걸려 이번 회차는 여기까지(GITHUB_TOKEN 을 주면 풀린다)", flush=True)
            break
        store.save_json(OUT, data)
    print(f"조직 기록 {sum(1 for v in data.values() if v.get('verified'))}곳 확인 / 전체 {len(data)}", flush=True)


if __name__ == "__main__":
    main()
