"""raw 글 → 경로 한 줄(paths.jsonl). 글 몇 개씩 묶어 `claude -p` 에 표준입력으로 준다.

  python -m careers.extract                  # 아직 안 뽑은 글 전부
  python -m careers.extract --limit 40       # 40개만(시험)
  python -m careers.extract --workers 3 --batch 4 --model haiku

사람이 아니라 경로를 남긴다 — 이름·아이디·연락처·학교명·사진 설명은 뽑지 않고, 학력은 갈래로만
남긴다. 커리어 글이 아니면 is_story=false 로 남겨 다음 회차에 다시 묻지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from careers import checks, store

BODY_CHARS = 7000
APP_SCHEMA = """{                        // 서류: 이력서·포트폴리오·자기소개서를 어떻게 짰나(글에 없으면 null·빈 배열)
   "resume": "이력서 형식·구성(예: 1장 PDF, 노션, 원티드 이력서, 경력기술서 별도) 또는 null",
   "resume_points": ["이력서에서 한 방식(예: 성과를 숫자로, 기술 스택을 프로젝트별로, 1페이지로 줄임)"],
   "portfolio": "포트폴리오 형식(예: 노션, PDF, GitHub README, 개인 사이트, 없음) 또는 null",
   "portfolio_projects": ["담은 프로젝트를 일반화해서(예: 팀 프로젝트 2개, 대용량 트래픽 개인 프로젝트, 운영 중인 서비스)"],
   "portfolio_points": ["포트폴리오에서 강조한 것·짜는 방식(예: 문제-해결-결과 순서, 트러블슈팅 중심, 아키텍처 그림)"],
   "cover_letter_points": ["자기소개서 쓰는 방식·구성(예: 경험을 STAR 로, 회사 서비스 분석, 두괄식)"],
   "cover_letter_questions": ["자소서 문항 주제(예: 지원 동기, 협업 갈등 해결, 가장 어려웠던 기술 문제)"],
   "doc_result": "서류 지원·합격 수 표기(예: 40곳 지원 8곳 서류 합격) 또는 null",
   "resume_length": "이력서·포트폴리오 분량(글에 나온 쪽수·장수) 또는 null",
   "portfolio_detail": [{"project": "프로젝트를 일반화한 이름", "problem": "풀려던 문제", "solution": "한 일·쓴 방법",
                         "result": "결과(숫자가 있으면 숫자째)", "tech": ["그 프로젝트에 쓴 기술"]}],
   "jd_requirements": ["글쓴이가 밝힌 그 공고의 자격요건·우대사항(공고에 적힌 말 그대로에 가깝게)"],
   "jd_matching": [{"requirement": "공고가 요구한 것", "shown_by": "서류·면접에서 그걸 무엇으로 보여줬나"}],
   "tailoring": "공고·회사마다 서류를 어떻게 바꿨나(안 바꿨으면 '안 바꿈') 또는 null",
   "feedback": "서류를 누구에게 봐 달라고 했나(멘토·현직자·스터디·교육과정·없음) 또는 null",
   "revisions": "서류를 몇 번·어떻게 고쳤나 또는 null"
 }"""
SCHEMA = """{
 "id": "<입력의 id 그대로>",
 "is_story": true,                       // 개발 직군의 취업·합격·이직·전환·불합격 경험담인가 (기술 글·광고·남의 이야기 요약이면 false)
 "kind": "합격|불합격|이직|첫취업|직무전환|교육과정|서류준비|회고",
 "year": 2026,                           // 합격·입사·이직이 일어난 해(글 작성일이 아니라 사건의 해, 모르면 null)
 "period": "가장 자세한 시기 표기(예: 2026 상반기 공채, 2025-11, 2026 봄) 또는 null",
 "company": "회사 표시명 또는 null",       // 결과가 난 회사. 여러 곳이면 최종 선택한 곳
 "other_companies": [{"company":"", "result":"합격|불합격|진행중|중도포기", "stage":"서류|코테|과제|1차면접|2차면접|최종|null"}],
 "role": "다음 중 하나만: 백엔드|프론트엔드|풀스택|iOS|안드로이드|데이터엔지니어|데이터분석|ML/AI|DevOps/SRE|보안|게임|임베디드|QA|기타",
 "level": "인턴|신입|경력",
 "years_before": 0,                      // 그 시점 개발 경력(년, 모르면 null)
 "background": {
   "education": "CS전공 4년제|비전공 4년제|전문대|고졸|대학원|재학중|null",
   "major_field": "컴퓨터|공학(비컴퓨터)|자연과학|인문|사회/상경|예체능|기타|null",
   "bootcamp": "부트캠프/교육기관 이름(공개 프로그램명은 남겨도 된다) 또는 null",
   "prior_non_dev_career": "개발 전 직업을 일반명사로(예: 영업, 디자이너, 공무원) 또는 null",
   "age": null                           // 합격·입사 당시 나이 숫자 — 글에 나온 것만('29살', '만 31세', '94년생'+사건 연도로 계산, '30대 초반'이면 32). 없으면 null
 },
 "spec": {                               // 글쓴이가 밝힌 스펙(없으면 null·빈 배열)
   "gpa": "학점 표기 그대로(예: 3.8/4.5) 또는 null",
   "language": ["어학 점수(예: 토익 850, 오픽 IH)"],
   "certs": ["자격증(예: 정보처리기사, SQLD, AWS SAA)"],
   "activities": ["대외활동·동아리·교육과정(공개 프로그램명)"],
   "awards": ["수상·대회(예: 해커톤 대상)"],
   "internships": ["인턴 경험(회사 규모나 이름)"],
   "algorithm": "알고리즘 실력 표기(예: 백준 플래티넘, 프로그래머스 4단계) 또는 null"
 },
 "path": [ {"step":"순서대로 거친 단계를 짧게(예: 비전공 졸업, 부트캠프 6개월, SI 1년, 스타트업 백엔드 2년)", "months": null} ],
 "transition": "예: 비개발→개발, SI→서비스, 스타트업→대기업, 프론트→백엔드, 없음",
 "stack": ["주력 기술"],
 "prep_months": null,
 "prep_methods": ["알고리즘", "CS 공부", "토이 프로젝트", "오픈소스", "블로그", "자격증", "인턴", "스터디" ...],
 "selection": {"coding_test": "있음/없음/유형", "assignment": "있음/없음", "interviews": ["면접 단계 이름"], "notable_questions": ["면접에서 나온 질문 주제(짧게)"]},
 "application": """ + APP_SCHEMA + """,
 "key_factors": ["글쓴이가 합격(또는 탈락)의 이유로 꼽은 것"],
 "advice": ["다음 사람에게 준 조언(짧게)"],
 "market_note": "글쓴이가 묘사한 그때 채용 시장 분위기(예: 채용 한파, 공채 축소, 개발자 붐) 또는 null",
 "summary": "이 경로를 한두 문장으로"
}"""
PROMPT = """너는 개발자 커리어 경험담에서 '경로'만 뽑는 추출기다. 아래 글 각각을 JSON 객체 하나로 바꿔라.

