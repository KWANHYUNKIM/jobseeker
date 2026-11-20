"""후기 수집 — velog 검색(robots 전면 허용, 공개 GraphQL) + inbox(사람이 넣은 글).

  python -m careers.collect                 # 일반 검색어 + 공고 있는 회사 전부
  python -m careers.collect --generic-only  # 일반 검색어만
  python -m careers.collect --companies 토스,카카오
  python -m careers.collect --inbox         # inbox 폴더만 읽어 raw 로 옮긴다

검색 결과에서 제목이 커리어 글로 보이는 것만 본문을 받는다(_RELEVANT). 회사 검색어는
'회사명 합격 / 입사 / 이직' 셋이다. 본 글은 seen.json 에 남겨 다음 회차에 다시 받지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "crawlers"))
from jobs_common import USER_AGENT  # noqa: E402

from careers import store  # noqa: E402

VELOG = "https://v2.velog.io/graphql"
PAGE = 50
GENERIC = [
    "합격 후기", "최종 합격", "합격 회고", "취업 회고", "취업 후기", "신입 개발자 취업", "개발자 취업 성공",
    "이직 후기", "이직 회고", "개발자 이직", "경력 이직", "커리어 전환", "비전공자 개발자 취업", "비전공 합격",
    "부트캠프 취업", "국비 취업", "SI 탈출", "공채 합격", "인턴 합격", "전환형 인턴", "코딩테스트 합격 후기",
    "기술면접 후기", "면접 후기 개발", "오퍼 수락", "입사 회고", "첫 직장 개발자", "신입 공채 회고",
    "백엔드 합격", "프론트엔드 합격", "데이터 엔지니어 합격", "iOS 합격", "안드로이드 합격", "DevOps 합격",
    # 해외 회사 — 한국 개발자가 해외로 간 경로
    "해외 취업 개발자", "해외 개발자 이직", "미국 개발자 취업", "일본 개발자 취업", "캐나다 개발자 취업", "독일 개발자 취업",
    "싱가포르 개발자", "호주 개발자 취업", "유럽 개발자 이직", "구글 합격", "구글 오퍼", "아마존 오퍼", "아마존 합격",
    "메타 오퍼", "마이크로소프트 합격", "애플 합격", "엔비디아 합격", "넷플릭스 합격", "빅테크 오퍼", "FAANG",
    "외국계 합격", "외국계 이직",
    # 시기 — 최근 채용일수록 쓸모가 크다
    "2026 합격", "2026 상반기 공채", "2026 하반기 공채", "2026 이직", "2026 신입 개발자", "2025 하반기 공채", "2025 합격 후기",
    "2025 이직 후기", "2026 인턴 합격", "26년 상반기 합격", "25년 하반기 합격", "해외 원격 근무 개발자", "비자 스폰서 개발자",
    # 경력직 — 연차·이직 과정·처우·면접 형식
    "경력직 합격", "경력직 이직 후기", "경력 공채", "경력 면접 후기", "이직 면접 후기", "이직 성공 회고", "이직 준비 회고",
    "2년차 이직", "3년차 이직", "4년차 이직", "5년차 이직", "7년차 이직", "10년차 개발자", "N년차 회고", "연차 회고 개발자",
    "주니어 이직", "미들 개발자 이직", "시니어 개발자 이직", "시니어 합격", "테크리드 이직", "팀장 이직", "리드 개발자",
    "중고신입", "주니어 탈출", "처우 협의", "연봉 협상 이직", "이직 오퍼 비교", "레퍼런스 체크", "컬처핏 면접",
    "경력 기술면접", "시스템 디자인 면접", "과제 전형 경력", "라이브 코딩 면접", "헤드헌터 이직", "이직 실패",
    "스타트업에서 대기업", "대기업에서 스타트업", "SI에서 서비스 회사", "에이전시 탈출", "금융권 개발자 이직",
    "2026 경력 이직", "2025 경력 이직", "26년 이직 회고", "25년 이직 회고", "퇴사 후 이직", "이직 후 3개월",
    # 서류 — 이력서·포트폴리오·자기소개서를 어떻게 짰나
    "개발자 포트폴리오 작성", "포트폴리오 합격", "포트폴리오 피드백", "노션 포트폴리오", "깃허브 README 포트폴리오",
    "개발자 이력서 작성", "이력서 피드백 개발자", "이력서 회고", "서류 합격 이력서", "서류 합격률", "서류 탈락 이유",
    "경력기술서 작성", "경력 이력서", "자기소개서 개발자", "자소서 합격", "자소서 문항 개발자", "공채 자소서 후기", "서류 합격 후기", "최종 합격 후기", "신입 개발자 합격 후기", "백엔드 합격 후기", "프론트엔드 합격 후기", "인턴 합격 후기", "부트캠프 후기", "부트캠프 수료 후기", "국비지원 후기", "국비 취업 후기", "SSAFY 후기", "우테코 후기", "항해99 후기", "과제 전형 후기", "라이브 코딩 후기", "컬처핏 면접 후기", "임원 면접 후기", "인적성 후기", "채용 연계 후기", "비전공 취업 후기", "30대 취업 후기", "늦은 나이 개발자 취업", "2024 합격 후기", "2023 합격 후기", "2026 합격 후기", "불합격 후기", "탈락 후기 개발", "연봉 협상 후기", "오퍼 후기", "해외 취업 후기 개발자",
    "이력서 수정 서류 합격", "원티드 이력서", "영문 이력서 개발자", "resume 개발자 해외",
    # IT 일반 — 2026-11-18 에 velog 로 재 보고 안 본 글이 남은 것만('IT 합격 후기'·'개발자 이직 후기' 등은 이미 다 봤다)
    "IT 회사 입사", "IT 기업 합격", "IT 신입 합격", "개발자 면접 후기", "데이터 분석가 합격", "SW 합격", "QA 합격",
]
DEVTO = "https://dev.to/api/articles"
DEVTO_TAGS = ["career", "interview", "jobsearch", "careeradvice", "hiring", "codenewbie", "beginners"]
_RELEVANT_EN = re.compile(r"\b(hired|offer|landed|got (a|my|the) (first )?(job|role|offer)|joined|new job|first job|"
                          r"career (change|switch|transition)|switch(ed)? to|bootcamp|self[- ]taught|rejected|rejection|"
                          r"interview(ed|ing)? (at|with|process)|job (hunt|search)|laid off|layoff|"
                          r"(google|meta|amazon|microsoft|apple|netflix|stripe|shopify|faang|maang)|journey to|became a|"
                          r"senior (engineer|developer)|staff engineer|tech lead|promot(ed|ion)|years? (as|of) (a )?(software|dev))\b", re.I)
PER_COMPANY = ["합격", "입사", "이직", "경력"]
_RELEVANT = re.compile(r"합격|입사|이직|취업|회고|공채|오퍼|최종|전환|면접|퇴사|커리어|신입|인턴|합류|붙었|"
                       r"년차|경력|처우|연봉|시니어|리드|팀장|주니어")
SEARCH_Q = "query($k:String!,$o:Int,$l:Int){searchPosts(keyword:$k,offset:$o,limit:$l){count posts{id title url_slug released_at user{username}}}}"
POST_Q = "query($u:String!,$s:String!){post(username:$u,url_slug:$s){id title body released_at tags}}"


def gql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(VELOG, data=body, headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("data") or {}
        except Exception as e:  # noqa: BLE001 — 네트워크 오류는 잠깐 쉬고 다시
            if attempt == 2:
                print(f"  ! velog 실패 {variables}: {e}", flush=True)
                return {}
            time.sleep(3 * (attempt + 1))
    return {}


def search(keyword: str, max_pages: int) -> list[dict]:
    out = []
    for page in range(max_pages):
        d = gql(SEARCH_Q, {"k": keyword, "o": page * PAGE, "l": PAGE}).get("searchPosts") or {}
        posts = d.get("posts") or []
        out += posts
        time.sleep(0.8)
        if len(posts) < PAGE:
            break
    return out


def fetch(post: dict, keyword: str, seen: dict) -> bool:
    if post["id"] in seen:
        return False
    title = post.get("title") or ""
    if not _RELEVANT.search(title):
        seen[post["id"]] = "skip:title"
        return False
    user = (post.get("user") or {}).get("username")
    d = gql(POST_Q, {"u": user, "s": post["url_slug"]}).get("post") or {}
    time.sleep(0.8)
    if not d.get("body"):
        seen[post["id"]] = "skip:nobody"
        return False
    url = f"https://velog.io/@{user}/{post['url_slug']}"
    item = {"id": store.rid("velog", post["id"]), "source": "velog", "url": url, "title": title,
            "date": (d.get("released_at") or "")[:10], "tags": d.get("tags") or [], "query": keyword,
            "body": d["body"][:30000], "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    store.save_json(store.RAW / f"{item['id']}.json", item)
    seen[post["id"]] = item["id"]
    return True


def run_velog(keywords: list[tuple[str, int]]) -> None:
    seen = store.load_json(store.SEEN, {})
    new = 0
    for n, (kw, pages) in enumerate(keywords, 1):
        posts = search(kw, pages)
        got = sum(fetch(p, kw, seen) for p in posts)
        new += got
        print(f"[{n}/{len(keywords)}] {kw}: 검색 {len(posts)} → 새 글 {got} (누적 {new})", flush=True)
        if n % 10 == 0:
            store.save_json(store.SEEN, seen)
    store.save_json(store.SEEN, seen)
    print(f"velog 끝 — 새 글 {new}, raw 총 {len(list(store.RAW.glob('*.json')))}", flush=True)


def run_devto(pages: int = 5) -> None:
    """dev.to 공개 API(robots 허용, 문서화된 API) — 해외 개발자 취업·이직·전환 글."""
    seen = store.load_json(store.SEEN, {})
    new = 0
    for tag in DEVTO_TAGS:
        for page in range(1, pages + 1):
            try:
                with urllib.request.urlopen(urllib.request.Request(f"{DEVTO}?tag={tag}&per_page=100&page={page}",
                                            headers={"User-Agent": USER_AGENT}), timeout=30) as r:
                    arts = json.load(r)
            except Exception as e:  # noqa: BLE001
                print(f"  ! dev.to {tag} p{page}: {e}", flush=True)
                break
            time.sleep(1)
            for a in arts:
                key = f"devto:{a['id']}"
                if key in seen:
                    continue
                if not _RELEVANT_EN.search(a.get("title") or ""):
                    seen[key] = "skip:title"
                    continue
                try:
                    with urllib.request.urlopen(urllib.request.Request(f"{DEVTO}/{a['id']}", headers={"User-Agent": USER_AGENT}), timeout=30) as r:
                        d = json.load(r)
                except Exception:  # noqa: BLE001
                    continue
                time.sleep(1)
                item = {"id": store.rid("devto", str(a["id"])), "source": "devto", "url": a.get("url"), "title": a.get("title"),
                        "date": (a.get("published_at") or "")[:10], "tags": a.get("tag_list") or [], "query": f"tag:{tag}",
                        "body": (d.get("body_markdown") or "")[:30000],
                        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                store.save_json(store.RAW / f"{item['id']}.json", item)
                seen[key] = item["id"]
                new += 1
            if len(arts) < 100:
                break
        print(f"  dev.to #{tag}: 누적 새 글 {new}", flush=True)
        store.save_json(store.SEEN, seen)
    print(f"dev.to 끝 — 새 글 {new}", flush=True)


VISION_MODEL = "qwen2.5vl:7b"   # 5070 Ti 에서 캡처 글자를 읽는다
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
OCR_PROMPT = ("이 이미지는 SNS 에 올라온 개발자 합격·이직·스펙 게시물 캡처다. 이미지 안의 글자를 빠짐없이 그대로 옮겨 적어라. "
              "표나 카드는 '항목: 값' 줄로 적는다. 사람 이름·아이디·얼굴 묘사는 적지 않는다. 옮긴 글만 출력한다.")


def _small(path, side: int = 1280) -> str:
    """큰 캡처(2160×2700 등)는 줄여 보낸다 — 글자는 그대로 읽히고 메모리·시간이 준다."""
    import base64
    import io
    try:
        from PIL import Image
        im = Image.open(path)
        if max(im.size) > side:
            im.thumbnail((side, side))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001
        pass
    return base64.b64encode(path.read_bytes()).decode()


def ocr(path: Path) -> str:
    import base64
    body = json.dumps({"model": VISION_MODEL, "stream": False, "keep_alive": "20s", "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1800},
                       "messages": [{"role": "user", "content": OCR_PROMPT,
                                     "images": [_small(path)]}]}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)["message"]["content"].strip()


def _capture_post(images: list[Path], url: str, note: str, name: str) -> dict:
    """캡처 몇 장 = 게시물 하나. 장마다 글자를 읽어 이어 붙인다."""
    parts, errs = [], []
    for i, p in enumerate(images, 1):          # 한 장이 안 읽혀도(같은 말 되풀이로 끊기는 등) 그 장만 건너뛴다
        try:
            parts.append(f"[{i}장]\n{ocr(p)}")
        except Exception as e:  # noqa: BLE001
            errs.append(e)
    if not parts:
        raise errs[0]
    body = (note + "\n\n" if note else "") + "\n\n".join(parts)
    src = "instagram" if "instagram.com" in url else "facebook" if "facebook.com" in url else "capture"
    return {"id": store.rid(src, url or name + str(len(body))), "source": src, "url": url, "title": name,
            "date": "", "tags": [], "query": "capture", "body": body[:30000], "images": [p.name for p in images],
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def run_inbox() -> None:
    """inbox → raw.
      *.txt|*.md      첫 줄이 http 면 원문 URL, 나머지는 본문
      *.png|*.jpg     캡처 한 장 = 게시물 하나(글자를 읽어 본문으로)
      폴더/           캡처 여러 장 = 게시물 하나. 폴더 안 url.txt(첫 줄 URL, 나머지 메모)가 있으면 쓴다
    처리한 것은 inbox/done/ 으로 옮긴다.
    """
    done = store.INBOX / "done"
    done.mkdir(exist_ok=True)
    n = 0
    for f in sorted(p for p in store.INBOX.iterdir() if p.name != "done"):
        try:
            if f.is_dir():
                imgs = sorted(p for p in f.iterdir() if p.suffix.lower() in IMG_EXT)
                meta = (f / "url.txt").read_text(encoding="utf-8").strip().splitlines() if (f / "url.txt").exists() else []
                url = meta[0].strip() if meta and meta[0].startswith("http") else ""
                note = "\n".join(meta[1:] if url else meta)
                if not imgs:
                    continue
                item = _capture_post(imgs, url, note, f.name)
            elif f.suffix.lower() in IMG_EXT:
                item = _capture_post([f], "", "", f.stem)
            else:
                continue
        except Exception as e:  # noqa: BLE001 — 비전 모델이 없거나 죽으면 다음 회차에 다시
            print(f"  ! 캡처 읽기 실패 {f.name}: {e}", flush=True)
            continue
        store.save_json(store.RAW / f"{item['id']}.json", item)
        f.replace(done / f.name)
        n += 1
    for f in sorted([*store.INBOX.glob("*.txt"), *store.INBOX.glob("*.md")]):
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        lines = text.splitlines()
        url = lines[0].strip() if lines and lines[0].startswith("http") else ""
        body = "\n".join(lines[1:] if url else lines)
        src = "instagram" if "instagram.com" in url else "facebook" if "facebook.com" in url else "inbox"
        item = {"id": store.rid(src, url or body[:500]), "source": src, "url": url, "title": f.stem,
                "date": "", "tags": [], "query": "inbox", "body": body[:30000],
                "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        store.save_json(store.RAW / f"{item['id']}.json", item)
        f.replace(done / f.name)
        n += 1
    print(f"inbox → raw {n}건", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generic-only", action="store_true")
    ap.add_argument("--companies", default="")
    ap.add_argument("--inbox", action="store_true")
    ap.add_argument("--generic-pages", type=int, default=20)
    a = ap.parse_args()
    store.ensure()
    run_inbox()
    if a.inbox:
        return
    kws: list[tuple[str, int]] = []
    if not a.companies:
        kws += [(k, a.generic_pages) for k in GENERIC]
    if not a.generic_only:
        cos = [c for c in a.companies.split(",") if c] or store.companies()
        kws += [(f"{c} {s}", 2) for c in cos for s in PER_COMPANY]
    run_velog(kws)


if __name__ == "__main__":
    main()
