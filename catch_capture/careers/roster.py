"""인스타 '합격자 명단·취업 현황' 게시물 — 캡처해서 학교·전공·합격처로 정리한다.

    python -m careers.roster collect [--posts 20] [--tags 합격자명단,취업현황]   # 인스타에서 캡처(읽기만)
    python -m careers.roster read                                              # 캡처 → 표(GPU)
    python -m careers.roster show                                              # 정리된 숫자 보기

- 학원·부트캠프·학과가 올리는 '○○대 → △△ 합격' 명단 카드를 모은다. IT 쪽만 남긴다.
- 사람 이름은 남기지 않는다: 글자 읽기에서 이름을 ○○ 로 두게 하고, 표에는 이름 칸이 없다. 읽은 글 원문도 저장하지 않는다.
- 캡처 이미지는 var/careers/roster/img/<게시물>/ 에 로컬로만 둔다(페이지에는 안 띄운다).
- 표: var/careers/roster/rows.jsonl — 게시물 하나 = 줄 하나 {post, url, tag, date, poster, list_kind, it, rows:[…]}
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.request
from collections import Counter, defaultdict

from . import store

DIR = store.DIR / "roster"
INBOX = DIR / "inbox"
IMG = DIR / "img"
ROWS = DIR / "rows.jsonl"
IT_TAGS = ["it취업성공", "개발자취업성공", "it취업합격", "개발자최종합격", "개발자합격자", "it합격", "부트캠프취업",
           "부트캠프합격", "국비지원취업", "국비취업성공", "수료생취업", "it취업현황", "컴퓨터공학과취업", "컴공취업",
           "소프트웨어학과", "싸피합격", "우테코합격", "개발자취업", "코딩학원취업", "it국비취업", "sw취업", "개발자신입합격"]
GEN_TAGS = ["개발자합격자명단", "it취업현황", "개발자취업성공", "it취업률", "개발자취업실적", "부트캠프합격실적", "개발자취업합격",
            "개발자최종합격", "개발자합격수기", "it취업합격후기", "늦은나이개발자", "30대개발자취업", "30대개발자", "30대비전공개발자",
            "늦깎이개발자", "나이많은신입개발자", "고졸개발자"]   # 예전 '합격자명단'·'취업현황' 은 입시·체대·공무원이 대부분이었다
TAGS = IT_TAGS + GEN_TAGS     # 회차마다 IT 셋 + 넓은 쪽 하나(이것도 IT 낱말을 단다)

VISION = "qwen2.5vl:7b"
OCR_PROMPT = ("이 이미지는 학원·부트캠프·학과가 올린 합격자 명단이나 취업 현황 게시물이다. "
              "표나 목록이 있으면 한 사람(또는 한 묶음)을 한 줄로 '학교 | 전공 | 나이·학번 | 합격처(회사·기관·과정) | 직무 | 연도 | 인원' 처럼 옮긴다. "
              "모르는 칸은 비운다. 사람 이름은 절대 적지 말고 ○○ 로 둔다. 표가 아니면 이미지의 글자를 그대로 옮긴다. 옮긴 글만 출력한다.")
PROMPT = """다음은 인스타 게시물(합격자 명단·취업 현황 카드)에서 읽은 글이다. JSON 객체 하나로 정리하라.
{{
 "poster": "학원|부트캠프|대학·학과|회사|개인|기타",
 "list_kind": "취업|교육과정선발|진학|자격증|기타",
 "it": true 또는 false — 개발·IT·소프트웨어·데이터·보안 쪽 명단이면 true (의대·편입·공무원 등 IT 아니면 false),
 "year": 명단의 연도(글에 나온 숫자만, 없으면 null),
 "rows": [{{"school": "출신 학교(없으면 null, 고졸·학점은행이면 그대로)", "major": "전공(없으면 null)",
           "major_cs": 전공이 컴퓨터·소프트웨어·전자·정보 계열이면 true, 다른 계열이면 false, 모르면 null,
           "org": "합격한 회사·기관·과정 이름", "org_type": "회사|교육과정|공공기관|대학원|기타",
           "role": "직무(백엔드·프론트엔드·데이터·AI·임베디드·보안·SI·QA 등, 없으면 null)",
           "it": 이 줄의 직무가 개발·IT·SW·데이터·AI·보안·인프라면 true(합격처가 제조사여도 SW 직무면 true), 아니면 false,
           "age": 나이 숫자(글에 나온 것만 — '28세', '95년생'이면 연도로 계산, '30대'면 35) 또는 null,
           "year": 연도 또는 null, "count": 이 줄의 인원(모르면 1)}}]
}}
규칙: 사람 이름은 어떤 칸에도 넣지 않는다. 글에 없는 것은 지어내지 않는다. 합격처가 없는 줄은 뺀다.
학원이 '개설 과정·직무 목록'을 보여 주는 것은 합격 줄이 아니다 — 실제로 누가 어디에 붙었는지만 줄로 적는다.
school 에는 학교 이름만(학과·지역·'비전공' 같은 말은 major 로). org 에는 실제 회사·기관·과정 이름만('데이터', 'IT계열사' 같은 일반어는 빼고 그 줄은 버린다).