규칙:
- 사람을 알아볼 수 있는 정보는 절대 쓰지 않는다: 이름·닉네임·아이디·이메일·SNS·학교 이름·사는 곳·사진 묘사. 학력은 갈래로만.
- 글에 없는 내용은 지어내지 않는다. 모르면 null 또는 빈 배열.
- 회사 이름을 글에서 알 수 없으면 null("최종 합격한 회사" 같은 말을 넣지 않는다). 회사 이름은 글에 나온 표기를 그대로 쓴다(약칭이면 널리 쓰는 정식 표시명으로: 예 당근 → 당근마켓).
- 교육과정·부트캠프·IT 동아리 선발(YAPP·DND·SOPT·넥스터즈·SSAFY·우아한테크코스·부스트캠프·42서울·소프트웨어 마에스트로 등)은 회사 합격이 아니다:
  kind="교육과정", company=null, background.bootcamp 에 과정 이름. 그 과정을 거쳐 회사에 간 이야기면 company 는 그 회사.
- 값은 한국어로 짧게.

형식(주석은 설명이다, 출력에는 넣지 않는다):
{schema}

출력은 JSON 배열 하나만, 다른 말 없이. 입력 순서대로 객체 {n}개.

입력:
{items}"""


def _clean(body: str) -> str:
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)          # 이미지
    body = re.sub(r"\(https?://[^)]+\)", "", body)             # 링크 주소
    body = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[이메일]", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()[:BODY_CHARS]


OLLAMA = "http://127.0.0.1:11434/api/chat"
LOCAL_MODEL = "qwen3:14b"     # 5070 Ti(16GB)에서 거르기·구조화를 둘 다 한다(모델 하나만 올려 VRAM 교체를 없앤다)

# 로컬 모델이 자주 틀리는 것을 코드로 바로잡는다(Claude 와 같은 글로 견줘 본 결과 — 2026-11)
_CLUBS = re.compile(r"YAPP|DND|SOPT|넥스터즈|Nexters|디프만|SSAFY|싸피|우테코|우아한테크코스|부스트캠프|42\s?서울|소프트웨어\s?마에스트로|소마|멋쟁이사자처럼|멋사|GDSC|코드스테이츠|항해99|이어드림|KDT|국비")
_GENERIC_CO = re.compile(r"^(스타트업|중소기업|대기업|중견기업|회사|IT\s?회사|외국계|최종\s?합격한\s?회사|SI\s?회사|.*기업)$")


def _fix(r: dict, body: str) -> dict:
    co = (r.get("company") or "").strip()
    if co and _GENERIC_CO.match(co):
        r["company"] = None
    if co and _CLUBS.search(co):                     # 동아리·교육과정을 회사로 넣은 경우
        r["kind"], r["company"] = "교육과정", None
        bg = r.setdefault("background", {}) or {}
        bg["bootcamp"] = bg.get("bootcamp") or co
        r["background"] = bg
    y = r.get("year")
    if isinstance(y, int) and str(y) not in body and f"{str(y)[2:]}년" not in body:
        r["year"] = None                             # 글에 그 해가 안 나오면 지어낸 것으로 본다
    p = r.get("period") or ""
    if p and not any(tok in body for tok in re.findall(r"\d{2,4}|상반기|하반기|봄|가을|여름|겨울", p)):
        r["period"] = None
    if "application" in r:
        r["application"] = _fix_app(r["application"])
    checks.check_background(r, body)                 # 학력·전환은 원문에 근거가 있을 때만 — 없으면 '확인되지 않음'
    if r.get("role") and r["role"] not in ROLES:
        r["role"] = "기타"
    return r


ROLES = {"백엔드", "프론트엔드", "풀스택", "iOS", "안드로이드", "데이터엔지니어", "데이터분석", "ML/AI", "DevOps/SRE", "보안",
         "게임", "임베디드", "QA", "기타"}


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            return any(m["name"].startswith(LOCAL_MODEL) for m in json.load(r).get("models", []))
    except Exception:  # noqa: BLE001
        return False


def _ask(prompt: str, model: str, fmt: str | None = None) -> str:
    if model == "local":
        req_body = {"model": LOCAL_MODEL, "stream": False, "think": False, "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 6000},
                    "messages": [{"role": "user", "content": prompt}]}
        if fmt:
            req_body["format"] = fmt
        body = json.dumps(req_body).encode("utf-8")
        req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)["message"]["content"]
    exe = shutil.which("claude")
    p = subprocess.run([exe, "-p", "--output-format", "json", "--model", model], input=prompt, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=600)
    return json.loads(p.stdout.strip().splitlines()[-1])["result"]


def _call(batch: list[dict], model: str) -> list[dict]:
    if model == "local":                     # 로컬은 한 건씩, JSON 모드로(배열은 자주 깨진다)
        res = []
        for b in batch:
            items = f"### id: {b['id']}\n제목: {b['title']}\n본문:\n{_clean(b['body'])}"
            prompt = PROMPT.format(schema=SCHEMA, n=1, items=items).replace("출력은 JSON 배열 하나만", "출력은 JSON 객체 하나만")
            try:
                r = json.loads(_ask(prompt, "local", fmt="json"))
            except (json.JSONDecodeError, ValueError):
                r = {"error": "badjson"}
            r = _fix(r, b["body"]) if not r.get("error") else r
            r.update(id=b["id"], source=b["source"], url=b["url"], title=b["title"], posted=b.get("date") or None, by=LOCAL_MODEL)
            res.append(r)
        return res
    items = "\n\n".join(f"### id: {b['id']}\n제목: {b['title']}\n본문:\n{_clean(b['body'])}" for b in batch)
    prompt = PROMPT.format(schema=SCHEMA, n=len(batch), items=items)
    out = _ask(prompt, model)
    m = re.search(r"\[.*\]", out, re.S)
    rows = json.loads(m.group(0)) if m else []
    by_id = {r.get("id"): r for r in rows if isinstance(r, dict)}
    res = []
    for b in batch:
        r = by_id.get(b["id"]) or {"id": b["id"], "is_story": None, "error": "missing"}
        r.update(id=b["id"], source=b["source"], url=b["url"], title=b["title"], posted=b.get("date") or None)
        res.append(r)
    return res


def recheck() -> dict:
    """이미 뽑은 줄에 원문 규칙을 다시 건다 — 근거 없는 학력·전환은 지우고, IT 낱말이 없는 글은 경험담에서 뺀다.
    지운 값은 *_unverified 에 남기므로 되돌릴 수 있다. 원본은 paths.jsonl.bak 로 둔다."""
    raw = {r["id"]: r for r in store.raw_items() if r.get("id")}
    rows = store.read_paths()
    store.PATHS.with_suffix(".jsonl.bak").write_text(store.PATHS.read_text(encoding="utf-8"), encoding="utf-8")
    n = {"rows": len(rows), "education_cleared": 0, "transition_cleared": 0, "not_it": 0}
    for r in rows:
        b = raw.get(r["id"]) or {}
        text = f"{b.get('title') or r.get('title') or ''}\n{b.get('body') or ''}"
        if not r.get("is_story") or not b:
            continue
        if not checks.is_it_item(r.get("source") or b.get("source"), text):
            r["is_story"], r["screened"] = False, "not_it"
            n["not_it"] += 1
            continue
        ed, tr = (r.get("background") or {}).get("education"), r.get("transition")
        checks.check_background(r, text)
        n["education_cleared"] += bool(ed and not (r.get("background") or {}).get("education"))
        n["transition_cleared"] += bool(tr and not r.get("transition"))
    tmp = store.PATHS.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(store.PATHS)
    print(f"다시 확인: {n}", flush=True)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recheck", action="store_true", help="이미 뽑은 줄에 원문 확인 규칙을 다시 건다")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--model", default="auto", help="auto(로컬 모델이 있으면 local) | local | haiku | sonnet")
    a = ap.parse_args()
    if a.recheck:
        recheck()
        return
    main_args(a.limit, a.batch, a.workers, a.model)


APPS = store.DIR / "application.jsonl"      # 먼저 뽑은 경험담에 서류 항목만 덧붙인 것(id → application)
_DOCS = re.compile(r"포트폴리오|포폴|이력서|자기소개서|자소서|경력기술서|서류|공고|자격\s*요건|우대\s*사항|요구\s*사항|\bJD\b|"
                   r"resume|portfolio|cover letter|job description|requirements", re.I)   # 서류 또는 '그때 공고' 이야기가 있는 글
APP_PROMPT = """아래 개발자 취업·이직 경험담에서 '서류(이력서·포트폴리오·자기소개서)를 어떻게 짰나'만 뽑아 JSON 객체 하나로 내라.
사람을 알아볼 수 있는 정보(이름·아이디·학교·링크)는 쓰지 않는다. 글에 없는 내용은 지어내지 않는다(null·빈 배열). 값은 한국어로 짧게.

