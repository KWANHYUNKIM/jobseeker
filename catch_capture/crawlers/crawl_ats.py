"""회사 자체 채용페이지(ATS) 통합 크롤러 → 표준 jobs.json 스키마로 누적 저장.

대기업/스타트업 다수가 채용을 Greenhouse·Lever·Ashby 같은 ATS의 공개 JSON
API로 노출한다. `ats_boards.json` 의 (provider, slug, company) 목록을 받아
각 보드에서 개발직군만 골라 수집한다. 브라우저 불필요(순수 HTTP).

기존 국내 크롤러와 동일한 계약:
  - 인자:   python -m crawlers.crawl_ats <keyword> <target> [per_board]
            keyword 는 폴더명 통일용(영어 공고라 is_developer_job 으로 거른다).
            target = 이번 실행에서 수집할 신규 공고 총량(전 보드 합산).
            per_board = 회사당 이번 실행 신규 상한(기본 6, 다양성 확보용).
  - 출력:   screenshots/ats_<keyword>/  (fixed_out_dir, 누적)
  - dedup:  pid = "<provider>:<slug>:<job_id>"

보드는 매 실행 무작위 순서로 돌아, 사이클마다 다른 회사들이 우선 채워진다.

사용법:
    python -m crawlers.crawl_ats 개발자 100
    python -m crawlers.crawl_ats 개발자 200 10
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import html as _html
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from crawlers import block_detect, kr_portals
from crawlers.jobs_common import (
    USER_AGENT,
    build_jd_sections,
    extract_tech_stack,
    fixed_out_dir,
    html_to_text,
    http_get,
    is_developer_job,
    jitter,
    load_existing_jobs,
    load_seen_pids,
    sanitize_filename,
    save_jobs_json,
    save_listing,
)

SITE = "ats"
CONFIG = Path(__file__).resolve().parent / "ats_boards.json"
# 키워드 무관(회사 보드 전체를 훑음) → 출력 폴더 고정 + 신선도 가드.
PIN_KEYWORD = "개발자"
FRESH_SECS = 1200

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
# SK 그룹 통합 채용(계열사 공고가 다 여기로 모인다 — 계열사 광고 마이크로사이트도 결국
# 여기 공고로 링크한다). robots 가 /Recruit 를 허용한다. 목록 API 는 폼 필드 7개를 빈 값까지
# 전부 보내야 JSON 을 주고(하나라도 빠지면 오류 페이지로 보낸다), 언어는 Accept-Language 로 고른다.
SKCAREERS_LIST = "https://www.skcareers.com/Recruit/GetRecruitList"
SKCAREERS_DETAIL = "https://www.skcareers.com/Recruit/Detail/{nid}"
SKCAREERS_FORM = {"sort": "2", "searchText": "", "corpCode": "", "jobRole": "",
                  "recruitType": "", "workingType": "", "workingRegion": ""}


def _clean(text: str, limit: int = 16000) -> str:
    return (text or "").strip()[:limit]


def _fetch_json(url: str) -> object:
    return json.loads(http_get(url, timeout=30).decode("utf-8", "ignore"))


def _post_form_json(url: str, form: dict[str, str]) -> object:
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(form).encode(),
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9",
                 "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


# ---- provider 별 파서: 공통 후보 dict 리스트로 정규화 --------------------
def _from_greenhouse(slug: str, company: str) -> list[dict]:
    data = _fetch_json(GREENHOUSE.format(slug=slug))
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []))
        content = html_to_text(_html.unescape(j.get("content") or ""))
        out.append({
            "ext_id": str(j.get("id")),
            "title": (j.get("title") or "").strip(),
            "company": company,
            "url": j.get("absolute_url") or "",
            "location": loc or "—",
            "category": depts,
            "full_jd": _clean(content),
        })
    return out


def _from_lever(slug: str, company: str) -> list[dict]:
    data = _fetch_json(LEVER.format(slug=slug))
    out = []
    for j in data:
        cat = j.get("categories") or {}
        desc = j.get("descriptionPlain") or html_to_text(j.get("description") or "")
        extra = j.get("additionalPlain") or ""
        out.append({
            "ext_id": str(j.get("id")),
            "title": (j.get("text") or "").strip(),
            "company": company,
            "url": j.get("hostedUrl") or j.get("applyUrl") or "",
            "location": cat.get("location") or j.get("country") or "—",
            "category": ", ".join(x for x in (cat.get("department"), cat.get("team")) if x),
            "full_jd": _clean((desc + "\n\n" + extra).strip()),
        })
    return out


def _from_ashby(slug: str, company: str) -> list[dict]:
    data = _fetch_json(ASHBY.format(slug=slug))
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        desc = j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or "")
        loc = j.get("location") or ""
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = (loc + " (Remote)").strip()
        out.append({
            "ext_id": str(j.get("id")),
            "title": (j.get("title") or "").strip(),
            "company": company,
            "url": j.get("jobUrl") or j.get("applyUrl") or "",
            "location": loc or "—",
            "category": ", ".join(x for x in (j.get("department"), j.get("team")) if x),
            "full_jd": _clean(desc),
        })
    return out


# SK 는 직무 분류를 직접 붙여 준다 — 제목보다 이게 정확하다. 제목만 보면 "Junior Talent
# 채용(AT/DT)" 의 Talent 가 영어 비개발 단어로 걸려 백엔드 공고가 빠진다.
_SK_DEV_ROLE = re.compile(
    r"Tech R&D/(AI|Data|Software|Solution SW|SW|Client|ML|Backend|Frontend|Web|App|Embedded)"
    r"|Backend|Frontend|Infra/Cloud|IT/(IT 보안|QA|구축)|정보보안", re.IGNORECASE)
_SK_DATE = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")
# 상세 페이지의 섹션 제목(영문 고정) → build_jd_sections 가 아는 머리말
_SK_SECTIONS = {"About the job": "주요업무", "Who We're Looking For": "자격요건",
                "Preferred Qualifications": "우대사항"}
_SK_ITEM_RE = re.compile(
    r'<h2 class="detail-content-title">(.*?)</h2>\s*<div class="detail-content-box">(.*?)'
    r'(?=<div class="detail-content-item">|<div class="floating-box">)', re.S)


def _sk_is_dev(title: str, role: str) -> bool:
    if _SK_DEV_ROLE.search(role):
        return True
    return "사업개발" not in role and is_developer_job(title)


def _sk_detail(nid: str) -> tuple[str, dict[str, str]]:
    raw = http_get(SKCAREERS_DETAIL.format(nid=nid), timeout=30).decode("utf-8", "ignore")
    structured: dict[str, str] = {}
    parts: list[str] = []
    for head, body in _SK_ITEM_RE.findall(raw):
        head = _html.unescape(re.sub(r"<[^>]+>", "", head)).strip()
        text = re.sub(r"\s*\n\s*", "\n", html_to_text(_html.unescape(body))).strip()
        if not text:
            continue
        parts.append(f"[{head}]\n{text}")
        if head in _SK_SECTIONS:
            structured[_SK_SECTIONS[head]] = text
    return _clean("\n\n".join(parts)), structured


def _from_skcareers(slug: str, company: str) -> list[dict]:
    data = _post_form_json(SKCAREERS_LIST, SKCAREERS_FORM)
    if not isinstance(data, dict) or not data.get("success"):
        raise RuntimeError("skcareers 목록 응답 이상")
    out = []
    for j in data.get("list") or []:
        nid = str(j.get("noticeID") or "")
        title = (j.get("title") or "").strip()
        role = j.get("jobRole") or ""
        m = _SK_DATE.search(j.get("end") or "")
        out.append({
            "ext_id": nid,
            "title": title,
            "company": (j.get("corpName") or company).strip(),
            "url": SKCAREERS_DETAIL.format(nid=nid),
            "location": j.get("workingArea") or "—",
            "category": role,
            "full_jd": "",
            "dev": _sk_is_dev(title, role),
            "detail": (lambda nid=nid: _sk_detail(nid)),
            # job_status 가 읽는 표기("~ MM/DD")로 둔다. 연도는 가장 가까운 해로 골라진다.
            "deadline": f"~ {int(m.group(2)):02d}/{int(m.group(3)):02d}" if m else "",
            "career": j.get("recruitType") or "",
        })
    return out


PARSERS = {"greenhouse": _from_greenhouse, "lever": _from_lever, "ashby": _from_ashby,
           "skcareers": _from_skcareers, **kr_portals.PARSERS}


def _load_boards() -> list[dict]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    boards = cfg.get("boards", [])
    return [b for b in boards if b.get("provider") in PARSERS and b.get("slug")]


def crawl(keyword: str, target: int, per_board: int, *, site: str = SITE,
          boards: list[dict] | None = None, parsers: dict | None = None) -> None:
    """보드 목록을 돌며 개발직만 누적한다. crawl_boards(국내 채용 보드·공공)도 이 루프를
    site·boards·parsers 만 바꿔 쓴다."""
    parsers = parsers or PARSERS
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = fixed_out_dir(base_dir, site, PIN_KEYWORD)  # 키워드 무관, 고정 폴더
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)

    jobs_json = out_dir / "jobs.json"
    if jobs_json.exists() and (time.time() - jobs_json.stat().st_mtime) < FRESH_SECS:
        age = int(time.time() - jobs_json.stat().st_mtime)
        print(f"[*] 최근 {age}s 전 갱신됨(<{FRESH_SECS}s) — 이번 호출 스킵", flush=True)
        return

    collected: list[dict] = load_existing_jobs(out_dir)
    base_count = len(collected)
    seen = load_seen_pids(base_dir, site)
    for j in collected:
        if j.get("pid"):
            seen.add(str(j["pid"]).strip())

    boards = boards if boards is not None else _load_boards()
    # 국내(kr) 보드는 수가 적어 무작위 순서면 상한에 밀려 누락될 수 있다.
    # 항상 kr 보드를 먼저 돌고, 해외(global)만 무작위 순서로 섞는다.
    kr = [b for b in boards if b.get("region") == "kr"]
    others = [b for b in boards if b.get("region") != "kr"]
    random.shuffle(others)
    boards = kr + others
    print(f"[*] 보드 {len(boards)}개 / 기존 수집 {base_count}건 / 이전 PID {len(seen)}개", flush=True)
    print(f"[*] 목표 신규 {target}건 (회사당 상한 {per_board})", flush=True)

    scanned = skipped_dup = skipped_nondev = failed_boards = 0
    # 보드 API 는 그 회사의 공고를 **전부** 준다. 그래서 받아 온 보드는 "여기 없으면
    # 내려간 것" 이라고 말할 수 있다 — 검색 앞 몇 쪽만 보는 다른 사이트와 다른 점이다.
    # 신규 목표를 채워 중간에 멈추면 뒤쪽 보드는 이번 회차에 안 본 것이라 빠진다.
    listed: list[str] = []
    complete_boards: list[str] = []
    # 국내 보드가 70곳을 넘어 밀린 공고만으로 회차 목표를 다 쓰면 해외 보드가 굶는다 —
    # 국내 몫을 목표의 70% 로 묶는다(국내만 도는 crawl_boards 는 region 이 다 kr 라 상관없다).
    kr_quota = target if all(x.get("region") == "kr" for x in boards) else int(target * 0.7)
    kr_new = 0
    for bi, b in enumerate(boards, 1):
        if len(collected) - base_count >= target:
            break
        if b.get("region") == "kr" and kr_new >= kr_quota:
            continue
        provider, slug, company = b["provider"], b["slug"], b["company"]
        try:
            candidates = parsers[provider](slug, company)
        except Exception as exc:
            reason, code = block_detect.from_http_error(exc)
            note = reason or type(exc).__name__
            print(f"  [{bi}/{len(boards)}] {company:22s} ({provider}:{slug}) 실패: {note}", flush=True)
            failed_boards += 1
            continue
        # 0건은 "공고가 다 내려갔다"보다 "응답이 이상했다"일 가능성이 크다 — 완전한
        # 목록으로 치지 않는다(치면 그 회사 공고가 한꺼번에 사라짐 처리된다).
        listed.extend(f"{provider}:{slug}:{c['ext_id']}" for c in candidates if c.get("ext_id"))
        # 앞 몇 쪽만 보는 보드(complete: false)는 안 보였다고 내려간 게 아니다.
        if candidates and b.get("complete", True):
            complete_boards.append(f"{provider}:{slug}")

        board_new = 0
        # 그룹 포털(skcareers 등)은 보드 하나에 계열사 수십 곳이 모여 있어 회사당 상한이 따로다.
        board_cap = int(b.get("per_board") or per_board)
        for c in candidates:
            if (len(collected) - base_count >= target or board_new >= board_cap
                    or (b.get("region") == "kr" and kr_new >= kr_quota)):
                break
            scanned += 1
            pid = f"{provider}:{slug}:{c['ext_id']}"
            if not c["ext_id"] or pid in seen:
                skipped_dup += 1
                continue
            is_dev = c["dev"] if "dev" in c else is_developer_job(c["title"], c.get("category"))
            if not is_dev:
                skipped_nondev += 1
                continue

            full_jd, structured = c["full_jd"], None
            if c.get("detail"):
                # 목록에 본문이 없는 곳은 개발직으로 골라진 것만 상세를 받는다.
                # 실패하면 seen 에 안 넣어 다음 회차에 다시 받는다.
                # 상세가 세 번째 값으로 목록에 없던 칸(마감일 등)을 돌려줄 수 있다.
                try:
                    full_jd, structured, *more = c["detail"]()
                    if more:
                        c.update(more[0])
                except Exception as exc:                            # noqa: BLE001
                    print(f"    상세 실패 {pid}: {type(exc).__name__}", flush=True)
                    continue
                time.sleep(jitter(800) / 1000)
            cname = c.get("company") or company
            tech = extract_tech_stack(f"{c['title']}\n{c.get('category','')}\n{full_jd}")
            jd_parts = build_jd_sections(structured, full_jd)

            idx = len(collected) + 1
            label = f"{cname}_{c['title']}".strip("_")
            base_name = f"{idx:02d}_{sanitize_filename(label)}"
            lines = [
                f"회사: {cname}",
                f"제목: {c['title']}",
                f"URL: {c['url']}",
                f"출처: {provider}:{slug} ({b.get('label', '자체 채용페이지')})",
                "",
                "[조건]",
                f"위치: {c['location']}",
                "",
                "[직무 카테고리]",
                c.get("category") or "(없음)",
                "",
                "[기술스택]",
                ", ".join(tech) if tech else "(JD에서 식별된 기술스택 없음)",
                "",
                "[채용 상세]",
                full_jd or "(상세 내용을 가져오지 못함)",
            ]
            (out_dir / f"{base_name}.txt").write_text("\n".join(lines), encoding="utf-8")
            collected.append({
                "idx": idx,
                "pid": pid,
                "position_id": pid,
                "source_board": f"{provider}:{slug}",
                "company": cname,
                "title": c["title"],
                "url": c["url"],
                "category": c.get("category", ""),
                "location": c["location"],
                "reward": "",
                "skills": [],
                "tech_stack": tech,
                "main_tasks": jd_parts.get("main_tasks", ""),
                "qualifications": jd_parts.get("qualifications", ""),
                "preferences": jd_parts.get("preferences", ""),
                "tech_stack_raw": jd_parts.get("tech_stack_raw", ""),
                "benefits": jd_parts.get("benefits", ""),
                "full_jd": full_jd,
                "txt": f"{base_name}.txt",
                "company_page": b.get("company_page", True),
                "region": b.get("region", ""),
                **{k: c[k] for k in ("deadline", "career") if c.get(k)},
            })
            seen.add(pid)
            board_new += 1
            if b.get("region") == "kr":
                kr_new += 1
        if board_new:
            save_jobs_json(out_dir, collected)
            print(f"  [{bi}/{len(boards)}] {company:22s} ({provider}:{slug}) +{board_new} "
                  f"→ 누적 {len(collected)}", flush=True)
        time.sleep(jitter(600) / 1000)

    save_jobs_json(out_dir, collected)
    save_listing(out_dir, listed, complete_scopes=complete_boards)
    if failed_boards < len(boards):
        block_detect.note_success(site)
    print(
        f"\n[완료] 수집 {len(collected)} (신규 {len(collected) - base_count}) / "
        f"중복 {skipped_dup} / 비개발 {skipped_nondev} / 훑음 {scanned} / 실패보드 {failed_boards}",
        flush=True,
    )
    print(f"[결과 위치] {out_dir}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 100
    per_board = int(args[2]) if len(args) > 2 else 6
    crawl(keyword, target, per_board)


if __name__ == "__main__":
    main()
