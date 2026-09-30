"""시리즈 게시물 — [데이터로 본 채용] · [들어가려면] 을 판 여러 장으로 찍어 승인함(inbox)에 넣는다.

공고 묶음·회사 해부는 poster/collection.py 가 만든다(approve-collection). 여기는 공고 판이 아니라
**우리 데이터에서 센 숫자**와 **취업 브리핑(guide-engine)** 으로 만드는 카드다. 틀은
templates/series.html 하나이고 시리즈마다 색만 다르다(CONTENT_PLAN.md 의 시리즈 표).

지켜야 하는 것
  - 숫자는 센 것만. 판마다 기준일과 n 을 적는다(note).
  - 가이드의 '공고 원문' 은 브리핑이 공고에서 옮겨 온 quote 그대로다. 해설은 브리핑의 글이다.
  - 모집이 끝난 공고로 가이드를 만들지 않는다 — 색인에서 모집중인 같은 회사·같은 제목이 있어야 한다.

  python -m poster.series stack          # [데이터로 본 채용] 모집중 공고가 가장 많이 찾는 기술
  python -m poster.series rates          # [데이터로 본 채용] 외주 월 단가, 등급별
  python -m poster.series guide 쿠팡     # [들어가려면] 그 회사 공고 하나에서 뽑은 공부할 것
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import shutil
import socket
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

from . import jobsource
from .collection import _not_dev, _deadline

LAB_DIR = Path(__file__).resolve().parent.parent
ROOT = LAB_DIR.parent
TEMPLATE = Path(__file__).resolve().parent / "templates" / "series.html"
OUT = LAB_DIR / "out" / "series"
INBOX = LAB_DIR / "inbox"
GUIDE = ROOT / "jd-viewer" / "public" / "guide"

#: 시리즈마다 색 하나. 틀·서체·쪽 번호 자리는 같다 — 3칸 그리드에서 색이 번갈아도 한 계정으로 읽힌다.
THEMES = {
    "insight": {"paper": "#f5f2ea", "ink": "#111317", "sub": "#5d6068", "accent": "#ff5a1f", "line": "#d8d3c7"},
    "guide": {"paper": "#102a43", "ink": "#f4f1e8", "sub": "#9fb3c8", "accent": "#ffc53d", "line": "#2a4a6b"},
    "term": {"paper": "#fff7e8", "ink": "#1d1a14", "sub": "#6d6456", "accent": "#e8590c", "line": "#eadcc4"},
    "interview": {"paper": "#16161d", "ink": "#f2f2f5", "sub": "#9a9aa8", "accent": "#7c9cff", "line": "#2c2c38"},
    "qa": {"paper": "#eef4ff", "ink": "#0f1b33", "sub": "#55627a", "accent": "#1f6feb", "line": "#cfdcf3"},
    "jd": {"paper": "#f3efe6", "ink": "#1b1a17", "sub": "#6b6557", "accent": "#2b8a3e", "line": "#ddd5c4"},
    "same": {"paper": "#ffffff", "ink": "#16161a", "sub": "#6a6a75", "accent": "#d6336c", "line": "#ececf0"},
    "roadmap": {"paper": "#eaf7f0", "ink": "#0c2a24", "sub": "#4f6b64", "accent": "#0b7285", "line": "#c9e8da"},
    "weekly": {"paper": "#111317", "ink": "#f5f5f0", "sub": "#9a9ca3", "accent": "#ffd43b", "line": "#2a2d33"},
    "signal": {"paper": "#f8f0fa", "ink": "#2a1233", "sub": "#6f5a77", "accent": "#862e9c", "line": "#e8d5ee"},
    "talent": {"paper": "#0e1a2b", "ink": "#f3f5f8", "sub": "#9aa6b8", "accent": "#5cc8ff", "line": "#22324a"},
}
SERIES = {"insight": "[데이터로 본 채용]", "guide": "[들어가려면]", "term": "[IT 용어]",
          "interview": "[면접 예상 질문]", "qa": "[고민 상담소]", "jd": "[JD 번역기]",
          "same": "[같은 직무 다른 회사]", "roadmap": "[공부 로드맵]", "weekly": "[주간 리포트]", "signal": "[채용 시그널]", "talent": "[인재상 해부]"}
TAGS = {"insight": ["개발자채용", "채용트렌드", "개발자취업", "IT채용", "데이터"],
        "guide": ["개발자취업", "취업준비", "개발자채용", "이직준비", "기업분석"],
        "term": ["IT용어", "개발자면접", "백엔드개발자", "Kafka", "개발공부"],
        "interview": ["면접질문", "개발자면접", "올리브영", "백엔드개발자", "이직준비"],
        "qa": ["신입개발자", "개발자취업", "취업고민", "개발자채용", "취업준비"],
        "jd": ["채용공고", "자격요건", "개발자취업", "백엔드개발자", "이직준비"],
        "same": ["백엔드개발자", "채용공고", "개발자채용", "이직준비", "기업분석"],
        "roadmap": ["백엔드로드맵", "개발공부", "백엔드개발자", "신입개발자", "개발자취업"],
        "weekly": ["주간리포트", "개발자채용", "채용트렌드", "IT채용", "개발자취업"],
        "signal": ["채용시그널", "기업분석", "개발자채용", "이직준비", "채용트렌드"],
        "talent": ["인재상", "기업분석", "개발자채용", "이직준비", "면접준비"]}


# --- 재료 ---------------------------------------------------------------
def _stack(j: dict) -> list[str]:
    s = j.get("stack") or []
    if isinstance(s, str):
        try:
            s = ast.literal_eval(s)
        except (ValueError, SyntaxError):
            s = []
    return [x for x in s if isinstance(x, str) and x.strip()]


def _active_dev() -> tuple[list[dict], str]:
    idx = jobsource.load_index()
    today = date.today()
    rows = [j for j in idx["jobs"] if j.get("status") == "active" and not _not_dev(j)
            and not ((d := _deadline(j, today)) and d < today)]
    mt = idx.get("source_mtime") or ""
    try:
        asof = datetime.fromtimestamp(float(mt)).date().isoformat() if mt else today.isoformat()
    except (TypeError, ValueError):
        asof = str(mt)[:10] or today.isoformat()
    return rows, asof


def _dot(iso: str) -> str:
    return iso.replace("-", ". ")


def _plain(s: str) -> str:
    return re.sub(r"`", "", s or "").strip()


def _first(s: str, limit: int = 150) -> str:
    """브리핑 문단에서 앞 문장들 — limit 자를 넘기지 않는 데까지. 문장 중간에서 자르지 않는다."""
    parts = re.split(r"(?<=[.다])\s+", (s or "").replace("\n", " "))
    out = ""
    for p in parts:
        if len(re.sub(r"\*\*", "", out + " " + p)) > limit and out:
            break
        out = (out + " " + p).strip()
    return out


# --- 시리즈 -------------------------------------------------------------
def build_stack() -> dict:
    rows, asof = _active_dev()
    n = len(rows)
    cnt = collections.Counter(s for j in rows for s in set(_stack(j)))
    top = cnt.most_common(10)
    note = f"모집중 개발 공고 {n:,}건 · {_dot(asof)} 수집 기준 · 공고 하나가 기술을 여럿 적으면 각각 센다"
    # 짝꿍 — 상위 셋 각각에 대해, 그 기술을 적은 공고 중 다른 기술을 같이 적은 비율
    pairs = []
    for s, c in top[:4]:
        co = collections.Counter(t for j in rows if s in _stack(j) for t in set(_stack(j)) if t != s)
        t, k = co.most_common(1)[0]
        pairs.append([s, t, {"v": f"{round(100 * k / c)}%", "s": f"{k}/{c}"}])
    newgrad = sum(1 for j in rows if "신입" in (j.get("career") or ""))
    first, fc = top[0]
    slides = [
        {"type": "cover", "big": f"{round(100 * fc / n)}", "big_unit": "%",
         "lines": ["지금 개발 공고", f"열에 {round(10 * fc / n)}개는 {first}"],
         "sub": f"모집중 {n:,}건에서 센 기술 순위", "note": note},
        {"type": "bars", "title": "가장 많이 찾는 기술 10", "sub": "공고에 이 기술을 적은 수",
         "rows": [{"label": s, "value": c, "display": f"{c:,}", "unit": f"{round(100 * c / n)}%", "hi": i == 0}
                  for i, (s, c) in enumerate(top)], "note": note},
        {"type": "table", "title": "같이 적는 기술", "sub": "왼쪽 기술을 적은 공고 중 오른쪽도 적은 비율",
         "head": ["기술", "같이 나오는 것", "비율"], "rows": pairs, "hi_col": 2, "note": note},
        {"type": "stat", "title": "신입도 넣을 수 있는 공고", "num": f"{round(100 * newgrad / n)}", "unit": "%",
         "label": f"{n:,}건 중 {newgrad:,}건이 경력 조건에 '신입' 을 적었다",
         "explain": "나머지는 경력만 받거나 조건을 적지 않았다. 신입이면 **'신입' 이 적힌 공고부터** 보는 게 빠르다.",
         "note": note},
        {"type": "end", "title": "공부 순서를 정할 때", "lines": [
            f"**{first}** 는 공고 {round(100 * fc / n)}%가 적는다",
            f"{pairs[0][0]} 를 적은 공고의 {pairs[0][2]['v']}가 **{pairs[0][1]}** 도 적는다",
            "저장해 두고 이력서 기술 칸을 채울 때 다시 보세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"지금 올라와 있는 개발 공고 {n:,}건, 가장 많이 찾는 기술은 {first}({round(100 * fc / n)}%)",
        "\n".join(f"{i:02d}. {s} — {c:,}건" for i, (s, c) in enumerate(top, 1)),
        f"같이 적는 기술: " + " · ".join(f"{a}→{b} {v['v']}" for a, b, v in pairs),
        f"신입 가능 공고는 {round(100 * newgrad / n)}%({newgrad:,}건).",
        f"{_dot(asof)} 수집한 모집중 개발 공고 기준. 공고 하나가 여러 기술을 적으면 각각 셌습니다.",
    ])
    return {"kind": "insight", "id": f"insight-stack-{asof.replace('-', '')}", "title": "모집중 공고의 기술 순위",
            "slides": slides, "caption": caption, "jobs": []}


def build_rates() -> dict:
    f = json.loads((ROOT / "jd-viewer" / "public" / "freelance.json").read_text(encoding="utf-8"))
    a = f["analysis"]
    g = a["grades"]
    asof = (f.get("generated_at") or "")[:10] or date.today().isoformat()
    total = len(f.get("projects") or f.get("items") or [])
    counted = sum(v["n"] for v in g.values())
    note = (f"외주·프리랜서 프로젝트 {total:,}건 중 월 단가·등급이 확인된 {counted}건 · {_dot(asof)} 기준 · "
            "올라올 때 적힌 단가(만원/월)")
    order = ["초급", "중급", "고급", "특급"]
    by_type = {t["key"]: t for t in a["by_type"]}
    si, sm = by_type.get("SI", {}).get("grades", {}).get("고급"), by_type.get("SM", {}).get("grades", {}).get("고급")
    roles = [r for r in a["by_role"] if r["total"]["n"] >= 10]
    roles.sort(key=lambda r: -r["total"]["median"])
    slides = [
        {"type": "cover", "big": f"{g['고급']['median']}", "big_unit": "만원",
         "lines": ["고급 개발자", "외주 월 단가"], "sub": "중앙값 · 등급별로 이렇게 갈린다", "note": note},
        {"type": "table", "title": "등급별 월 단가", "sub": "가운데 = 중앙값, 범위 = 가운데 절반(25~75%)",
         "head": ["등급", "가운데", "범위", "건수"],
         "rows": [[k, {"v": f"{g[k]['median']}", "s": "만원"}, f"{g[k]['p25']}–{g[k]['p75']}", f"{g[k]['n']}"]
                  for k in order if k in g], "hi_col": 1, "note": note},
    ]
    if si and sm:
        slides.append({"type": "table", "title": "같은 고급이라도", "sub": "SI(구축)와 SM(운영)의 월 단가",
                       "head": ["유형", "가운데", "범위", "건수"],
                       "rows": [["SI 구축", {"v": f"{si['median']}", "s": "만원"}, f"{si['p25']}–{si['p75']}", f"{si['n']}"],
                                ["SM 운영", {"v": f"{sm['median']}", "s": "만원"}, f"{sm['p25']}–{sm['p75']}", f"{sm['n']}"]],
                       "hi_col": 1, "note": note})
    if roles:
        slides.append({"type": "bars", "title": "직무별 월 단가", "sub": "등급을 섞은 중앙값 · 10건 이상인 직무만",
                       "rows": [{"label": r["key"], "value": r["total"]["median"], "display": f"{r['total']['median']}",
                                 "unit": f"n{r['total']['n']}", "hi": i == 0} for i, r in enumerate(roles[:7])],
                       "note": note})
    lines = [f"초급 {g['초급']['median']} → 중급 {g['중급']['median']} → 고급 {g['고급']['median']} → 특급 {g['특급']['median']}"]
    if si and sm:
        lines.append(f"고급은 **SI 가 SM 보다 {si['median'] - sm['median']}만원** 높다")
    lines.append("건수가 적은 칸(초급·특급)은 참고만 하세요")
    slides.append({"type": "end", "title": "단가를 부를 때", "lines": lines, "note": note})
    caption = "\n\n".join([
        f"외주 개발 월 단가, 등급별로 얼마일까 — 고급 중앙값 {g['고급']['median']}만원",
        "\n".join(f"{k}: 중앙값 {g[k]['median']}만원 (가운데 절반 {g[k]['p25']}–{g[k]['p75']}, {g[k]['n']}건)"
                  for k in order if k in g),
        (f"같은 고급이라도 SI(구축) {si['median']}만원, SM(운영) {sm['median']}만원." if si and sm else ""),
        f"{_dot(asof)} 기준, 외주 프로젝트 {total:,}건 중 단가·등급이 확인된 {counted}건으로 셌습니다. 올라올 때 적힌 단가입니다.",
    ])
    return {"kind": "insight", "id": f"insight-rates-{asof.replace('-', '')}", "title": "외주 월 단가 등급별",
            "slides": slides, "caption": caption.replace("\n\n\n\n", "\n\n"), "jobs": []}


def _guide_company(name: str) -> dict:
    idx = json.loads((GUIDE / "index.json").read_text(encoding="utf-8"))["companies"]
    key = re.sub(r"\s+", "", name).lower()
    hit = next(c for c in idx if key in {re.sub(r"\s+", "", n).lower() for n in [c["name"], c["slug"], *c.get("aliases", [])]})
    return json.loads((GUIDE / "companies" / f"{hit['slug']}.json").read_text(encoding="utf-8"))


def build_guide(name: str, *, exclude: set[str] | None = None) -> dict:
    g = _guide_company(name)
    rows, asof = _active_dev()
    norm = lambda s: re.sub(r"\W+", "", (s or "").lower())                # noqa: E731
    names = {norm(n) for n in [g["name"], *g.get("aliases", [])]}
    live = {norm(j.get("title")): j for j in rows if norm(j.get("company")) in names
            or any(n and n in norm(j.get("company")) for n in names)}
    exclude = exclude or set()
    # 모집중인 공고 중 공부할 것이 가장 많은 것 — 원문 인용이 있는 항목만 센다
    cands = []
    for p in g.get("postings") or []:
        j = live.get(norm(p.get("title")))
        if p.get("closed") or not j or j["key"] in exclude:
            continue
        study = [s for s in p.get("study") or [] if s.get("quote") and s.get("gap_check")]
        if len(study) >= 4:
            cands.append((sum(s.get("priority") == "core" for s in study), len(study), p, j, study))
    if not cands:
        raise LookupError(f"{name}: 모집중이고 공부할 것이 4개 이상인 공고가 없다")
    cands.sort(key=lambda c: (-c[0], -c[1]))
    _, _, p, j, study = cands[0]
    study.sort(key=lambda s: 0 if s.get("priority") == "core" else 1)
    study = study[:5]
    short = g["name"]
    role = j.get("title") or p["title"]
    note = f"{short} · {role[:40]} · {_dot(asof)} 모집중 공고 · 해설은 이 계정의 공고 분석"
    slides = [{"type": "cover", "lines": [f"{short}", "들어가려면"],
               "sub": f"**{role}** 공고에서 뽑은 공부할 것 {len(study)}가지", "note": note}]
    verdict = _first(_plain(p.get("verdict", "")), 170)
    if verdict:
        slides.append({"type": "end", "title": "이 자리는", "lines": [verdict] +
                       [_plain(m) for m in (p.get("fit") or {}).get("must_have", [])[:3]], "note": note})
    for i, s in enumerate(study, 1):
        slides.append({"type": "gi", "no": f"{i:02d} / {len(study):02d}", "topic": _plain(s["topic"]),
                       "quote": _plain(s["quote"])[:220], "why": _first(_plain(s.get("why", "")), 150),
                       "check": _plain(s["gap_check"])[:160], "note": note})
    slides.append({"type": "end", "title": "저장해 두고", "lines": [
        "면접 전날 **스스로 점검** 질문만 다시 읽어 보세요",
        "공고 전문은 프로필 링크에서", f"{short} 공고는 [회사 해부] 시리즈에도 있습니다"], "note": note})
    caption = "\n\n".join([
        f"[들어가려면] {short} — {role}",
        f"공고 원문에서 뽑은 공부할 것 {len(study)}가지:",
        "\n".join(f"{i:02d}. {re.sub(r'[*`]', '', s['topic'])}" for i, s in enumerate(study, 1)),
        "각 장의 '스스로 점검' 질문에 답할 수 있으면 준비가 된 것. 저장해 두고 면접 전에 다시 보세요.",
    ])
    caption = enrich(caption, g["name"], before="각 장의")
    return {"kind": "guide", "id": f"guide-{g['slug']}-{date.today().isoformat().replace('-', '')}",
            "title": f"{short} 들어가려면", "slides": slides, "caption": caption,
            "jobs": [{"key": j["key"], "company": j["company"], "role": role}]}


# --- [IT 용어] · [면접 예상 질문] · [고민 상담소] -----------------------------
# 형식은 인프런·코드잇 계정의 시리즈에서 빌렸다(코드잇 'IT 용어'·'직무 인터뷰'·'고민 상담소').
ARTICLE = "올리브영 테크블로그 「45분 배치에서 준실시간으로!」(2026.04.22)"
SEND = "취준 중인 친구에게 보내 주세요"          # 마지막 장은 받을 사람을 지정한다(DM 공유가 가장 큰 도달 신호)


def build_term_idempotency() -> dict:
    """멱등성 — 올리브영 원문이 중복 메시지를 견딘 방법을 예시로. 뜻·비유는 일반 지식, 사례는 원문."""
    note = f"예시: {ARTICLE} · 뜻과 비유는 일반적인 설명"
    slides = [
        {"type": "cover", "lines": ["멱등성", "**한 번 해도, 두 번 해도**"],
         "sub": "같은 결과 — 면접 단골 용어를 1분 만에", "note": note},
        {"type": "end", "title": "뜻", "lines": [
            "같은 요청을 **여러 번** 보내도 결과가 **한 번** 보낸 것과 같은 성질",
            "엘리베이터 버튼은 열 번 눌러도 한 번 부른 것과 같다 → 멱등",
            "'결제하기' 를 두 번 눌러 두 번 빠져나가면 → 멱등이 아니다"], "note": note},
        {"type": "end", "title": "왜 필요한가", "lines": [
            "메시지는 **두 번 올 수 있다**",
            "컨슈머가 죽었다 살아날 때, 리밸런싱될 때, 타임아웃으로 다시 보낼 때",
            "'딱 한 번만 온다' 고 믿고 짜면 데이터가 틀어진다"], "note": note},
        {"type": "end", "title": "올리브영은 이렇게", "lines": [
            "① 메시지를 묶어 가져와 **중복을 지운다**",
            "② **최신 발행 시각** 기준으로 걸러 오래된 게 최신을 덮지 않게",
            "③ **UPSERT** 로 저장 — 중복이 남아 있어도 결과는 같다"], "note": note},
        {"type": "end", "title": "면접에서 물으면", "lines": [
            "Q. Kafka 컨슈머가 같은 메시지를 두 번 받으면?",
            "① 중복이 생기는 이유(재시도·리밸런싱)를 먼저",
            "② 막는 장치(중복 제거·시각 비교·UPSERT)를 **순서대로**"], "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            "비슷한 용어: 정합성 · 순서 보장 · 재시도",
            "3D 해설은 [회사 해부] 올리브영 릴스에서", SEND], "note": note},
    ]
    caption = "\n\n".join([
        "[IT 용어] 멱등성 — 한 번 해도, 두 번 해도 같은 결과",
        "같은 요청을 여러 번 보내도 결과가 한 번 보낸 것과 같은 성질. 메시지 시스템에서는 같은 메시지가 "
        "두 번 올 수 있어서(재시도·리밸런싱) 꼭 필요합니다.",
        "올리브영은 중복 제거 → 최신 발행 시각으로 거르기 → UPSERT 로 이 문제를 풀었습니다.",
        "📌 출처: 사례는 올리브영 테크블로그 「45분 배치에서 준실시간으로! 다수 도메인 데이터를 Kafka로 "
        "통합한 전환기」(2026.04.22) oliveyoung.tech/2026-04-22/display-benefits-migration/ · 뜻과 비유는 일반적인 설명입니다.",
    ])
    return {"kind": "term", "id": f"term-idempotency-{date.today().isoformat().replace('-', '')}",
            "title": "멱등성", "slides": slides, "caption": caption, "jobs": []}


def build_interview(name: str, title_part: str) -> dict:
    """한 회사의 공고 하나 — 취업 브리핑이 공고에서 읽어 낸 예상 질문(interview.expect)을 묶는다.
    답은 쓰지 않는다(지어내지 않는다). 그 자리가 무엇을 하는지(verdict)를 앞에 둔다."""
    g = _guide_company(name)
    p = next(p for p in g["postings"] if title_part in p["title"] and not p.get("closed"))
    qs = [_plain(q).replace("**", "") for q in (p.get("interview") or {}).get("expect", [])][:8]
    short = g["name"]
    note = f"{short} · {p['title'][:40]} · 공고 본문에서 읽어 낸 예상 — 실제 면접과 다를 수 있다"
    slides = [{"type": "cover", "lines": [short, "면접 예상 질문"],
               "sub": f"**{p['title']}** 공고에서 읽어 낸 {len(qs)}개", "note": note},
              {"type": "end", "title": "이 자리는", "lines": [_first(_plain(p.get("verdict", "")), 150)] +
               [_plain(m) for m in (p.get("fit") or {}).get("must_have", [])[:2]], "note": note}]
    for k in range(0, len(qs), 4):
        slides.append({"type": "jobs", "title": f"질문 {k + 1}–{min(k + 4, len(qs))}",
                       "rows": [{"role": q[:70], "meta": ""} for q in qs[k:k + 4]], "note": note})
    slides.append({"type": "end", "title": "준비하는 법", "lines": [
        "질문마다 **내 경험 하나**를 붙여 1분 안에 말해 보기",
        "숫자로 끝내기 — 무엇이 몇 % 줄었나",
        "회사 테크블로그를 읽고 가면 질문의 맥락이 보인다", SEND], "note": note})
    caption = "\n\n".join([
        f"[면접 예상 질문] {short} — {p['title']}",
        "\n".join(f"Q{i}. {q}" for i, q in enumerate(qs, 1)),
        "질문은 공고 본문(자격요건·우대사항·담당업무)에서 읽어 낸 예상이며, 실제 면접과 다를 수 있습니다.",
    ])
    caption = enrich(caption, short, before="질문은 공고")
    return {"kind": "interview", "id": f"interview-{g['slug']}-{date.today().isoformat().replace('-', '')}",
            "title": f"{short} 면접 예상 질문", "slides": slides, "caption": caption, "jobs": []}


def build_qa_newgrad() -> dict:
    """고민: '신입인데 경력 공고에 넣어도 되나요?' — 판단하지 않고, 모집중 공고가 요구하는 경력을 센다."""
    rows, asof = _active_dev()
    n = len(rows)

    def band(c: str) -> str:
        c = c or ""
        if "신입" in c:
            return "신입 가능"
        m = re.search(r"(\d+)", c)
        if not m:
            return "적지 않음"
        y = int(m.group(1))
        return "1–2년" if y <= 2 else "3–4년" if y <= 4 else "5–7년" if y <= 7 else "8년 이상"

    cnt = collections.Counter(band(j.get("career", "")) for j in rows)
    order = ["신입 가능", "1–2년", "3–4년", "5–7년", "8년 이상", "적지 않음"]
    note = f"모집중 개발 공고 {n:,}건 · {_dot(asof)} 수집 기준 · 경력 칸의 최소 연차로 셈"
    slides = [
        {"type": "cover", "lines": ["신입인데", "**경력 공고** 넣어도 돼요?"],
         "sub": "답 대신, 지금 공고가 요구하는 경력을 세 봤습니다", "note": note},
        {"type": "bars", "title": "공고가 적은 최소 경력", "sub": f"모집중 {n:,}건",
         "rows": [{"label": k, "value": cnt[k], "display": f"{cnt[k]:,}", "unit": f"{round(100 * cnt[k] / n)}%",
                   "hi": k == "신입 가능"} for k in order if cnt[k]], "note": note},
        {"type": "stat", "title": "신입이 바로 넣을 수 있는 곳", "num": f"{round(100 * cnt['신입 가능'] / n)}", "unit": "%",
         "label": f"{n:,}건 중 {cnt['신입 가능']:,}건이 경력 칸에 '신입' 을 적었다",
         "explain": "나머지는 경력을 요구하거나 적지 않았다. **'적지 않음'** 인 공고는 본문 자격요건을 먼저 읽어 보자.",
         "note": note},
        {"type": "end", "title": "그래서 이렇게", "lines": [
            "① '신입' 이 적힌 공고부터 — 가장 확실한 문",
            "② 경력 칸이 비어 있으면 자격요건 본문을 확인",
            "③ 1–2년 공고는 프로젝트 경험을 경력처럼 **숫자로** 정리",
            SEND], "note": note},
    ]
    caption = "\n\n".join([
        "[고민 상담소] 신입인데 경력 공고 넣어도 돼요?",
        f"정답 대신 숫자로 봤습니다. 지금 모집중인 개발 공고 {n:,}건이 경력 칸에 적은 최소 연차:",
        "\n".join(f"· {k}: {cnt[k]:,}건 ({round(100 * cnt[k] / n)}%)" for k in order if cnt[k]),
        f"{_dot(asof)} 수집한 모집중 개발 공고 기준, 경력 칸의 최소 연차로 셌습니다. 공고마다 사정이 다르니 출발점으로만 보세요.",
    ])
    return {"kind": "qa", "id": f"qa-newgrad-{asof.replace('-', '')}", "title": "신입인데 경력 공고?",
            "slides": slides, "caption": caption, "jobs": []}


# --- [JD 번역기] · [같은 직무 다른 회사] · [공부 로드맵] · [주간 리포트] · [채용 시그널] -----------
# CONTENT_SERIES.md 2절의 '만들 것' 들. 모두 공고 색인과 취업 브리핑(guide-engine)에서만 만든다.
BRIEF = "해설은 이 계정의 공고 분석(취업 브리핑)"


def _guides() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((GUIDE / "companies").glob("*.json"))]


def build_jd_translate() -> dict:
    """공고에 자주 나오는 문장 다섯 — 원문 그대로 인용하고, 브리핑이 풀어 쓴 '진짜 뜻' 과 점검 질문을 붙인다."""
    keys = ["대용량 트래픽", "MSA", "레거시", "고가용성", "코드 리뷰"]
    picks = []
    gs = _guides()
    for k in keys:
        for g in gs:
            hit = next(((p, s) for p in g.get("postings") or [] if not p.get("closed")
                        for s in p.get("study") or [] if k in (s.get("quote") or "") and s.get("gap_check")), None)
            if hit:
                picks.append((k, g["name"], *hit))
                break
    note = f"원문: 각 회사 모집 공고 · {BRIEF}"
    slides = [{"type": "cover", "lines": ["JD 번역기", "공고 문장의 **진짜 뜻**"],
               "sub": "자주 나오는 문장 다섯, 무엇을 할 줄 알라는 걸까", "note": note}]
    for i, (k, co, p, s) in enumerate(picks, 1):
        slides.append({"type": "gi", "no": f"'{k}' · {co}", "topic": _plain(s["topic"]).replace("**", ""),
                       "quote": _plain(s["quote"])[:200], "why": _first(_plain(s.get("why", "")), 140),
                       "check": _plain(s["gap_check"])[:150], "note": note})
    slides.append({"type": "end", "title": "읽는 법", "lines": [
        "형용사(대용량·안정적)는 **숫자**로 바꿔 읽는다 — 얼마나?",
        "'경험' 은 **사례 하나**를 말할 수 있냐는 뜻", SEND], "note": note})
    caption = "\n\n".join([
        "[JD 번역기] 공고 문장의 진짜 뜻 — 자주 나오는 문장 다섯",
        "\n".join(f"· '{k}' ({co} · {p['title'][:30]})" for k, co, p, _ in picks),
        "문장은 각 회사 모집 공고 원문 그대로 인용했고, 뜻풀이와 점검 질문은 이 계정의 공고 분석입니다.",
    ])
    return {"kind": "jd", "id": f"jd-translate-{date.today().isoformat().replace('-', '')}", "title": "JD 번역기",
            "slides": slides, "caption": caption, "jobs": []}


def build_same_role() -> dict:
    """같은 '백엔드' 라도 회사마다 요구가 다르다 — 브랜드 회사 다섯의 백엔드 공고 필수 조건을 나란히."""
    want = ["토스플레이스", "컬리", "빗썸", "CJ올리브영", "포티투닷", "쿠팡", "미리디"]
    rows, asof = _active_dev()
    live = {(re.sub(r"\W+", "", (j.get("company") or "")), re.sub(r"\W+", "", (j.get("title") or "").lower())) for j in rows}
    picks = []
    for g in _guides():
        if g["name"] not in want or len(picks) >= 5:
            continue
        p = next((p for p in g.get("postings") or [] if not p.get("closed")
                  and re.search(r"백엔드|Back-?end|Server|서버", p["title"], re.I) and (p.get("fit") or {}).get("must_have")), None)
        if p:
            picks.append((g["name"], p))
    note = f"원문: 각 회사 백엔드 모집 공고 · {BRIEF}"
    slides = [{"type": "cover", "lines": ["같은 '백엔드'", "**다른 사람**을 찾는다"],
               "sub": f"회사 {len(picks)}곳의 백엔드 공고, 꼭 필요하다고 적은 것", "note": note}]
    for co, p in picks:
        mh = [_plain(m).replace("**", "")[:70] for m in (p["fit"]["must_have"] or [])[:3]]
        st = (p.get("study") or [{}])[0].get("topic", "")
        slides.append({"type": "end", "title": co, "lines": [f"**{re.sub(r'\s*\(.*$', '', p['title'])[:34]}**"] + mh +
                       ([f"공부할 것 → {_plain(st).replace('**', '')[:48]}"] if st else []), "note": note})
    slides.append({"type": "end", "title": "그래서", "lines": [
        "'백엔드' 라는 이름보다 **필수 조건 첫 줄**을 먼저 본다",
        "내 경험과 겹치는 회사부터 — 전부를 준비할 수는 없다", SEND], "note": note})
    caption = "\n\n".join([
        "[같은 직무 다른 회사] 같은 '백엔드', 다른 사람을 찾는다",
        "\n".join(f"· {co} — {p['title'][:40]}" for co, p in picks),
        "필수 조건은 각 회사 공고 원문에서, 요약과 '공부할 것' 은 이 계정의 공고 분석입니다.",
    ])
    return {"kind": "same", "id": f"same-backend-{date.today().isoformat().replace('-', '')}", "title": "같은 백엔드 다른 회사",
            "slides": slides, "caption": caption, "jobs": []}


CATS = [("언어", ["Java", "Kotlin", "Python", "Go", "Node.js", "TypeScript", "JavaScript", "C++", "PHP", "Scala", "C#", "Rust"]),
        ("프레임워크", ["Spring", "Spring Boot", "JPA", "NestJS", "Django", "FastAPI", "Express", "Flask", "MyBatis"]),
        ("데이터 저장", ["MySQL", "PostgreSQL", "Redis", "MongoDB", "Oracle", "Elasticsearch", "DynamoDB", "MariaDB"]),
        ("메시징", ["Kafka", "RabbitMQ", "SQS", "Redis Pub/Sub"]),
        ("인프라·운영", ["AWS", "Docker", "Kubernetes", "GCP", "Terraform", "Linux", "Jenkins", "GitHub Actions", "Git"])]


def build_roadmap() -> dict:
    """백엔드 공고가 함께 적는 기술을 단계별로 센다 — 순서는 우리가 정한 학습 흐름, 숫자는 공고에서."""
    rows, asof = _active_dev()
    be = [j for j in rows if re.search(r"백엔드|back-?end|server|서버", j.get("title") or "", re.I)]
    n = len(be)
    cnt = collections.Counter(s for j in be for s in set(_stack(j)))
    note = f"모집중 백엔드 공고 {n:,}건 · {_dot(asof)} 수집 기준 · 단계 순서는 이 계정의 제안"
    slides = [{"type": "cover", "lines": ["백엔드", "**공부 로드맵**"], "sub": f"공고 {n:,}건이 함께 적은 기술을 단계별로", "note": note}]
    for i, (cat, names) in enumerate(CATS, 1):
        top = sorted(((k, cnt[k]) for k in names if cnt[k]), key=lambda x: -x[1])[:4]
        if top:
            slides.append({"type": "bars", "title": f"{i}단계 · {cat}", "sub": "이 기술을 적은 공고 수",
                           "rows": [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{round(100 * v / n)}%", "hi": j == 0}
                                    for j, (k, v) in enumerate(top)], "note": note})
    slides.append({"type": "end", "title": "순서대로 하나씩", "lines": [
        "각 단계에서 **1위 하나**만 먼저 — 넓게보다 깊게",
        "메시징·인프라는 공고 '우대사항' 에 자주 — 차이를 만드는 칸", SEND], "note": note})
    caption = "\n\n".join([
        f"[공부 로드맵] 백엔드 — 모집중 공고 {n:,}건이 함께 적은 기술",
        "\n".join(f"{i}단계 {cat}: " + " · ".join(f"{k} {round(100 * cnt[k] / n)}%" for k in sorted([k for k in names if cnt[k]], key=lambda x: -cnt[x])[:3])
                  for i, (cat, names) in enumerate(CATS, 1)),
        f"{_dot(asof)} 수집한 모집중 백엔드 공고(제목 기준) {n:,}건에서 셌습니다. 단계 순서는 이 계정의 제안입니다.",
    ])
    return {"kind": "roadmap", "id": f"roadmap-backend-{asof.replace('-', '')}", "title": "백엔드 공부 로드맵",
            "slides": slides, "caption": caption, "jobs": []}


def build_weekly() -> dict:
    rows, asof = _active_dev()
    n = len(rows)
    today = date.today()
    soon = [j for j in rows if (d := _deadline(j, today)) and 0 <= (d - today).days <= 7]
    newgrad = sum(1 for j in rows if "신입" in (j.get("career") or ""))
    cos = collections.Counter(re.sub(r"\(.*?\)|㈜|주식회사", "", j.get("company") or "").strip() for j in rows).most_common(6)
    st = collections.Counter(s for j in rows for s in set(_stack(j))).most_common(6)
    note = f"모집중 개발 공고 {n:,}건 · {_dot(asof)} 수집 기준"
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "건", "lines": ["이번 주", "개발 채용 리포트"],
         "sub": f"{_dot(today.isoformat())} 주 · 숫자로 보는 한 주", "note": note},
        {"type": "bars", "title": "공고를 가장 많이 연 회사", "sub": "모집중 개발 공고 수",
         "rows": [{"label": k[:8], "value": v, "display": f"{v}", "hi": i == 0} for i, (k, v) in enumerate(cos)], "note": note},
        {"type": "bars", "title": "가장 많이 찾는 기술", "sub": "공고에 적힌 수",
         "rows": [{"label": k, "value": v, "display": f"{v}", "unit": f"{round(100 * v / n)}%", "hi": i == 0} for i, (k, v) in enumerate(st)], "note": note},
        {"type": "stat", "title": "7일 안에 닫히는 공고", "num": f"{len(soon):,}", "unit": "건",
         "label": f"신입 가능 공고는 {newgrad:,}건", "explain": "마감일을 적지 않은 공고가 많아 실제로 닫히는 수는 더 많다.", "note": note},
        {"type": "end", "title": "다음 주 월요일에 또", "lines": ["저장해 두고 한 주씩 비교해 보세요", SEND], "note": note},
    ]
    caption = "\n\n".join([
        f"[주간 리포트] 이번 주 개발 채용 — 모집중 {n:,}건",
        "공고를 가장 많이 연 회사: " + " · ".join(f"{k} {v}" for k, v in cos),
        "가장 많이 찾는 기술: " + " · ".join(f"{k} {v}" for k, v in st),
        f"7일 안에 닫히는 공고 {len(soon):,}건 · 신입 가능 {newgrad:,}건",
        f"{_dot(asof)} 수집한 모집중 개발 공고 기준입니다.",
    ])
    return {"kind": "weekly", "id": f"weekly-{today.isoformat().replace('-', '')}", "title": "주간 리포트",
            "slides": slides, "caption": caption, "jobs": []}


def build_signals() -> dict:
    """회사 다섯의 채용 공고가 말해 주는 방향 — 브리핑 signals(해석)와 근거. 해석은 '추정' 으로 표시."""
    want = ["CJ올리브영", "쿠팡", "컬리", "토스플레이스", "빗썸"]
    picks = []
    for g in _guides():
        if g["name"] in want and (g.get("company") or {}).get("signals"):
            picks.append((g["name"], g["company"]["signals"][0]))
    note = f"근거: 각 회사 모집 공고·공시·기사 · 해석은 이 계정의 추정"
    slides = [{"type": "cover", "lines": ["채용 공고가", "**먼저 말해 주는 것**"], "sub": f"회사 {len(picks)}곳의 다음 방향", "note": note}]
    for co, s in picks:
        tag = "" if s.get("confidence") == "confirmed" else " (추정)"
        slides.append({"type": "end", "title": co, "lines": [
            _plain(s["reading"]).replace("**", "") + tag,
            "근거 · " + _first(_plain(s.get("evidence", "")).replace("**", "").lstrip("•-· "), 120),
            "그래서 · " + _first(_plain(s.get("so_what", "")).replace("**", ""), 110)], "note": note})
    slides.append({"type": "end", "title": "지원서에 쓰는 법", "lines": [
        "회사가 **지금 키우는 쪽**과 내 경험을 잇는 한 문장", SEND], "note": note})
    caption = "\n\n".join([
        "[채용 시그널] 채용 공고가 먼저 말해 주는 것 — 회사 다섯의 다음 방향",
        "\n".join(f"· {co}: {_plain(s['reading']).replace('**', '')}" + ("" if s.get("confidence") == "confirmed" else " (추정)")
                  for co, s in picks),
        "근거는 각 회사 모집 공고와 공시·기사이고, 해석은 이 계정의 추정입니다(추정 표시).",
    ])
    return {"kind": "signal", "id": f"signal-{date.today().isoformat().replace('-', '')}", "title": "채용 시그널",
            "slides": slides, "caption": caption, "jobs": []}


# --- [인재상 해부] ---------------------------------------------------------------
# 채용 페이지의 '인재상' 문구가 아니라 **증거에서 거꾸로 읽은 인재상**이다 — 돈 버는 구조(성과 기준),
# 공고들이 반복하는 요구, 현직 리더가 공개 인터뷰에서 한 말, 전형, 연봉과 '아직 모르는 것'.
# 전부 취업 브리핑(guide-engine)에 출처와 함께 있는 것만 쓴다. 해석(inferred)은 '(추정)' 으로 표시한다.
def _clean(s: str) -> str:
    return re.sub(r"`", "", _plain(s or "")).strip()


def _nostar(s: str) -> str:
    return _clean(s).replace("**", "")


def _sent(s: str, limit: int = 150) -> str:
    """문장 단위로 limit 자까지 — '보다' 처럼 '다' 로 끝나는 낱말에서 자르지 않도록 마침표로만 나눈다.
    강조(**)가 짝이 안 맞으면 걷어 낸다."""
    out = ""
    for p in re.split(r"(?<=[.!?])\s+", (s or "").replace(chr(10), " ")):
        if len(re.sub(r"\*\*", "", out + " " + p)) > limit and out:
            break
        out = (out + " " + p).strip()
    return out.replace("**", "") if out.count("**") % 2 else out


def _est(x: dict) -> str:
    return "" if x.get("confidence") == "confirmed" else " (추정)"


def _eok(won: int | None) -> str:
    """원 → '1,733억' / '9.3억' / '6,617만'. 매출 칸 한 줄."""
    if not won:
        return ""
    e = won / 1e8
    return f"{e:,.0f}억" if e >= 100 else f"{e:.1f}억" if e >= 1 else f"{won / 1e4:,.0f}만"


def _salary_slide(g: dict, facts: dict | None, note: str, cite) -> dict | None:
    """연봉 한 장 — 브리핑 연봉이 있으면 그것(출처별 범위), 없으면 원티드의 국민연금 기반 평균.
    국민연금 추정치는 여러 회사가 **똑같은 값**으로 나오는 상한이 있다(6,032만원 등) — 그때는 '그 이상' 으로 읽게 쓴다."""
    sal = g.get("salary") or {}
    if sal.get("bands"):
        b = sal["bands"][0]
        for s in b.get("sources") or []:
            cite([s])
        rng = b["low"] != b["high"]
        unit = sal.get("unit", "만원")
        why = " ".join(x for x in re.split(r"(?<=[.])\s+", re.sub(r"\s*\([^()]*(?:inferred|confirmed)[^()]*\)", "",
                                                                     _clean(sal.get("note", ""))))
                       if not re.search(r"bands|inferred|confirmed|basis", x))
        return {"type": "stat", "title": "평균 연봉", "num": f"{b['low']:,}", "unit": unit,
                "label": (f"부터 최고 {b['high']:,}{unit}까지 · " if rng else "") + f"{b.get('role', '')} · {sal.get('as_of', '')}",
                "explain": _sent(why, 90), "note": note}
    if not (facts and facts.get("salary")):
        return None
    from .company_facts import load as _facts_all
    s = facts["salary"]
    cite([{"title": f"{facts.get('title') or g['name']} 기업정보(원티드)", "url": facts["url"]}])
    same = [n for n, f in _facts_all().items() if f.get("salary") == s and n != facts["name"]]
    tag = next((t for t in facts.get("tags") or [] if "연봉" in t), "")
    if same:
        why = (f"{same[0]} 등 다른 회사도 **정확히 같은 {s:,}만원**으로 나온다 — 추정식의 상한으로 보인다. "
               "실제 평균은 그 이상일 수 있다 (추정).")
    elif s < 3000:
        why = "매장·현장 인력까지 섞인 전 직군 평균이다 — **개발 직군 값으로 읽으면 안 된다.**"
    else:
        why = "국민연금 납부액으로 추정한 **전 직군 평균**이다 — 개발 직군만의 값은 공개돼 있지 않다."
    return {"type": "stat", "title": "평균 연봉", "num": f"{s:,}", "unit": "만원",
            "label": " · ".join(x for x in [f"전 직군 · 국민연금 기준 · {facts.get('salary_as_of') or ''}", tag] if x),
            "explain": why, "note": note}


def build_talent(name: str) -> dict:
    """[인재상 해부] 회사 한 곳, 10장.
    ① 표지 ② 회사 한눈에(업종·업력·인원·매출·위치 — 원티드 공개값) ③ 무엇으로 돈을 버나 ④ 도메인, 쉽게
    ⑤ 지금 여는 자리 ⑥~ 현직 리더의 공개 발언·신호·남들과 갈리는 한 수(남는 칸만큼) ⑨ 평균 연봉 ⑩ 한 줄로.
    작은 회사는 이름만으로는 무엇을 하는지 모른다 — ②③④ 를 앞에 둔 까닭이다."""
    from .company_facts import get as _facts
    g = _guide_company(name)
    co = g["company"]
    short = g["name"]
    facts = _facts(short)
    live = [p for p in g["postings"] if not p.get("closed")]
    note = f"{short} · 취업 브리핑(공고·공시·기사·공개 인터뷰, {g.get('updated_at', '')[:10]}) · 원티드 기업정보 · (추정)은 이 계정의 해석"
    srcs: list[tuple[str, str]] = []

    def cite(items):
        for s in items or []:
            if s.get("url") and s["url"] not in [u for _, u in srcs]:
                srcs.append((s.get("title") or s.get("publisher") or "", s["url"]))

    sig = [x for x in co.get("signals") or [] if "수집" not in x["reading"]]
    hook = _nostar(sig[0]["reading"]) if sig else _nostar(g["one_liner"])
    emp = (facts or {}).get("employees")
    small = bool(emp and emp < 300)
    head: list[dict] = [{"type": "cover", "lines": [short, "**이런 사람**을 찾는다"],
                         "sub": (f"직원 {emp:,}명 — " if small else "") + hook + _est(sig[0] if sig else {"confidence": "confirmed"}),
                         "note": note}]

    # ② 회사 한눈에 — 숫자는 원티드 기업정보(국민연금·국세청·공시 기반)
    if facts:
        cite([{"title": f"{facts.get('title') or short} 기업정보(원티드)", "url": facts["url"]}])
        rows = []                                    # '하는 일' 은 길어서 표 글자를 통째로 줄인다 — 부제로 뺀다
        if facts.get("industry"):
            rows.append(["업종", facts["industry"][:22]])
        if facts.get("founded"):
            rows.append(["설립", f"{facts['founded']}년 · 업력 {facts.get('age')}년"])
        if emp:
            rows.append(["인원", f"{emp:,}명 (국민연금 가입자)"])
        if facts.get("sales"):
            rows.append(["매출", f"{_eok(facts['sales'])}원"])
        if facts.get("location"):
            rows.append(["위치", facts["location"]])
        perks = [t for t in facts.get("tags") or [] if not re.search(r"명|연봉", t)]
        if perks:
            rows.append(["표시", " · ".join(perks[:2])])
        head.append({"type": "table", "title": "회사 한눈에",
                     "sub": _first(_nostar(g["one_liner"]), 70) + " · 숫자는 원티드 기업정보 공개값(인원 = 국민연금 가입자)",
                     "head": ["", ""], "rows": rows, "note": note})

    # ③ 무엇으로 돈을 버나 — 작은 회사일수록 사업 설명을 앞에
    rev = (co.get("revenue") or [{}])[0]
    cite(co.get("business_sources"))
    cite(rev.get("sources"))
    lines = [_sent(_clean(co.get("business", "")), 120)] if small or not rev else []
    if rev:
        lines.append(_sent(_clean(rev.get("how", "")), 110) + _est(rev))
    head.append({"type": "end", "title": "무엇으로 돈을 버나", "lines": [x for x in lines if x][:2], "note": note})

    # ④ 도메인, 쉽게 — 이 회사에서 일하려면 알아 둘 세계
    doms = (co.get("domains") or [])[:3]
    if doms:
        head.append({"type": "end", "title": "이 회사의 도메인, 쉽게",
                     "lines": [f"**{_nostar(d['name'])[:24]}** — {_first(_nostar(d.get('why', '')), 60)}"
                               + (f" · 알아 둘 것: {', '.join(_nostar(w) for w in (d.get('what_to_know') or [])[:3])}"
                                  if d.get("what_to_know") else "") for d in doms], "note": note})

    # ⑤ 지금 여는 자리
    # 한 문장이 길면 _first 가 통째로 돌려준다 — 칸이 좁아 이름이 세로로 접히므로 글자 수로 한 번 더 자른다
    roles = [{"role": re.sub(r"^\[[^\]]*\]\s*|\s*\(.*$", "", p["title"])[:22],
              "meta": (lambda m: m if len(m) <= 34 else m[:33] + "…")(_first(_nostar(p.get("verdict", "")), 34))}
             for p in live if p.get("verdict")]
    roles = list({r["role"]: r for r in reversed(roles)}.values())[::-1][:4]   # 같은 이름은 한 번만
    if roles:
        head.append({"type": "jobs", "title": f"지금 여는 자리 {len(live)}개 중", "rows": roles, "note": note})

    tail = [x for x in [_salary_slide(g, facts, note, cite)] if x]

    # 남는 칸 — 현직 리더의 말 → 신호 → 한 수 순서로 채운다
    extra: list[dict] = []
    for pe in (g.get("people") or [])[:2]:
        cite(pe.get("public_work"))
        lean = [_nostar(x) for x in pe.get("leanings") or []]
        if lean:
            extra.append({"type": "gi", "no": f"현직 리더의 말 · {pe['role']}", "topic": _first(lean[0], 70),
                          "quote": " / ".join(_first(x, 90) for x in lean[1:3]),
                          "why": _sent(_clean(pe.get("what_it_means", "")), 150),
                          "quote_label": "공개 인터뷰에서", "check_label": "출처",
                          "check": f"{(pe.get('public_work') or [{}])[0].get('title', '')[:60]} · {(pe.get('public_work') or [{}])[0].get('kind', '')}",
                          "note": note})
    for s in sig[1:3]:
        extra.append({"type": "end", "title": _first(_nostar(s["reading"]), 40) + _est(s),
                      "lines": ["근거 · " + _first(_nostar(s.get("evidence", "")).lstrip("•-· "), 110),
                                "그래서 · " + _first(_nostar(s.get("so_what", "")), 120)], "note": note})
    edges = [(re.sub(r"\s*\(.*$", "", p["title"])[:24], e) for p in live[:3] for e in (p.get("edge") or [])[:1]]
    if edges:
        extra.insert(min(len(extra), 2), {"type": "end", "title": "남들과 갈리는 한 수",
                                          "lines": [f"**{t}** · {_nostar(e['idea'])[:60]} ({e.get('effort', '')})" for t, e in edges],
                                          "note": note})
    room = 9 - len(head) - len(tail)                   # 인스타 캐러셀 10장 — 마지막 '한 줄로' 를 남긴다
    slides = head + extra[:max(room, 0)] + tail

    internal = re.compile(r"salary|people|signals|비웠|PROMPT|사이클|엔진|보강|평판|소문|열지 못했|403|더 찾지|검색 결과"
                          r"|읽지 않았|읽혔|읽지 못|제목만|본문|열리지|머리말|wd/|\(\d{6}\)|확인하지 못했다\.?$")
    oq = [_first(_nostar(q), 90) for q in ((g.get("salary") or {}).get("open_questions") or []) + (g.get("open_questions") or [])
          if not internal.search(q)][:3]
    slides.append({"type": "end", "title": "한 줄로", "lines": [
        _first(_nostar(sig[0].get("so_what", "")), 110) if sig else _nostar(g["one_liner"]),
        *( [f"공개 자료로 확인 안 되는 것 · {oq[0]}"] if oq else [] ),
        f"{short} 가려는 친구에게 보내 주세요"], "note": note})
    for p in live[:4]:
        cite([{"title": p["title"], "url": p.get("url")}])

    fact_line = ""
    if facts:
        fact_line = " · ".join(x for x in [
            facts.get("industry"), f"설립 {facts['founded']}년" if facts.get("founded") else "",
            f"인원 {emp:,}명" if emp else "", f"매출 {_eok(facts.get('sales'))}원" if facts.get("sales") else "",
            f"평균연봉 {facts['salary']:,}만원(국민연금 기준, 전 직군)" if facts.get("salary") else "", facts.get("location")] if x)
    caption = "\n\n".join(x for x in [
        f"[인재상 해부] {short} — {hook}",
        _first(_nostar(g["one_liner"]), 200),
        f"▪ 회사 한눈에\n{fact_line}" if fact_line else "",
        "▪ 도메인\n" + "\n".join(f"· {_nostar(d['name'])} — {_first(_nostar(d.get('why', '')), 90)}" for d in doms) if doms else "",
        "▪ 공고가 먼저 말해 주는 것\n" + "\n".join(f"· {_nostar(s['reading'])}{_est(s)}" for s in sig[:4]) if sig else "",
        "▪ 공개 자료로 확인 안 되는 것 — 면접 끝 질문으로 쓸 만하다\n" + "\n".join(f"· {q}" for q in oq) if oq else "",
        "채용 페이지의 '인재상' 문구가 아니라 공고·공시·기사·공개 인터뷰에서 거꾸로 읽었습니다. 평균연봉은 국민연금 기준 전 직군 "
        "평균이라 개발 직군 값과 다를 수 있습니다. (추정)은 이 계정의 해석이고, 커뮤니티 평판·소문은 쓰지 않았습니다.",
        "📌 출처\n" + "\n".join(f"· {t[:50]} {u}" for t, u in srcs[:8]),
    ] if x)
    return {"kind": "talent", "id": f"talent-{g['slug']}-{date.today().isoformat().replace('-', '')}",
            "title": f"{short} 인재상", "slides": slides, "caption": caption, "jobs": []}


# --- 캡션의 회사 정보 -------------------------------------------------------
def _sentences(s: str, n: int = 2, limit: int = 220) -> str:
    """브리핑 문단에서 앞 n 문장 — 마크다운 표기(**, `)는 떼고 limit 자 안에서."""
    t = re.sub(r"\*\*|`", "", s or "").replace("\n", " ")
    parts = re.split(r"(?<=[.다])\s+", t)
    out = ""
    for p in parts[:n]:
        if out and len(out) + len(p) > limit:
            break
        out = (out + " " + p).strip()
    return out


def company_info(name: str) -> str:
    """캡션에 붙일 회사 정보 — 취업 브리핑(guide-engine)이 출처와 함께 조사한 것만 쓴다.
    확인된(confirmed) 것은 그대로, 추정(inferred)은 '(추정)' 을 붙인다. 브리핑이 없으면 빈 문자열."""
    try:
        g = _guide_company(name)
    except (StopIteration, OSError, KeyError):
        return ""
    c = g.get("company") or {}
    blocks = []
    if c.get("business"):
        blocks.append("▪ 무슨 회사\n" + _sentences(c["business"], 3, 260))
    scale = [x for x in c.get("scale") or [] if x.get("confidence") == "confirmed"][:3]
    if scale:
        blocks.append("▪ 규모\n" + "\n".join(f"· {x['label']}: {re.sub(r'[*`]', '', x['value'])}" for x in scale))
    rev = (c.get("revenue") or [])[:3]
    if rev:
        blocks.append("▪ 어떻게 돈을 버나\n" + "\n".join(f"· {x['name']}" for x in rev))
    sig = (c.get("signals") or [])[:2]
    if sig:
        lines = []
        for x in sig:
            tag = "" if x.get("confidence") == "confirmed" else " (추정)"
            lines.append(f"· {re.sub(r'[*`]', '', x['reading'])}{tag}\n  → {_sentences(x.get('so_what', ''), 1, 140)}")
        blocks.append("▪ 채용에서 읽히는 것\n" + "\n".join(lines))
    doms = c.get("domains") or []
    know = [k for d in doms[:2] for k in (d.get("what_to_know") or [])[:2]]
    if know:
        blocks.append("▪ 개발자가 알아두면 좋은 것\n" + "\n".join(f"· {re.sub(r'[*`]', '', k)[:90]}" for k in know))
    bands = [b for b in ((g.get("salary") or {}).get("bands") or []) if b.get("confidence") == "confirmed"][:2]
    if bands:
        blocks.append("▪ 연봉(확인된 것)\n" + "\n".join(
            f"· {b.get('role', '')} {b.get('level', '')}: {b.get('low')}~{b.get('high')}만원" for b in bands))
    if blocks:
        blocks.append("※ 회사 정보는 공시·기사·공고를 모아 정리했습니다. 추정은 (추정)으로 표시.")
    return "\n\n".join(blocks)


def enrich(caption: str, name: str, *, before: str = "") -> str:
    """캡션에 회사 정보를 끼운다. before 가 있으면 그 문단 앞에, 없으면 해시태그 앞에. 2,200자를 넘지 않게."""
    info = company_info(name)
    if not info:
        return caption
    parts = caption.split("\n\n")
    at = next((i for i, p in enumerate(parts) if before and p.startswith(before)), None)
    if at is None:
        at = next((i for i, p in enumerate(parts) if p.startswith("#")), len(parts))
    out = "\n\n".join(parts[:at] + [info] + parts[at:])
    while len(out) > 2150 and "\n\n" in info:
        info = info.rsplit("\n\n", 1)[0]
        out = "\n\n".join(parts[:at] + [info] + parts[at:])
    return out


# --- 찍기 · 승인 ---------------------------------------------------------
def render(post: dict) -> list[Path]:
    from .render import _page_maker
    theme, series = THEMES[post["kind"]], SERIES[post["kind"]]
    dest = OUT / post["id"]
    dest.mkdir(parents=True, exist_ok=True)
    paths, n = [], len(post["slides"])
    for i, s in enumerate(post["slides"], 1):
        data = {"theme": theme, "series": series, "page": f"{i} / {n}", "slide": s}
        html = TEMPLATE.read_text(encoding="utf-8").replace(
            "/*__DATA__*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
        page = _page_maker().new_page(viewport={"width": 1080, "height": 1350})
        try:
            page.set_content(html, wait_until="load")
            page.wait_for_function("window.__ready === true", timeout=30000)
            bad = page.evaluate("window.__overflow")
            small = page.evaluate("window.__minBody")
            if bad or small < 18:
                print(f"[series] {post['id']} {i}장: 넘침={bad} 최소 글자 {small:.0f}px", file=sys.stderr)
            p = dest / f"{i:02d}.jpg"
            page.query_selector(".sheet").screenshot(path=str(p), type="jpeg", quality=95)
            paths.append(p)
        finally:
            page.close()
    return paths


def approve(post: dict, paths: list[Path]) -> Path:
    """publish.cli approve-collection 과 같은 모양으로 inbox 에 넣는다 — 발행(수동·데몬)과
    '이미 낸 공고' 판단(publish.posted)이 이 모양을 읽는다."""
    item = uuid.uuid4().hex[:8]
    d = INBOX / item
    d.mkdir(parents=True)
    shutil.copyfile(paths[0], d / "poster.jpg")
    for i, p in enumerate(paths[1:], 1):
        shutil.copyfile(p, d / f"slide_{i:02d}.jpg")
    tags = " ".join(f"#{t}" for t in TAGS[post["kind"]])
    cap = f"{post['caption']}\n\n{tags}"
    (d / "caption_instagram.txt").write_text(cap, encoding="utf-8")
    bundle = {"id": item, "job_key": f"collection:{post['id']}", "company": SERIES[post["kind"]],
              "role": post["title"], "template": "series", "platforms": ["instagram"],
              "captions": {"instagram": cap}, "caption": cap, "note": post["kind"], "force": False,
              "collection": {"id": post["id"], "kind": post["kind"], "title": post["title"],
                             "count": len(post["jobs"]), "jobs": post["jobs"]},
              "format": "carousel", "approved_on": socket.gethostname(),
              "approved_at": datetime.now().isoformat(timespec="seconds")}
    (d / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.series")
    ap.add_argument("kind", choices=["stack", "rates", "guide", "term", "interview", "qa", "jd", "same", "roadmap", "weekly", "signal", "talent"])
    ap.add_argument("company", nargs="?", default="")
    ap.add_argument("--dry", action="store_true", help="찍기만 하고 승인함에 넣지 않는다")
    args = ap.parse_args()
    from .render import shutdown
    if args.kind == "guide":
        from publish.posted import posted
        post = build_guide(args.company, exclude=set(posted()))
    elif args.kind == "term":
        post = build_term_idempotency()
    elif args.kind == "interview":
        name, _, part = args.company.partition(":")
        post = build_interview(name, part)
    elif args.kind == "qa":
        post = build_qa_newgrad()
    elif args.kind == "talent":
        post = build_talent(args.company)
    elif args.kind in ("jd", "same", "roadmap", "weekly", "signal"):
        post = {"jd": build_jd_translate, "same": build_same_role, "roadmap": build_roadmap,
                "weekly": build_weekly, "signal": build_signals}[args.kind]()
    else:
        post = build_stack() if args.kind == "stack" else build_rates()
    try:
        paths = render(post)
    finally:
        shutdown()
    print(f"[series] {post['id']} {len(paths)}장 → {paths[0].parent}")
    if not args.dry:
        print(f"[series] 승인함 → {approve(post, paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