형식(주석은 설명이다, 출력에는 넣지 않는다):
{schema}

제목: {title}
본문:
{body}"""


_EXAMPLES: set[str] | None = None


def _fix_app(a) -> dict:
    """형식 설명의 예시 문구를 그대로 베낀 값은 지운다(로컬 모델이 자주 그런다)."""
    global _EXAMPLES
    if _EXAMPLES is None:
        ex = set()
        for grp in re.findall(r"예:\s*([^)]*)\)", APP_SCHEMA):
            ex |= {x.strip() for x in grp.split(",") if x.strip()}
        ex |= {x.strip() for x in re.findall(r'"([^"]{2,})"', APP_SCHEMA)}
        _EXAMPLES = ex
    if not isinstance(a, dict):
        return {}
    out = {}
    for k, v in a.items():
        if isinstance(v, str):
            t = v.strip()
            v = None if (t in _EXAMPLES or "또는 null" in t or t.lower() in ("null", "none", "")) else t
        elif isinstance(v, list):
            keep = []
            for x in v:
                if isinstance(x, str) and x.strip() and x.strip() not in _EXAMPLES:
                    keep.append(x.strip())
                elif isinstance(x, dict):              # portfolio_detail·jd_matching — 설명 문구를 베낀 칸은 비운다
                    d = {kk: (vv if not (isinstance(vv, str) and vv.strip() in _EXAMPLES) else None) for kk, vv in x.items()}
                    if any(vv for vv in d.values() if not isinstance(vv, list)) or any(d.get("tech") or []):
                        keep.append(d)
            v = keep
        out[k] = v
    return out


def read_apps() -> dict:
    if not APPS.exists():
        return {}
    out = {}
    for l in APPS.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            out[r["id"]] = r.get("application")
    return out


def backfill_application(limit: int = 40) -> int:
    """application 없이 뽑힌 경험담 중 본문에 서류 이야기가 있는 글만 서류 항목을 따로 뽑는다(GPU, 한 건씩)."""
    if not _ollama_up():
        return 0
    have = read_apps()
    raw = {r["id"]: r for r in store.raw_items() if r.get("id")}
    cand = [r for r in store.read_paths() if r.get("is_story") and "application" not in r and r["id"] not in have
            and r["id"] in raw and _DOCS.search(raw[r["id"]].get("body") or "")]
    todo = cand[:limit]
    n = 0
    with APPS.open("a", encoding="utf-8") as f:
        for r in todo:
            b = raw[r["id"]]
            try:
                app = json.loads(_ask(APP_PROMPT.format(schema=APP_SCHEMA, title=b["title"], body=_clean(b["body"])), "local", fmt="json"))
            except Exception:  # noqa: BLE001 — 한 건 실패는 건너뛴다(다음 회차에 다시)
                continue
            f.write(json.dumps({"id": r["id"], "application": _fix_app(app)}, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
    print(f"서류 항목 덧붙임 {n}건 · 남은 후보 {len(cand) - n}건", flush=True)
    return n


SCREEN = """아래 글이 '글쓴이 본인'의 개발 직군 취업·합격·불합격·이직·직무 전환·교육과정 선발 경험담인지 판정해라.
본인이 이력서·포트폴리오·자기소개서를 어떻게 썼는지(서류 합격·탈락 경험 포함) 쓴 글도 경험담이다.
기술 설명, 공부 기록(TIL), 행사·강의 홍보, 채용 공고, 남의 이야기 정리면 아니다. 답은 YES 또는 NO 한 단어만.