글:
{text}"""

_UNI = re.compile(r"(대학교|대학)$")
_CO = re.compile(r"\(주\)|㈜|주식회사|\s+")


_SCHOOL_OK = re.compile(r"(대|대학|대학교|고|고등학교|폴리텍|학점은행|고졸|검정고시|대학원|사이버대)$")
_GENERIC_ORG = re.compile(r"^(데이터|IT|개발|대기업|중견기업|중소기업|스타트업|공기업|외국계|회사|기업|.*계열사|.*IT기업|.*개발자|.*엔지니어|.*디자이너|.*기획자|.*분석가|미정|기타)$", re.I)


def _school(s: str | None) -> str | None:
    s = (s or "").strip()
    if not s or s in ("null", "없음", "-") or re.search(r"[|/○]", s):
        return None
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(캠퍼스|분교)$", "", s)
    s = _UNI.sub("대", s) if not s.endswith("대") else s
    return s if _SCHOOL_OK.search(s) and len(s) <= 15 else None


def _org(s: str | None) -> str | None:
    s = _CO.sub("", (s or "").strip())
    return s if s and not _GENERIC_ORG.match(s) and len(s) <= 30 and not re.search(r"[,/·]", s) else None


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


def _vl(path) -> str:
    body = json.dumps({"model": VISION, "stream": False, "keep_alive": "20s", "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1800},
                       "messages": [{"role": "user", "content": OCR_PROMPT,
                                     "images": [_small(path)]}]}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)["message"]["content"].strip()


def _pages(imgs) -> list[str]:
    out = []
    for i, p in enumerate(imgs, 1):          # 한 장이 안 읽혀도 그 장만 건너뛴다
        try:
            out.append(f"[{i}장]\n{_vl(p)}")
        except Exception:  # noqa: BLE001
            pass
    if imgs and not out:
        raise RuntimeError("한 장도 못 읽었다")
    return out


def collect(posts: int = 20, tags: list[str] | None = None) -> int:
    import random
    from . import instagram
    INBOX.mkdir(parents=True, exist_ok=True)
    return instagram.run(posts=posts, tags=tags or random.sample(IT_TAGS, 3) + random.sample(GEN_TAGS, 1), dest=INBOX)


def read(limit: int = 0) -> int:
    from .extract import _ask
    IMG.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(p for p in INBOX.iterdir() if p.is_dir()) if INBOX.exists() else []:
        if limit and n >= limit:
            break
        imgs = sorted(p for p in f.iterdir() if p.suffix.lower() in (".jpg", ".png", ".jpeg", ".webp"))
        meta = (f / "url.txt").read_text(encoding="utf-8").splitlines() if (f / "url.txt").exists() else []
        url, tag = (meta + ["", ""])[:2]
        cap = "\n".join(meta[2:])
        try:
            text = (cap + "\n\n" if cap else "") + "\n\n".join(_pages(imgs))
            r = json.loads(_ask(PROMPT.format(text=text[:14000]), "local", fmt="json"))
        except Exception as e:  # noqa: BLE001 — 모델이 내려가 있으면 다음 회차에, 두 번 실패하면 버린다
            fails = store.load_json(DIR / "fails.json", {})
            fails[f.name] = fails.get(f.name, 0) + 1
            store.save_json(DIR / "fails.json", fails)
            print(f"  ! {f.name}: {e} ({fails[f.name]}번째)", flush=True)
            if fails[f.name] >= 2:
                f.replace(IMG / f.name)
            continue
        date = next((l[4:].strip() for l in meta if l.startswith("게시일")), "")
        rows = []
        for x in r.get("rows") or []:
            if not isinstance(x, dict) or not _org(x.get("org")):
                continue
            try:
                cnt = max(1, min(200, int(x.get("count") or 1)))
            except (TypeError, ValueError):
                cnt = 1
            rows.append({"school": _school(x.get("school")), "major": (x.get("major") or None),
                         "major_cs": x.get("major_cs") if isinstance(x.get("major_cs"), bool) else None,
                         "org": _org(x.get("org")), "org_type": x.get("org_type") or "기타",
                         "role": x.get("role") if isinstance(x.get("role"), str) else None,
                         "it": x["it"] if isinstance(x.get("it"), bool) else bool(r.get("it")),
                         "age": x["age"] if isinstance(x.get("age"), int) and 17 <= x["age"] <= 60 else None, "year": x.get("year") or r.get("year") or (int(date[:4]) if date[:4].isdigit() else None),
                         "count": cnt})
        rows = [x for x in rows if x["org_type"] != "교육과정" or x["school"] or x["major"] or x["age"]]   # 학원의 개설 과정 목록은 뺀다
        rec = {"post": f.name, "url": url.strip(), "tag": tag.strip().lstrip("#"), "date": date, "poster": r.get("poster"),
               "list_kind": r.get("list_kind"), "it": bool(r.get("it")), "rows": rows}
        with ROWS.open("a", encoding="utf-8") as w:
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if not rows and rec["it"] and not (store.INBOX / f.name).exists():
            import shutil                      # 명단이 아니라 한 사람의 합격 후기 카드 — 경험담 쪽에서 읽게 넘긴다
            shutil.copytree(f, store.INBOX / f.name)
            print(f"  {f.name}: 명단 아님 → 후기로 넘김", flush=True)
        f.replace(IMG / f.name)
        n += 1
        print(f"  {f.name}: IT={rec['it']} {rec['list_kind']} 줄 {len(rows)}", flush=True)
    print(f"명단 읽기 {n}건", flush=True)
    return n


def load() -> list[dict]:
    out = []
    for l in ROWS.read_text(encoding="utf-8").splitlines() if ROWS.exists() else []:
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out


def summary() -> dict:
    """보고서·페이지용 — IT 명단만, 사람 단위(count) 로 센다."""
    def is_it(p, x):                      # 줄마다 — 제조사 명단 안의 SW 직무도 센다
        return x.get("it") if isinstance(x.get("it"), bool) else p.get("it")
    posts = [p for p in load() if p.get("list_kind") != "진학" and any(is_it(p, x) for x in p.get("rows") or [])]
    allrows = [x | {"poster": p.get("poster"), "list_kind": p.get("list_kind")} for p in posts for x in p["rows"]
               if is_it(p, x) and _org(x.get("org"))]
    edu_rows = [x for x in allrows if x.get("org_type") == "교육과정"]   # 부트캠프·교육과정 선발은 따로 — 취업과 섞지 않는다
    rows = [x for x in allrows if x.get("org_type") in ("회사", "공공기관", "대학원")]   # 자격증·'기타'는 합격처로 안 센다
    by_org, by_school = defaultdict(list), defaultdict(list)
    for x in rows:
        by_org[x["org"]].append(x)
        if x.get("school"):
            by_school[x["school"]].append(x)

    def cnt(xs, key, top=8):
        c = Counter()
        for x in xs:
            if x.get(key):
                c[x[key]] += x["count"]
        return c.most_common(top)

    def cs_share(xs):
        known = [x for x in xs if x.get("major_cs") is not None]
        tot = sum(x["count"] for x in known)
        return round(100 * sum(x["count"] for x in known if x["major_cs"]) / tot) if tot else None

    from . import age as _age

    def ages(xs):
        return _age.stats([x["age"] for x in xs if isinstance(x.get("age"), int) for _ in range(x["count"])])

    orgs = sorted(({"org": o, "age": ages(xs), "n": sum(x["count"] for x in xs), "type": Counter(x["org_type"] for x in xs).most_common(1)[0][0],
                    "schools": cnt(xs, "school"), "majors": cnt(xs, "major", 5), "cs_share": cs_share(xs),
                    "roles": cnt(xs, "role", 5), "years": cnt(xs, "year", 5), "posts": len({id(x) for x in xs})}
                   for o, xs in by_org.items()), key=lambda d: -d["n"])
    schools = sorted(({"school": s, "age": ages(xs), "n": sum(x["count"] for x in xs), "orgs": cnt(xs, "org"), "roles": cnt(xs, "role", 5)}
                      for s, xs in by_school.items()), key=lambda d: -d["n"])
    by_prog = defaultdict(list)
    for x in edu_rows:
        by_prog[x["org"]].append(x)
    programs = sorted(({"org": o, "n": sum(x["count"] for x in xs), "schools": cnt(xs, "school"), "majors": cnt(xs, "major", 5),
                        "cs_share": cs_share(xs), "age": ages(xs)} for o, xs in by_prog.items()), key=lambda d: -d["n"])
    allp = load()
    return {"posts_read": len(allp), "posts_it": len(posts), "people": sum(x["count"] for x in rows),
            "with_school": sum(x["count"] for x in rows if x.get("school")), "cs_share": cs_share(rows), "age": ages(rows),
            "orgs": orgs[:150], "schools": schools[:150], "programs": programs[:60],
            "posters": Counter(p.get("poster") or "기타" for p in posts).most_common(),
            "kinds": Counter(p.get("list_kind") or "기타" for p in posts).most_common(),
            "sources": [{"url": p["url"], "tag": p["tag"], "date": p["date"], "poster": p.get("poster"), "n": sum(x["count"] for x in p["rows"])}
                        for p in posts][-200:]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "read", "show"])
    ap.add_argument("--posts", type=int, default=20)
    ap.add_argument("--tags", default="")
    a = ap.parse_args()
    if a.cmd == "collect":
        collect(a.posts, [t.strip().lstrip("#") for t in a.tags.split(",") if t.strip()] or None)
    elif a.cmd == "read":
        read()
    else:
        s = summary()
        print(json.dumps({k: s[k] for k in ("posts_read", "posts_it", "people", "with_school", "cs_share")}, ensure_ascii=False))
        for o in s["orgs"][:20]:
            print(o["n"], o["org"], o["type"], o["schools"][:4], "CS", o["cs_share"])