제목: {title}
본문 앞부분:
{body}"""


def _screen(item: dict) -> bool:
    """로컬 모델(5070 Ti)로 경험담인지만 가른다 — 긴 구조화는 정확한 쪽(Claude)에 맡기고, 거르는 일은 GPU 가 한다."""
    ans = _ask(SCREEN.format(title=item["title"], body=_clean(item["body"])[:1800]), "local")
    return "YES" in ans.upper()


def main_args(limit: int = 0, batch: int = 4, workers: int = 3, model: str = "auto") -> None:
    local = _ollama_up()
    if model == "auto":
        model = "local" if local else "haiku"     # 그래픽카드가 있으면 구조화도 거기서
    print(f"거르기: {LOCAL_MODEL if local else '없음(전부 추출로)'} · 구조화: {model}", flush=True)
    done = {r["id"] for r in store.read_paths()}
    todo = [r for r in store.raw_items() if r.get("id") and r["id"] not in done]
    if limit:
        todo = todo[:limit]
    if local:
        keep = []
        with store.PATHS.open("a", encoding="utf-8") as f:
            for i, it in enumerate(todo, 1):
                if not checks.is_it_item(it.get("source"), f"{it.get('title') or ''}\n{it.get('body') or ''}"):   # IT 낱말이 하나도 없으면 모델에 묻지도 않는다
                    f.write(json.dumps({"id": it["id"], "is_story": False, "screened": "not_it", "source": it["source"],
                                        "url": it["url"], "title": it["title"]}, ensure_ascii=False) + "\n")
                    continue
                try:
                    ok = _screen(it)
                except Exception as e:  # noqa: BLE001 — 로컬 모델이 죽으면 거르지 않고 넘긴다
                    print(f"  ! 거르기 실패 → 추출로 넘김: {e}", flush=True)
                    ok = True
                if ok:
                    keep.append(it)
                else:
                    f.write(json.dumps({"id": it["id"], "is_story": False, "screened": "local", "source": it["source"],
                                        "url": it["url"], "title": it["title"]}, ensure_ascii=False) + "\n")
                if i % 25 == 0:
                    f.flush()
                    print(f"  거르기 {i}/{len(todo)} → 경험담 후보 {len(keep)}", flush=True)
        print(f"거르기 끝: {len(todo)}건 중 {len(keep)}건을 구조화로", flush=True)
        todo = keep
    if model == "local":
        workers, batch = 2, 2      # 5070 Ti 16GB — qwen3:14b 한 벌에 요청 둘(OLLAMA_NUM_PARALLEL)
    batches = [todo[i: i + batch] for i in range(0, len(todo), batch)]
    print(f"추출 대기 {len(todo)}건 → 묶음 {len(batches)}개", flush=True)
    n_story = 0
    with ThreadPoolExecutor(workers) as ex, store.PATHS.open("a", encoding="utf-8") as f:
        futs = {ex.submit(_call, b, model): b for b in batches}
        for i, fu in enumerate(as_completed(futs), 1):
            try:
                rows = fu.result()
            except Exception as e:  # noqa: BLE001 — 한 묶음이 깨져도 나머지는 간다(다음 회차에 다시)
                print(f"  ! 묶음 실패: {e}", flush=True)
                continue
            for r in rows:
                if r.get("error"):
                    continue
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                n_story += bool(r.get("is_story"))
            f.flush()
            print(f"[{i}/{len(batches)}] 누적 경험담 {n_story}", flush=True)


if __name__ == "__main__":
    main()
