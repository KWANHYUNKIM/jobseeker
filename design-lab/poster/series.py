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
  python -m poster.series pay            # [신입 초봉] 신입 연봉을 숫자로 적은 곳
  python -m poster.series perk           # [이런 조건 되는 곳] 재택·주 4일·스톡옵션·주거 지원
  python -m poster.series map "판교·분당:성수"   # [출근길 지도] 권역별 공고 + 두 곳 밸런스 게임
  python -m poster.series welcome        # [신입 환영] 전환형 인턴·졸업예정자·신입 우대
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
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
    "pay": {"paper": "#fbf6e9", "ink": "#1c1708", "sub": "#6e6450", "accent": "#e8a400", "line": "#eadfc2"},
    "perk": {"paper": "#effaf3", "ink": "#0d2618", "sub": "#4e6b5a", "accent": "#12b886", "line": "#cdebd9"},
    "map": {"paper": "#f1f3f9", "ink": "#121a2e", "sub": "#58627a", "accent": "#4263eb", "line": "#d6dcec"},
    "welcome": {"paper": "#fff4f1", "ink": "#2b1310", "sub": "#7a5a54", "accent": "#f76707", "line": "#f3d9d1"},
    "gongchae": {"paper": "#14161c", "ink": "#f4f2ec", "sub": "#9b9fa9", "accent": "#ff6b4a", "line": "#2b2f38"},
    "lunch": {"paper": "#fff8ef", "ink": "#24170d", "sub": "#7b6a58", "accent": "#ffb02e", "line": "#f0e2cf"},
    "kit": {"paper": "#f3f0ff", "ink": "#1b1533", "sub": "#655d80", "accent": "#7048e8", "line": "#ddd6f7",
            "photo_accent": "#c0abff"},
    "balance": {"paper": "#141218", "ink": "#ffffff", "sub": "#b9b4c7", "accent": "#ffe066", "line": "#2c2833"},
    "tier": {"paper": "#141218", "ink": "#ffffff", "sub": "#b9b4c7", "accent": "#ffe066", "line": "#2c2833"},
    "contra": {"paper": "#15171d", "ink": "#f4f2ec", "sub": "#9b9fa9", "accent": "#ffd43b", "line": "#2b2f38"},
    "game": {"paper": "#0b0d1a", "ink": "#f2f4ff", "sub": "#9aa0c0", "accent": "#5df2c1", "line": "#232845"},
    "security": {"paper": "#0f1420", "ink": "#f3f4f8", "sub": "#9ba3b4", "accent": "#ff4d5a", "line": "#26304a"},
    "mobile": {"paper": "#f4f2fd", "ink": "#1a1533", "sub": "#615b7d", "accent": "#7f52ff", "line": "#dfdaf5"},
    "docker": {"paper": "#eef6fd", "ink": "#0b2236", "sub": "#4f6a80", "accent": "#1d63ed", "line": "#d3e5f4"},
    "swift": {"paper": "#fff6f2", "ink": "#2a1410", "sub": "#7a5a52", "accent": "#f05138", "line": "#f3ddd5"},
    "java": {"paper": "#f6f1ea", "ink": "#1c2430", "sub": "#5f6875", "accent": "#e76f00", "line": "#e6ddd0"},
    "rust": {"paper": "#1b1210", "ink": "#f6efe9", "sub": "#b8a59b", "accent": "#f2804a", "line": "#3a2a24"},
    "node": {"paper": "#f3f8ef", "ink": "#16240f", "sub": "#566b4c", "accent": "#3c873a", "line": "#dbe8d3"},
    "python": {"paper": "#0f1b2d", "ink": "#eef3fb", "sub": "#95a6bf", "accent": "#ffd43b", "line": "#20314d"},
    "lang": {"paper": "#0e1626", "ink": "#eef3fb", "sub": "#94a3bc", "accent": "#ffd23f", "line": "#1f2c44"},
    "agent": {"paper": "#faf6f1", "ink": "#1f1a14", "sub": "#6f6457", "accent": "#d97706", "line": "#ece2d5"},
    "vc": {"paper": "#160f24", "ink": "#f4f0fb", "sub": "#a69bbb", "accent": "#b388ff", "line": "#2d2340"},
    "spring": {"paper": "#f2f8ef", "ink": "#14230f", "sub": "#5c6e55", "accent": "#4c9b2f", "line": "#d6e6cf"},
    "robot": {"paper": "#111418", "ink": "#f2f4f7", "sub": "#9aa2ad", "accent": "#36d399", "line": "#262c34"},
    "wish": {"paper": "#fdf7ee", "ink": "#22180c", "sub": "#76674f", "accent": "#c2410c", "line": "#efe2cc"},
    "cloud": {"paper": "#0f1b2d", "ink": "#f3f6fa", "sub": "#97a6ba", "accent": "#ff9900", "line": "#22334d"},
    "gap": {"paper": "#f6f4ef", "ink": "#181614", "sub": "#6b655c", "accent": "#d9480f", "line": "#e2ddd2"},
    "usvs": {"paper": "#10131a", "ink": "#f1f3f7", "sub": "#9aa1ae", "accent": "#7ee787", "line": "#262b36"},
    "junior": {"paper": "#fff6ec", "ink": "#2a1a0c", "sub": "#77624f", "accent": "#f0620a", "line": "#f0dcc7"},
    "health": {"paper": "#f3f8fb", "ink": "#0f2230", "sub": "#566b7a", "accent": "#0b84c6", "line": "#d4e4ee"},
    "pangyo": {"paper": "#f1f6ee", "ink": "#14241a", "sub": "#5b6d60", "accent": "#1a9e5a", "line": "#d3e2d6"},
    "mobility": {"paper": "#0a1a2f", "ink": "#f2f6fb", "sub": "#94a7bf", "accent": "#00c2ff", "line": "#1d3352"},
    "aitool": {"paper": "#0d1117", "ink": "#f0f3f6", "sub": "#9198a1", "accent": "#d2a8ff", "line": "#262c36"},
    "cert": {"paper": "#f4f1fb", "ink": "#17122b", "sub": "#615a78", "accent": "#5f3dc4", "line": "#ddd5f0"},
}
SERIES = {"insight": "[데이터로 본 채용]", "guide": "[들어가려면]", "term": "[IT 용어]",
          "interview": "[면접 예상 질문]", "qa": "[고민 상담소]", "jd": "[JD 번역기]",
          "same": "[같은 직무 다른 회사]", "roadmap": "[공부 로드맵]", "weekly": "[주간 리포트]", "signal": "[채용 시그널]", "talent": "[인재상 해부]",
          "pay": "[신입 초봉]", "perk": "[이런 조건 되는 곳]", "map": "[출근길 지도]", "welcome": "[신입 환영]", "gongchae": "[공채는 끝났다]",
          "lunch": "[점심 지도]", "kit": "[첫 출근 웰컴키트]", "balance": "[둘 중 하나]", "tier": "[티어표]",
          "contra": "[공고 원문]", "game": "[게임사 채용]", "security": "[보안 채용]",
          "cert": "[자격증 우대]", "aitool": "[AI 코딩 도구]", "mobility": "[모빌리티 채용]", "pangyo": "[판교 채용]", "health": "[헬스케어 채용]", "junior": "[주니어 채용]", "usvs": "[미국 vs 우리]", "gap": "[신입 vs 경력]", "cloud": "[클라우드 채용]", "wish": "[희망 초봉 vs 공고]", "robot": "[로봇 채용]", "spring": "[스프링 채용]", "vc": "[투자와 채용]", "agent": "[AI 에이전트 채용]", "lang": "[언어 순위 vs 공고]", "mobile": "[모바일 채용]", "python": "[파이썬 채용]", "node": "[Node.js 채용]", "rust": "[Rust 채용]", "java": "[Java 채용]", "swift": "[Swift 채용]", "docker": "[Docker 채용]"}
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
        "talent": ["인재상", "기업분석", "개발자채용", "이직준비", "면접준비"],
        "pay": ["신입연봉", "개발자연봉", "초봉", "신입개발자", "개발자취업"],
        "perk": ["재택근무", "주4일제", "스톡옵션", "개발자복지", "개발자채용"],
        "map": ["판교", "성수", "개발자채용", "IT회사", "밸런스게임"],
        "welcome": ["신입개발자", "전환형인턴", "졸업예정자", "개발자취업", "신입채용"],
        "gongchae": ["공채", "수시채용", "취업전략", "신입개발자", "중고신입"],
        "lunch": ["판교맛집", "판교점심", "판교테크노밸리", "IT회사", "개발자채용"],
        "kit": ["웰컴키트", "신입사원", "첫출근", "IT회사", "개발자취업"],
        "balance": ["밸런스게임", "신입개발자", "개발자취업", "IT회사", "취업고민"],
        "tier": ["신입연봉", "개발자연봉", "초봉", "신입개발자", "연봉티어"],
        "contra": ["채용공고", "신입개발자", "자격요건", "개발자취업", "중고신입"],
        "game": ["게임회사", "게임개발자", "게임스컴", "개발자채용", "게임업계취업"],
        "security": ["정보보안", "보안엔지니어", "보안채용", "개발자채용", "IT취업"],
        "mobile": ["모바일개발자", "안드로이드", "iOS개발자", "Kotlin", "Flutter"],
        "docker": ["Docker", "도커", "DevOps", "백엔드개발자", "개발자채용"],
        "swift": ["Swift", "iOS개발자", "SwiftUI", "앱개발자", "개발자채용"],
        "java": ["자바", "Java", "백엔드개발자", "스프링", "개발자채용"],
        "rust": ["Rust", "러스트", "시스템프로그래밍", "백엔드개발자", "개발자채용"],
        "node": ["Nodejs", "NestJS", "백엔드개발자", "자바스크립트", "개발자채용"],
        "python": ["파이썬", "Python", "개발자채용", "데이터엔지니어", "AI개발자"],
        "lang": ["프로그래밍언어", "TIOBE", "Python", "Java", "개발자채용"],
        "agent": ["AI에이전트", "MCP", "RAG", "LLM", "개발자채용"],
        "vc": ["벤처투자", "스타트업", "AI개발자", "스타트업채용", "개발자채용"],
        "spring": ["스프링", "SpringBoot", "자바", "백엔드개발자", "개발자채용"],
        "robot": ["로봇", "휴머노이드", "ROS", "로보틱스", "개발자채용"],
        "wish": ["신입연봉", "초봉", "희망연봉", "신입개발자", "개발자연봉"],
        "cloud": ["AWS", "클라우드엔지니어", "Azure", "GCP", "개발자채용"],
        "gap": ["신입개발자", "경력직", "개발자취업", "이직준비", "개발자채용"],
        "usvs": ["개발자채용", "AI개발자", "시니어개발자", "채용트렌드", "IT채용"],
        "junior": ["주니어개발자", "신입개발자", "개발자취업", "취업준비", "개발자채용"],
        "health": ["헬스케어", "의료AI", "루닛", "디지털헬스", "개발자채용"],
        "pangyo": ["판교", "판교테크노밸리", "판교개발자", "IT회사", "개발자채용"],
        "mobility": ["모빌리티", "SDV", "현대자동차", "자율주행", "개발자채용"],
        "aitool": ["AI코딩", "ClaudeCode", "Cursor", "개발자채용", "코딩테스트"],
        "cert": ["자격증", "데브옵스", "인프라엔지니어", "AWS자격증", "개발자채용"]}


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


# --- [신입 초봉] · [이런 조건 되는 곳] · [출근길 지도] · [신입 환영] --------------------
# CONTENT_SERIES.md 의 2026-10-01 추가분. 공고 본문(복지·전문)을 봐야 해서 색인이 아니라 공고 전량
# 원본(jobsource.SOURCE)을 읽는다. 기준일은 파일 수정 시각이 아니라 **공고 등록일 중 가장 늦은 날**이다 —
# 파일은 복사·복원만 해도 시각이 바뀌어 '오늘 수집' 처럼 잘못 찍힌다.
def _source() -> list[dict]:
    return json.loads(jobsource.SOURCE.read_text(encoding="utf-8"))


def _data_date(rows: list[dict]) -> str:
    dates = [j.get("posted_date") for j in rows if j.get("posted_date")]
    return max(dates) if dates else date.today().isoformat()


def _open_dev(jobs: list[dict]) -> list[dict]:
    today = date.today()
    return [j for j in jobs if j.get("status") == "active" and not _not_dev(j)
            and not ((d := _deadline(j, today)) and d < today)]


def _text(j: dict) -> str:
    return "\n".join(j.get(k) or "" for k in ("benefits", "full_jd", "preferences", "qualifications"))


def _co(name: str) -> str:
    return re.sub(r"\(.*?\)|㈜|주식회사|\s+$", "", name or "").strip()


NO_CO = "회사명 없음"


def _company(j: dict) -> str:
    """회사 칸이 빈 공고는 제목의 [브랜드] 를 쓴다('[취팡] 프로덕트…'). '[부산/사상구]' 같은 근무지 머리는 회사가 아니다."""
    if co := _co(j.get("company") or ""):
        return co
    t = j.get("title") or ""
    if m := re.match(r"\s*(?:\(주\)|㈜)\s*([^\s\[\]()]{2,20})", t):
        return m[1]
    m = re.match(r"\s*\[([^\]]+)\]", t)
    if m and not re.search(r"/|(시|구|군|동|역)$|서울|경기|부산|대구|인천|광주|대전|울산|세종|재택|원격", m[1]):
        return m[1]
    return NO_CO


def _snip(s: str, n: int) -> str:
    """한 줄 칸에 넣을 원문 — 앞의 글머리표를 떼고, 넘치면 낱말 경계에서 자른다."""
    s = re.sub(r"^[\s\-–•·ㆍ‧∙・■□▶▷○●◦※*>]+", "", re.sub(r"\s+", " ", s or "")).strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut if len(cut) > n * .6 else s[:n]).rstrip(" ,(·/-–") + "…"


def _title(j: dict) -> str:
    """제목에서 회사 이름 머리('[인라이플] …', '(주)유니언스 …')를 뗀다 — 회사 칸에 이미 있다."""
    t = re.sub(r"^\s*\[[^\]]*\]\s*", "", j.get("title") or "")
    co = _company(j)
    t = re.sub(r"^\s*(\(주\)|㈜|주식회사)?\s*" + re.escape(co) + r"\s*", "", t) if co else t
    return t.strip() or (j.get("title") or "")


def _by_company(js: list[dict], limit: int = 8) -> list[dict]:
    """같은 회사가 여러 공고를 올리면 한 줄로 — '넛지헬스케어 · 6건' 처럼."""
    groups: dict[str, list[dict]] = {}
    for j in js:
        groups.setdefault(_company(j), []).append(j)
    rows = []
    for co, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:limit]:
        meta = _snip(_title(items[0]), 26) + (f" 외 {len(items) - 1}건" if len(items) > 1 else "")
        rows.append({"role": co[:14], "meta": meta})
    return rows


def _rows(js: list[dict], limit: int = 8) -> list[dict]:
    """회사가 셋 이상이면 회사별 한 줄, 적으면 공고별 한 줄(한 회사만 덩그러니 남지 않게)."""
    if len({_company(j) for j in js}) >= 3:
        return _by_company(js, limit)
    seen, rows = set(), []
    for j in js:
        t = _snip(_title(j), 30)
        if (_company(j), t) not in seen:
            seen.add((_company(j), t))
            rows.append({"role": _company(j)[:14], "meta": t})
    return rows[:limit]


def _companies(js: list[dict], limit: int = 8) -> str:
    seen: list[str] = []
    for j in js:
        c = _company(j)
        if c not in seen:
            seen.append(c)
    return ", ".join(seen[:limit]) + (f" 외 {len(seen) - limit}곳" if len(seen) > limit else "")


def _parse_pay():
    """연봉 문구 해석은 agent-mcp 의 salary_benchmark 와 같은 함수를 쓴다(두 벌이면 숫자가 갈린다)."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from servers.agent_mcp.data import parse_pay
    return parse_pay


_MAN = lambda v: f"{v:,}만"  # noqa: E731


def build_pay_newgrad() -> dict:
    """[신입 초봉] 신입 연봉을 숫자로 적어 둔 공고 — 수집 기간 전체.

    신입 연봉으로 볼 수 있는 것만 센다: 연봉 문구에 '신입' 이 있거나 경력 칸이 '신입'(무관) 하나뿐인 공고.
    '신입·경력' 공고의 연봉은 경력자 값일 수 있어 뺀다. 달러 등 외화로 적은 해외 공고도 뺀다.
    """
    parse = _parse_pay()
    allj = _source()
    asof = _data_date(allj)
    found: list[tuple[dict, dict, int]] = []
    newgrad_jobs = 0
    for j in allj:
        if "신입" not in (j.get("career") or "") or _not_dev(j):
            continue
        newgrad_jobs += 1
        p = parse("\n".join(j.get(k) or "" for k in ("benefits", "full_jd")))
        if not p or re.search(r"\$|USD|달러|환율", p["text"]):
            continue
        if "신입" not in p["text"] and not re.fullmatch(r"\s*신입(/무관)?\s*", j.get("career") or ""):
            continue
        mid = (p["low"] + p["high"]) // 2 if p.get("high") else p["low"]
        found.append((j, p, mid))
    # 같은 회사의 같은 공고가 사이트마다 올라온다 — 회사·금액이 같으면 한 번만.
    uniq: dict[tuple, tuple] = {}
    # 회사를 알 수 없는 사본(회사 칸이 빈 사이트)은 뺀다 — 같은 공고가 회사 이름을 달고 따로 있다.
    for j, p, mid in found:
        if _company(j) != NO_CO:
            uniq.setdefault((_company(j), mid), (j, p, mid))
    rows = list(uniq.values())
    n = len(rows)
    mids = sorted(m for _, _, m in rows)
    med = mids[n // 2]
    p90 = mids[int(n * .9)]
    bands = [("3,000 미만", 0, 3000), ("3,000–3,499", 3000, 3500), ("3,500–3,999", 3500, 4000),
             ("4,000–4,499", 4000, 4500), ("4,500–4,999", 4500, 5000), ("5,000 이상", 5000, 10**6)]
    cnt = [(lab, sum(1 for m in mids if lo <= m < hi)) for lab, lo, hi in bands]
    open_now = [(j, p, m) for j, p, m in rows if j.get("status") == "active"]
    top = sorted(rows, key=lambda r: -r[2])[:6]
    note = (f"신입 가능 개발 공고 {newgrad_jobs:,}건 중 신입 연봉을 숫자로 적은 {n}곳(회사·금액 중복 제외) · "
            f"수집 기간 전체 · 최신 공고 {_dot(asof)} · 범위는 가운데 값, '이상' 은 하한")
    slides = [
        {"type": "cover", "big": f"{med:,}", "big_unit": "만원",
         "lines": ["신입 연봉,", "**숫자로 적은 곳**만 모았다"],
         "sub": f"공고에 신입 연봉을 적은 {n}곳의 가운데 값", "note": note},
        {"type": "bars", "title": "신입 연봉 구간", "sub": f"{n}곳 · 만원",
         "rows": [{"label": lab, "value": c, "display": f"{c}", "unit": f"{round(100 * c / n)}%",
                   "hi": lab.startswith("3,500")} for lab, c in cnt if c], "note": note},
        {"type": "stat", "title": "숫자를 적은 곳은 이만큼", "num": f"{round(100 * len(found) / newgrad_jobs, 1)}",
         "unit": "%", "label": f"신입 가능 공고 {newgrad_jobs:,}건 중 신입 연봉을 숫자로 적은 공고",
         "explain": "대부분은 '회사 내규에 따름'이다. 그래서 이 값은 **적어 둔 곳들의 값**이지 시장 전체가 아니다. "
                    f"상위 10% 는 **{p90:,}만 원 이상**.", "note": note},
        {"type": "jobs", "title": "높게 적은 곳", "sub": "공고 원문의 신입 연봉(지난 공고 포함)",
         "rows": [{"role": _company(j)[:14], "meta": _snip(p["text"], 32)} for j, p, _ in top], "note": note},
    ]
    if open_now:
        slides.append({"type": "jobs", "title": "지금 모집중이면서 적어 둔 곳", "sub": f"{len(open_now)}곳",
                       "rows": [{"role": f"{_company(j)[:12]} · {_snip(_title(j), 18)}", "meta": _MAN(m)}
                                for j, p, m in sorted(open_now, key=lambda r: -r[2])[:7]], "note": note})
    slides.append({"type": "end", "title": "읽는 법", "lines": [
        "① 큰 회사일수록 숫자를 안 적는다 — 이 표에 없다고 낮은 게 아니다",
        "② '이상'·'협의' 는 출발점이다. 면접에서 근거를 들고 이야기하자",
        "③ 회사 평균연봉(공시)은 전 직군·전 연차 평균이라 **초봉이 아니다**",
        SEND], "note": note})
    caption = "\n\n".join([
        f"[신입 초봉] 신입 연봉을 숫자로 적어 둔 곳 {n}곳 — 가운데 값 {med:,}만 원",
        "우리가 모은 개발 공고에서 신입 연봉을 숫자로 적은 곳만 셌습니다(수집 기간 전체, 지난 공고 포함).",
        "구간: " + " · ".join(f"{lab} {c}곳" for lab, c in cnt if c),
        f"상위 10% 는 {p90:,}만 원 이상. 다만 신입 연봉을 적는 공고 자체가 {round(100 * len(found) / newgrad_jobs, 1)}% 뿐이고, "
        "큰 회사일수록 적지 않습니다 — '적어 둔 곳들의 값' 으로 읽어 주세요.",
        "세는 법: 연봉 문구에 '신입' 이 있거나 경력 칸이 '신입' 하나인 공고만. '신입·경력' 공고와 외화로 적은 해외 공고는 뺐습니다. "
        f"범위는 가운데 값, '이상' 은 하한. 최신 공고 {_dot(asof)} 기준.",
    ])
    return {"kind": "pay", "id": f"pay-newgrad-{asof.replace('-', '')}", "title": "신입 초봉",
            "slides": slides, "caption": caption,
            "jobs": [{"key": f"{j['site']}-{j['pid']}", "company": j["company"], "role": j["title"]}
                     for j, _, _ in open_now]}


PERKS = [  # (이름, 공고 본문에서 찾는 말) — 회사가 공고에 직접 적은 것만 센다
    ("재택·원격", r"(재택|원격\s*근무|리모트|remote)(?!\s*(근무\s*)?(불가|없음|미실시|불가능))"),
    ("스톡옵션", r"스톡\s*옵션|RSU"),
    ("주거·사택 지원", r"사택|기숙사|숙소\s*제공|주거\s*지원|주택\s*자금|전세\s*자금"),
    ("주 4일·4.5일", r"주\s*4\s*일\s*(제|근무)|주\s*4\.5\s*일"),
    ("자율 출퇴근", r"자율\s*출퇴근|유연\s*근무|시차\s*출퇴근"),
]


def build_perks() -> dict:
    """[이런 조건 되는 곳] IT 사람들이 먼저 보는 조건 — 공고에 직접 적은 곳."""
    allj = _source()
    asof = _data_date(allj)
    rows = _open_dev(allj)
    n = len(rows)
    has = {name: [j for j in rows if re.search(pat, _text(j), re.I)] for name, pat in PERKS}
    four = has["주 4일·4.5일"]
    remote_new = [j for j in has["재택·원격"] if "신입" in (j.get("career") or "")]
    note = f"모집중 개발 공고 {n:,}건 · 공고 본문에 그 말을 직접 적은 곳만 · 최신 공고 {_dot(asof)}"
    rare = four[0] if four else None
    slides = [
        {"type": "cover", "big": f"{len(four)}", "big_unit": "건",
         "lines": ["주 4일 적어 둔 공고,", f"개발 공고 {n:,}건 중"],
         "sub": "재택·스톡옵션·주거 지원까지 — 공고에 직접 적은 곳만 셌다", "note": note},
        {"type": "bars", "title": "공고에 적힌 조건", "sub": f"모집중 {n:,}건",
         "rows": [{"label": name, "value": len(v), "display": f"{len(v)}", "unit": f"{round(100 * len(v) / n)}%",
                   "hi": name == "주 4일·4.5일"} for name, v in has.items()], "note": note},
    ]
    if four:
        slides.append({"type": "jobs", "title": "주 4일·4.5일을 적은 곳", "sub": "공고 원문 기준",
                       "rows": _by_company(four),
                       "note": note})
    if remote_new:
        slides.append({"type": "jobs", "title": "재택 되고 신입도 받는 곳", "sub": f"{len(remote_new)}건 중",
                       "rows": _by_company(remote_new),
                       "note": note})
    slides.append({"type": "end", "title": "확인할 것", "lines": [
        "① '재택' 은 주 1회부터 전면까지 — 면접에서 **몇 회인지** 묻자",
        "② 스톡옵션은 행사가·베스팅 기간이 핵심",
        "③ 공고에 안 적어도 있는 회사가 많다 — 이 표는 '적어 둔 곳' 이다",
        SEND], "note": note})
    caption = "\n\n".join([
        f"[이런 조건 되는 곳] 주 4일 적어 둔 공고 {len(four)}건 — 개발 공고 {n:,}건 중",
        "회사가 공고 본문에 직접 적은 조건만 셌습니다: " + " · ".join(f"{name} {len(v)}건" for name, v in has.items()),
        (f"주 4일·4.5일: {_companies(four)}") if four else "",
        f"모집중 개발 공고 기준, 최신 공고 {_dot(asof)}. 공고에 안 적었다고 없는 건 아닙니다 — 면접에서 꼭 물어보세요.",
    ])
    caption = "\n\n".join(p for p in caption.split("\n\n") if p)
    return {"kind": "perk", "id": f"perks-{asof.replace('-', '')}", "title": "이런 조건 되는 곳",
            "slides": slides, "caption": caption,
            "jobs": [{"key": f"{j['site']}-{j['pid']}", "company": j["company"], "role": j["title"]}
                     for j in four[:8]]}


AREAS = [  # (권역, 근무지 표기에서 찾는 말, 대표 역)
    ("강남·역삼·선릉", r"강남|역삼|선릉|삼성동|테헤란", "강남·선릉역"),
    ("을지로·종로", r"을지로|중구|종로|광화문", "을지로입구·광화문역"),
    ("여의도·영등포", r"여의도|영등포", "여의도역"),
    ("판교·분당", r"판교|분당", "판교역"),
    ("구로·가산", r"구로|가산", "가산디지털단지역"),
    ("성수", r"성수|성동", "성수역"),
    ("마포·상암", r"마포|홍대|상암", "디지털미디어시티역"),
]


def build_commute(a: str = "판교·분당", b: str = "성수") -> dict:
    """[출근길 지도] 권역별 IT 공고 + 두 권역 밸런스 게임(댓글 투표)."""
    allj = _source()
    asof = _data_date(allj)
    rows = _open_dev(allj)
    n = len(rows)
    by = {name: [j for j in rows if re.search(pat, j.get("location") or "")] for name, pat, _ in AREAS}
    station = {name: st for name, _, st in AREAS}
    note = f"모집중 개발 공고 {n:,}건 · 근무지 표기로 묶음 · 최신 공고 {_dot(asof)}"

    def profile(name: str) -> list:
        js = by[name]
        cos = collections.Counter(_company(j) for j in js).most_common(3)
        st = collections.Counter(s for j in js for s in set(j.get("tech_stack") or [])).most_common(2)
        newg = sum(1 for j in js if "신입" in (j.get("career") or ""))
        # 표 칸은 좁아서 1위 회사만, 캡션에는 셋을 쓴다.
        return [f"{len(js)}건", cos[0][0][:8] if cos else "-", " · ".join(s for s, _ in st) or "-",
                f"{round(100 * newg / len(js)) if js else 0}%", " · ".join(c for c, _ in cos) or "-"]
    pa, pb = profile(a), profile(b)
    slides = [
        {"type": "cover", "lines": [f"**{a.split('·')[0]}** vs **{b.split('·')[0]}**", "어디로 출근할래?"],
         "sub": "개발 공고가 모인 곳을 근무지로 세 봤다", "note": note},
        {"type": "bars", "title": "개발 공고가 모인 곳", "sub": f"모집중 {n:,}건 · 서울·판교",
         "rows": [{"label": name, "value": len(v), "display": f"{len(v)}", "unit": "건",
                   "hi": name in (a, b)} for name, v in sorted(by.items(), key=lambda kv: -len(kv[1]))],
         "note": note},
        {"type": "table", "title": f"{a.split('·')[0]} vs {b.split('·')[0]}", "sub": "모집중 개발 공고로 비교",
         "head": ["", a.split("·")[0], b.split("·")[0]],
         "rows": [["공고 수", pa[0], pb[0]], ["가장 많이 뽑는 곳", pa[1], pb[1]],
                  ["많이 찾는 기술", pa[2], pb[2]], ["신입 가능", pa[3], pb[3]]], "note": note},
    ]
    for name in (a, b):
        js = by[name]
        if js:
            cos = collections.Counter(_company(j) for j in js).most_common(7)
            slides.append({"type": "jobs", "title": f"{name}에서 뽑는 곳", "sub": station[name],
                           "rows": [{"role": c[:16], "meta": f"공고 {k}건"} for c, k in cos], "note": note})
    slides.append({"type": "end", "title": "댓글로 골라 주세요", "lines": [
        f"🅰 {a.split('·')[0]} — 공고 {pa[0]}", f"🅱 {b.split('·')[0]} — 공고 {pb[0]}",
        "같이 고민하는 친구를 태그하고", SEND], "note": note})
    caption = "\n\n".join([
        f"[출근길 지도] {a.split('·')[0]} vs {b.split('·')[0]} — 어디로 출근할래요?",
        "모집중 개발 공고를 근무지로 묶었습니다: " + " · ".join(f"{name} {len(v)}" for name, v in
                                                     sorted(by.items(), key=lambda kv: -len(kv[1]))),
        f"{a}: 공고 {pa[0]} · 많이 뽑는 곳 {pa[4]} · 신입 가능 {pa[3]}",
        f"{b}: 공고 {pb[0]} · 많이 뽑는 곳 {pb[4]} · 신입 가능 {pb[3]}",
        f"근무지 표기 기준이라 '서울' 처럼 구를 안 적은 공고는 빠졌습니다. 최신 공고 {_dot(asof)}. 댓글로 🅰/🅱 골라 주세요!",
    ])
    return {"kind": "map", "id": f"commute-{asof.replace('-', '')}", "title": f"{a} vs {b}",
            "slides": slides, "caption": caption, "jobs": []}


WELCOME = [  # (묶음, 찾는 말) — 회사가 신입을 '받는다' 가 아니라 '원한다' 고 쓴 곳
    ("인턴 → 정규직 전환", r"전환형\s*인턴|인턴\s*(후|이후)?\s*(정규직\s*)?전환|채용\s*연계형"),
    ("졸업예정자 지원 가능", r"졸업\s*예정자|기졸업자\s*및\s*졸업"),
    ("신입 우대·환영", r"신입\s*(우대|환영)|주니어\s*환영"),
]

WELCOME_SHORT = {"인턴 → 정규직 전환": "전환형 인턴", "졸업예정자 지원 가능": "졸업예정자", "신입 우대·환영": "신입 우대"}


def build_welcome() -> dict:
    """[신입 환영] 신입을 '받는다' 가 아니라 '원한다' 고 공고에 적은 곳."""
    allj = _source()
    asof = _data_date(allj)
    rows = _open_dev(allj)
    groups = {name: [j for j in rows if re.search(pat, (j.get("title") or "") + "\n" + _text(j))]
              for name, pat in WELCOME}
    total = {f"{j['site']}-{j['pid']}" for v in groups.values() for j in v}
    newgrad = sum(1 for j in rows if "신입" in (j.get("career") or ""))
    note = f"모집중 개발 공고 {len(rows):,}건 · 제목·본문에 그 말을 직접 적은 곳 · 최신 공고 {_dot(asof)}"
    slides = [
        {"type": "cover", "big": f"{len(total)}", "big_unit": "건",
         "lines": ["신입을 **원한다** 고", "적어 둔 공고"],
         "sub": f"'신입 가능'({newgrad}건) 중에서도 전환형 인턴·졸업예정자·신입 우대를 직접 쓴 곳", "note": note},
        {"type": "bars", "title": "어떻게 환영하나", "sub": "공고에 적은 말로 묶음(겹칠 수 있음)",
         # 막대 이름 칸은 좁다 — 묶음 이름의 앞말만('인턴 → 정규직 전환' → '전환형 인턴').
         "rows": [{"label": WELCOME_SHORT.get(name, name), "value": len(v), "display": f"{len(v)}", "hi": i == 0}
                  for i, (name, v) in enumerate(groups.items())], "note": note},
    ]
    for name, v in groups.items():
        if v:
            slides.append({"type": "jobs", "title": name, "sub": f"{len(v)}건 중",
                           "rows": _rows(v), "note": note})
    slides.append({"type": "end", "title": "넣기 전에", "lines": [
        "① 전환형 인턴은 **전환율·기간**을 꼭 확인",
        "② 졸업예정자는 입사 가능 시점이 조건이다",
        "③ '신입 우대' 는 경력자와 같이 본다는 뜻일 수도 — 자격요건을 읽자",
        SEND], "note": note})
    caption = "\n\n".join([
        f"[신입 환영] 신입을 원한다고 적은 공고 {len(total)}건 — {len({_company(j) for v in groups.values() for j in v})}개 회사",
        "'신입 가능' 보다 한 걸음 더 — 전환형 인턴·졸업예정자·신입 우대를 공고에 직접 쓴 곳만 모았습니다.",
        "\n".join(f"· {name} {len(v)}건: {_companies(v, 6)}" for name, v in groups.items() if v),
        f"모집중 개발 공고 기준, 최신 공고 {_dot(asof)}. 자세한 조건은 공고 원문에서 확인하세요.",
    ])
    return {"kind": "welcome", "id": f"welcome-{asof.replace('-', '')}", "title": "신입 환영",
            "slides": slides, "caption": caption,
            "jobs": [{"key": f"{j['site']}-{j['pid']}", "company": j["company"], "role": j["title"]}
                     for j in {f"{j['site']}-{j['pid']}": j for v in groups.values() for j in v}.values()]}


# 바깥 숫자 — 공고로 셀 수 없는 것은 조사 기관의 공개 발표를 그대로 옮긴다(출처는 캡션에).
GONGCHAE_SRC = [
    ("경총 「2025 신규채용 실태조사」(100인 이상 500개사)", "https://www.mt.co.kr/industry/2025/03/20/2025032008550919932"),
    ("고용노동부 「2023 하반기 기업 채용동향조사」(500대 기업 315곳)", "https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=16352"),
    ("국민일보 — 대기업 신입 중 중고신입 28.1%(500대 기업 121곳, 2025)", "https://www.kmib.co.kr/article/view.asp?arcid=0019940870"),
    ("그리팅 — 현대차·LG 2019 공채 폐지, SK 2022 전원 수시", "https://blog.greetinghr.com/company-occasional-recruit-trend/"),
    ("아시아경제 — 4대 그룹 중 정기 공채는 삼성뿐(2026 하반기)", "https://view.asiae.co.kr/article/2026090712525576714"),
]

ASKS = [  # (이름, 공고에서 찾는 말) — 신입 가능 공고가 전형·자격에 적은 것
    ("포트폴리오", r"포트폴리오|portfolio"),
    ("코딩테스트", r"코딩\s*테스트|코테|알고리즘\s*테스트"),
    ("프로젝트 경험", r"프로젝트\s*(경험|수행)"),
    ("과제 전형", r"과제\s*(전형|테스트)|사전\s*과제|take[- ]?home"),
    ("인적성·필기", r"인적성|적성\s*검사|필기\s*(시험|전형)"),
    ("토익·어학", r"토익|TOEIC|어학\s*(성적|점수)|오픽|OPIc"),
]


def build_gongchae() -> dict:
    """[공채는 끝났다] 예전 공채와 지금 채용 — 무엇이 바뀌었고 그래서 무엇을 하나.

    바깥 숫자(수시 비중·평가 요소·중고신입)는 조사 발표를 옮기고, '지금 공고가 무엇을 요구하나' 는
    우리 모집중 개발 공고로 센다.
    """
    allj = _source()
    asof = _data_date(allj)
    rows = _open_dev(allj)
    n = len(rows)
    only = sum(1 for j in rows if re.fullmatch(r"\s*신입(/무관)?\s*", j.get("career") or ""))
    newg = [j for j in rows if "신입" in (j.get("career") or "")]
    ng = len(newg)
    asks = [(name, sum(1 for j in newg if re.search(pat, _text(j) + (j.get("title") or ""), re.I)))
            for name, pat in ASKS]
    note = f"바깥 숫자: 경총 2025·고용노동부·500대 기업 조사(출처는 캡션) · 공고: 모집중 개발 {n:,}건, 최신 {_dot(asof)}"
    slides = [
        {"type": "cover", "big": "70.8", "big_unit": "%",
         "lines": ["공채는 끝났다,", "**지금은 수시**다"],
         "sub": "신규채용을 '수시로만' 하는 기업 비율(경총 2025) — 예전 공식으로 준비하면 늦는다", "note": note},
        {"type": "table", "title": "예전 공채 vs 지금", "sub": "무엇이 바뀌었나", "head": ["", "예전", "지금"],
         "rows": [["뽑는 때", "상·하반기", "자리 날 때"], ["뽑는 곳", "그룹 인사팀", "현업 팀"],
                  ["보는 것", "학점·토익", "직무 경험"], ["시험", "인적성", "코테·과제"],
                  ["경쟁자", "동기 졸업생", "중고신입"]], "hi_col": 2, "note": note},
        {"type": "bars", "title": "신규채용을 어떻게 하나", "sub": "경총 2025 · 100인 이상 기업 500곳",
         "rows": [{"label": "수시채용만", "value": 70.8, "display": "70.8", "unit": "%", "hi": True},
                  {"label": "공채 + 수시", "value": 22.6, "display": "22.6", "unit": "%"},
                  {"label": "정기공채만", "value": 6.6, "display": "6.6", "unit": "%"}], "note": note},
        {"type": "bars", "title": "가장 중요한 건 직무 경험", "sub": "채용 평가 1순위로 '직무 관련 업무 경험' 을 꼽은 비율(경총)",
         "rows": [{"label": "2023", "value": 58.4, "display": "58.4", "unit": "%"},
                  {"label": "2024", "value": 74.6, "display": "74.6", "unit": "%"},
                  {"label": "2025", "value": 81.6, "display": "81.6", "unit": "%", "hi": True}], "note": note},
        {"type": "stat", "title": "신입의 경쟁자는 신입이 아니다", "num": "28.1", "unit": "%",
         "label": "대기업 신입사원 중 경력이 있는 '중고신입'(500대 기업 121곳, 2025)",
         "explain": "같은 신입 자리에 **1~2년 일해 본 사람**이 같이 넣는다. 그래서 신입도 '해 본 것' 을 보여 줘야 한다.",
         "note": note},
        {"type": "bars", "title": "우리가 모은 개발 공고로 보면", "sub": f"모집중 {n:,}건 · 경력 칸 기준",
         "rows": [{"label": "경력만", "value": n - ng, "display": f"{n - ng:,}", "unit": f"{round(100 * (n - ng) / n)}%"},
                  {"label": "신입·경력", "value": ng - only, "display": f"{ng - only}",
                   "unit": f"{round(100 * (ng - only) / n)}%", "hi": True},
                  {"label": "신입만", "value": only, "display": f"{only}", "unit": f"{round(100 * only / n)}%", "hi": True}],
         "note": note},
        {"type": "bars", "title": "신입 가능 공고가 적은 것", "sub": f"{ng}건 중 · 공고 본문에 그 말이 있는 수",
         "rows": [{"label": name, "value": c, "display": f"{c}", "unit": f"{round(100 * c / ng)}%",
                   "hi": name in ("포트폴리오", "코딩테스트")} for name, c in asks], "note": note},
        {"type": "end", "title": "그래서 이렇게 ①", "lines": [
            "① 공채 달력 대신 **공고 알림** — 수시는 자리 나면 열고 차면 닫는다. 가고 싶은 회사 10곳에 알림을 건다",
            "② 스펙 한 줄보다 **결과물 하나** — 배포한 서비스, README, 막혔다 푼 기록",
            "③ **직무 경험을 만든다** — 기업이 바라는 1순위는 3~6개월 장기 인턴(74%), 2위는 기업 프로젝트(69%)",
            "④ **코딩테스트·과제** 둘 다 — 신입 가능 공고 다섯에 하나는 코테, 일곱에 하나는 과제를 적는다",
        ], "note": note},
        {"type": "end", "title": "그래서 이렇게 ②", "lines": [
            f"⑤ **'신입·경력' 공고도 넣는다** — 신입만 받는 공고는 {only}건, 신입도 받는 공고는 {ng}건",
            "⑥ 지원서는 **공고 문장으로** 다시 — 현업 팀이 읽는다. 그 팀이 적은 기술·문제에 내 경험을 붙인다",
            "⑦ **작은 회사 1~2년도 길이다** — 돌아가는 게 아니라 경험을 사는 것",
            "⑧ 공채가 남은 곳(삼성 등)은 **일정을 따로** 챙긴다",
            SEND], "note": note},
    ]
    caption = "\n\n".join([
        "[공채는 끝났다] 예전 공채 공식으로 준비하면 늦습니다",
        "· 신규채용을 '수시로만' 하는 기업 70.8%, 정기공채만 하는 곳 6.6%(경총 2025, 100인 이상 500개사)\n"
        "· 현대차·LG 2019년 공채 폐지, SK 2022년부터 전원 수시 — 4대 그룹 중 정기 공채는 삼성뿐\n"
        "· 채용 평가 1순위 '직무 관련 업무 경험' 58.4%(2023) → 74.6%(2024) → 81.6%(2025)\n"
        "· 대기업 신입사원 중 경력이 있는 '중고신입' 28.1%",
        f"우리가 모은 모집중 개발 공고 {n:,}건 중 신입을 받는 공고는 {ng}건({round(100 * ng / n)}%), "
        f"신입만 받는 공고는 {only}건. 신입 가능 공고가 적은 것: "
        + " · ".join(f"{name} {c}건" for name, c in asks) + ".",
        "그래서 —\n① 공채 달력 대신 공고 알림\n② 스펙보다 결과물(배포·README·문제 해결 기록)\n"
        "③ 장기 인턴·기업 프로젝트로 직무 경험 만들기\n④ 코딩테스트와 과제 둘 다\n⑤ '신입·경력' 공고도 지원\n"
        "⑥ 지원서는 공고 문장으로 다시\n⑦ 작은 회사 1~2년도 길\n⑧ 공채 남은 곳은 일정 따로",
        "출처\n" + "\n".join(f"· {t}" for t, _ in GONGCHAE_SRC) + f"\n· 공고 숫자는 최신 공고 {_dot(asof)} 기준",
    ])
    # 릴스는 12초 예고만 — 9장을 2.6초씩 넘기면 24초짜리 글 읽기가 된다. 여덟 가지는 캡션에 두고 저장을 부른다
    # (playbook '정보가 길다': 영상은 예고, 본문은 캡션 체크리스트 — 보내기·저장이 신호)
    teaser = [slides[0], slides[1], slides[4], slides[5],
              {"type": "end", "title": "그래서 뭘 하나 — 8가지", "lines": [
                  "공채 달력 대신 **공고 알림** · 스펙보다 **결과물 하나**",
                  "**'신입·경력' 공고도** 넣는다 · 지원서는 **공고 문장으로**",
                  "나머지까지 **8가지는 캡션에** — 저장해 두세요",
                  SEND], "note": note}]
    return {"kind": "gongchae", "id": f"gongchae-{asof.replace('-', '')}", "title": "공채는 끝났다",
            "slides": slides, "caption": caption, "jobs": [],
            "reel_slides": teaser, "reel_hold": 2.3, "motion": 0.03, "audio": str(LAB_DIR / "assets" / "audio" / "bed_calm.wav"),
            "reel_lead": "준비하는 8가지는 캡션에 정리했어요 — 저장해 두고 꺼내 보세요 📌"}


#: 경력 칸이 '신입부터 N년까지' 범위인 공고 — 원티드식 표기('신입-경력 9년', '신입 이상')
CONTRA_RANGE = re.compile(r"^\s*신입\s*([-–~]\s*경력|이상)")
#: 자격요건 한 줄에 'N년 이상' 경력·경험 — '신입 / 경력 2년 이상' 처럼 두 갈래를 나눠 적은 줄은 뺀다
CONTRA_REQ = re.compile(r"^[^\n]*((경력|경험)[^\n]{0,40}?\d+\s*년\s*이상|\d+\s*년\s*이상[^\n]{0,40}(경력|경험))[^\n]*", re.M)


def _contra_short(q: str) -> str:
    """자격요건 한 줄 → 화면 한 줄. 끝의 '있으신 분' 만 떼고 원문 그대로, 'N년 이상' 이 든 마디까지."""
    q = re.sub(r"\s*(이\s*)?(있으신|이신|인|을\s*보유한|보유한)\s*분\.?$", "", q.strip(" •-ㆍ·\t."))
    part = next((c for c in re.split(r",\s*", q) if re.search(r"\d+\s*년\s*이상", c)), q)
    return _snip(part, 34)


def build_contra() -> dict:
    """[공고 원문] 경력 칸엔 '신입', 자격요건엔 'N년 이상' — 모집중 개발 공고에서 실제로 찾은 문장.

    판단할 대상을 화면에 두고(playbook '댓글을 받고 싶다') 고르게 한다. 우리 해석('혹은 그에 준하는')은
    정답처럼 캡션에서 공개한다. 회사 이름은 가린다 — 망신 주기가 아니라 읽는 법을 말하는 편이다.
    """
    allj = _source()
    asof = _data_date(allj)
    rows = _open_dev(allj)
    newg = [j for j in rows if "신입" in (j.get("career") or "")]
    rng = [j for j in newg if CONTRA_RANGE.search(j["career"])]
    hits = []
    for j in rng:
        ms = [m.group(0) for m in CONTRA_REQ.finditer(j.get("qualifications") or "")
              if not re.match(r"\s*[•\-ㆍ·]?\s*신입", m.group(0))]
        if ms:
            hits.append((j, ms[0].strip(" •-ㆍ·\t")))
    # 표에는 회사마다 한 줄 — '그에 준하는' 이 붙은 줄은 캡션의 정답이라 표에서 아낀다
    seen, table = set(), []
    for j, q in sorted(hits, key=lambda h: "준하는" in h[1]):
        co = _company(j)
        if co in seen:
            continue
        seen.add(co)
        table.append((j, q))
    table = table[:3]
    equiv = next((q for _, q in hits if "준하는" in q), "")
    n_co = len({_company(j) for j, _ in hits})
    note = f"모집중 개발 공고 {len(rows):,}건(최신 {_dot(asof)}) · 원문 그대로 · 회사 이름은 가렸습니다"
    slides = [
        {"type": "cover", "lines": ["경력 칸엔 **신입**,", "자격요건엔 **N년 이상**"],
         "sub": "지금 모집중인 개발 공고에서 실제로 찾은 문장", "note": note},
        {"type": "end", "title": "실제 공고 원문", "lines": [
            f"{'ABC'[i]}사 · 경력 칸 「{j['career'].replace('-', '–')}」\n→ 자격요건 「**{_contra_short(q)}**」"
            for i, (j, q) in enumerate(table)], "note": note},
        {"type": "bars", "title": "이런 공고, 몇 건?", "sub": "모집중 개발 공고 · 경력 칸과 자격요건 기준",
         "rows": [{"label": "신입 가능", "value": len(newg), "display": f"{len(newg)}", "unit": "건"},
                  {"label": "신입–N년", "value": len(rng), "display": f"{len(rng)}", "unit": "건"},
                  {"label": "+ N년 이상", "value": len(hits), "display": f"{len(hits)}", "unit": f"건 · {n_co}곳", "hi": True}],
         "note": note},
        {"type": "end", "title": "신입이라면 넣는다?", "lines": [
            "**A 넣는다** — 경력 칸에 '신입'",
            "**B 안 넣는다** — 자격요건에 'N년 이상'",
            "댓글로 **A? B?** 👇 정답은 캡션에",
            f"모든 공고가 이렇다는 게 아닙니다 · {len(rng)}건 중 {len(hits)}건"], "note": note},
    ]
    caption = "\n\n".join([
        "경력 칸엔 '신입', 자격요건엔 'N년 이상' — 신입이라면 넣는다(A)? 안 넣는다(B)? 댓글로 👇",
        "실제 원문(모집중 개발 공고, 회사 이름은 가림)\n" + "\n".join(
            f"· 경력 칸 '{j['career']}' / 자격요건 \"{q}\"" for j, q in table),
        f"이런 공고는 많지 않아요. 신입을 받는 모집중 개발 공고 {len(newg)}건 중 경력 칸이 '신입–N년' 범위인 게 {len(rng)}건, "
        f"그중 자격요건에 'N년 이상' 을 적은 건 {len(hits)}건({n_co}곳)이었습니다.",
        "정답(이 계정의 읽는 법): A 쪽에 가깝습니다. 경력 칸의 범위는 '이 범위면 지원 가능' 이라는 뜻일 때가 많고, "
        + (f"같은 갈래의 다른 공고에는 \"{equiv}\" 라고 적은 곳도 있어요 — '그에 준하는 역량' 을 보여 줄 결과물이 있으면 넣어 볼 만합니다. "
           if equiv else "")
        + "다만 'N년 이상' 이 필수 칸에 있으면 서류에서 그 기간만큼의 일을 해 봤다는 근거(프로젝트·운영 경험)를 먼저 찾는다는 뜻이니, "
          "지원서 첫 줄을 거기에 맞추세요.",
        "이런 공고 본 적 있으면 원문 한 줄 댓글로 공유해 주세요 · 취준 중인 친구에게 보내 주세요",
        f"세는 법: 우리가 모은 모집중 개발 공고 {len(rows):,}건(최신 {_dot(asof)}) 중 경력 칸에 '신입' 이 있는 공고에서, 자격요건(우대사항 제외)에 "
        "'경력·경험 N년 이상' 이 있는 줄을 찾았습니다. '신입 / 경력 2년 이상' 처럼 두 갈래를 나눠 적은 줄은 뺐습니다.",
    ])
    return {"kind": "contra", "id": f"contra-newgrad-{asof.replace('-', '')}", "title": "경력 칸엔 신입, 자격요건엔 N년",
            "slides": slides, "caption": caption, "jobs": [],
            "reel_hold": [2.2, 3.6, 2.6, 4.0], "motion": 0.0, "audio": str(LAB_DIR / "assets" / "audio" / "bed_calm.wav")}


# --- 사진이 들어가는 시리즈 — 원고는 content/*.json (출처·사진 저작자까지 거기에) ---------------
CONTENT = LAB_DIR / "content"
PHOTOS = LAB_DIR / "assets" / "photos"


def _photo(sub: str, name: str) -> tuple[str, str]:
    """사진 → (data URI, 출처 한 줄). 출처는 Commons API 로 확인해 둔 credits.json 에서 — 판마다 적는다."""
    import base64
    p = PHOTOS / sub / name
    credits = json.loads((PHOTOS / sub / "credits.json").read_text(encoding="utf-8"))
    c = credits[name.replace("_", " ")]
    uri = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
    return uri, f"{c['artist']} · {c['license']} · Wikimedia Commons"


def build_lunch(area: str = "pangyo") -> dict:
    """[점심 지도] IT 회사가 모인 동네의 점심 — 블로그·기사에 여러 번 나온 곳.

    가게 사진은 쓰지 않는다(사용권이 없다). 대표 메뉴 종류의 Commons 사진을 '메뉴 예시' 로 깔고
    판마다 '이 가게 사진 아님' 과 작가·라이선스를 적는다. 끝 장은 그 동네의 개발 공고로 잇는다.
    """
    doc = json.loads((CONTENT / f"lunch-{area}.json").read_text(encoding="utf-8"))
    src = doc["sources"]
    rows = _open_dev(_source())
    pg = [j for j in rows if re.search(r"판교|분당|삼평|백현", j.get("location") or "")]
    cos = collections.Counter(_company(j) for j in pg).most_common(4)
    places = doc["places"]
    first_uri, first_credit = _photo("lunch", places[0]["photo"])
    slides = [{"type": "photo", "image": first_uri, "title": "판교 IT 직장인 점심 10곳",
               "meta": "카카오·엔씨·NHN 근처 · 블로그·기사에 여러 번 나온 순",
               "credit": f"사진: 메뉴 예시({places[0]['dish']}) — {first_credit}"}]
    for i, pl in enumerate(places, 1):
        uri, credit = _photo("lunch", pl["photo"])
        years = sorted({src[k][1][:4] for k in pl["src"]})
        slides.append({"type": "photo", "image": uri, "rank": f"{i:02d} · {pl['where']}", "title": pl["name"],
                       "meta": pl["menu"] + (f" · {pl['price']}" if pl["price"] else ""),
                       "lines": [f"가까운 곳: {pl['near']}", f"나온 곳: 블로그·기사 {len(pl['src'])}곳({'·'.join(years)})"],
                       "credit": f"사진: 메뉴 예시({pl['dish']}) — 이 가게 사진 아님 · {credit}"})
    slides.append({"type": "end", "title": "점심 먹고, 지원하기", "lines": [
        f"판교·분당 모집중 개발 공고 **{len(pg)}건** — " + " · ".join(c for c, _ in cos),
        "가기 전에 영업시간·휴무를 꼭 확인 — 가격은 출처 시점 기준",
        "순서는 맛 순위가 아니라 **여러 출처에 나온 순**이다",
        "여기 없는 판교 점심, 댓글로 알려 주세요",
        SEND], "note": f"출처: 블로그·기사 {len(src)}곳(캡션) · 확인 {_dot(doc['checked'])}"})
    caption = "\n\n".join([
        "[점심 지도] 판교 IT 직장인 점심 10곳 — 카카오·엔씨·NHN 근처",
        "\n".join(f"{i:02d} {pl['name']} — {pl['menu']}" + (f" ({pl['price']})" if pl['price'] else "")
                  for i, pl in enumerate(places, 1)),
        "고른 기준: 서로 다른 블로그·기사에 나온 횟수 순, 2024년 이후 출처가 있는 곳만. 미쉐린은 판교를 다루지 않아 "
        "'순위' 가 아니라 '추천' 입니다. 가기 전에 영업시간을 확인하세요.",
        f"판교·분당 모집중 개발 공고 {len(pg)}건 — 많이 뽑는 곳: " + " · ".join(c for c, _ in cos) + ".",
        "사진은 메뉴 예시이고 각 가게 사진이 아닙니다(Wikimedia Commons, 작가·라이선스는 각 장에).",
        "출처\n" + "\n".join(f"· {v[0]} ({v[1]})" for v in src.values()),
    ])
    return {"kind": "lunch", "id": f"lunch-{area}-{doc['checked'].replace('-', '')}", "title": doc["title"],
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "motion": 0.05, "audio": str(LAB_DIR / "assets" / "audio" / "bed_calm.wav"),
            "reel_lead": "가 본 곳 중 최고는? 여기 없는 판교 점심도 댓글로 👇"}


def build_welcomekit() -> dict:
    """[첫 출근 웰컴키트] 입사하면 받는 것 — 회사가 공개한 품목만(연도 표기). 회사 사진은 쓰지 않는다."""
    doc = json.loads((CONTENT / "welcome-kits.json").read_text(encoding="utf-8"))
    kits, ph = doc["kits"], doc["pharma"]
    note = f"품목은 출처 원문에 적힌 것만 · 웰컴키트는 입사 시기마다 바뀐다 · 확인 {_dot(doc['checked'])}"
    slides = [{"type": "cover", "lines": ["입사하면", "**뭘 받을까**"],
               "sub": " · ".join(k["company"] for k in kits) + " — 그리고 제약·바이오는?", "note": note}]
    for k in kits:
        lines = list(k["items"])
        if k.get("quote"):
            lines.append(k["quote"])
        slides.append({"type": "end", "title": f"{k['company']} ({k['year']})", "lines": [f"**{k['hook']}**"] + lines,
                       "note": f"출처: {k['src'][0]} · {k['kind']}"})
    slides.append({"type": "end", "title": "제약·바이오 IT 는?", "lines": [
        "**품목을 공개한 곳이 거의 없다**",
        *[f"{f['company']} — {f['text']}" for f in ph["found"]],
        f"{' · '.join(ph['none'][:4])} 등은 공개 자료를 찾지 못했다",
        "면접 마지막 질문으로 **'입사 첫 주에 무엇을 하나요?'** 를 물어보자"], "note": note})
    slides.append({"type": "end", "title": "키트보다 중요한 것", "lines": [
        "① **온보딩** — 첫 주에 누가 무엇을 알려 주나(토스: 온보딩 세션, GC녹십자EM: 멘토링)",
        "② **장비** — 노트북·모니터 사양은 공고·면접에서 물어봐도 되는 것",
        "③ 계열사마다 다르다 — 카카오스타일 ≠ 카카오, 네이버클라우드 ≠ 네이버",
        SEND], "note": note})
    caption = "\n\n".join([
        "[첫 출근 웰컴키트] 입사하면 뭘 받을까 — " + " · ".join(f"{k['company']}({k['year']})" for k in kits),
        "\n".join(f"· {k['company']}: {k['hook']}" for k in kits),
        "제약·바이오는 품목을 공개한 곳이 거의 없었습니다. GC녹십자 계열사 채용 페이지에 '직장생활 필수품 Kit' 정도만 "
        "적혀 있어요. 면접에서 '입사 첫 주에 무엇을 하나요?' 를 물어보세요.",
        "품목은 회사 공식 글(토스·배민·카카오스타일)과 2차 자료(네이버클라우드)에 적힌 것만 옮겼습니다. "
        "웰컴키트는 입사 시기마다 바뀌니 연도를 같이 봐 주세요. 회사 사진은 사용권이 없어 싣지 않았습니다.",
        "출처\n" + "\n".join(f"· {k['company']} — {k['src'][0]}" for k in kits)
        + "\n" + "\n".join(f"· {f['company']} — 채용 페이지 복리후생" for f in ph["found"]),
    ])
    return {"kind": "kit", "id": f"welcomekit-{doc['checked'].replace('-', '')}", "title": doc["title"],
            "slides": slides, "caption": caption, "jobs": []}


def _kit_photo(name: str) -> tuple[str, str]:
    """웰컴키트 사진 → (data URI, 출처 한 줄). 그 회사 그해 키트 사진이고, 누가 어디에 올린 것인지 판마다 적는다."""
    import base64
    c = json.loads((PHOTOS / "welcome" / "credits.json").read_text(encoding="utf-8"))[name]
    uri = "data:image/jpeg;base64," + base64.b64encode((PHOTOS / "welcome" / name).read_bytes()).decode()
    return uri, f"{c['by']} · {c['where']}"


def build_kit_history(fmt: str = "feed") -> dict:
    """[첫 출근 웰컴키트] 2021→2026 변천사 — 해마다 그해 키트 사진 한 장 + 회사별 품목.

    판은 큰 채용 계정(캐치·링커리어·공취사, 팔로워 10만+)의 사진 판을 따른다 — 사진이 판을 채우고,
    노란 꼬리표 + 굵은 흰 제목 두 줄(핵심어 하나만 노랑) + 짧은 줄 몇 개. 자세한 품목은 캡션으로 뺀다.
    fmt: feed(4:5 캐러셀) · reel(9:16, 해마다 두 곳만 — 2.8초에 읽히는 만큼) · story(9:16 세 장).

    품목은 출처 원문에 적힌 것만(content/welcome-kit-history.json). 사진은 회사 공식 글·제작사 사례에서
    그 키트를 찍은 것만 쓰고, 개인 인스타 사진은 쓰지 않는다(원작자 허락 없음 · 원본성 규칙).
    """
    doc = json.loads((CONTENT / "welcome-kit-history.json").read_text(encoding="utf-8"))
    years = doc["years"]
    n_co = len({k["company"] for y in years for k in y["kits"]})
    span = f"{years[0]['year']} → {years[-1]['year']}"
    cover_uri, cover_credit = _kit_photo(doc["cover_photo"])   # 해마다 판과 겹치지 않는 사진
    rows = 2 if fmt == "reel" else 4
    cover = {"type": "mag", "image": cover_uri, "tag": f"웰컴키트 변천사 {span}", "big": 124,
             "head": ["입사하면", "**뭘 받을까?**"], "sub": f"IT 회사 {n_co}곳, 6년 동안 바뀐 것",
             "credit": f"사진: 2025 카카오 키트 — {cover_credit}"}
    year_slides = []
    for y in years:
        uri, credit = _kit_photo(y["photo"])
        year_slides.append({"type": "mag", "image": uri, "tag": y["year"], "head": y["head"],
                            "rows": [[k["company"], k["short"]] for k in y["kits"][:rows]], "credit": f"사진: {credit}"})
    first_uri, _ = _kit_photo(years[0]["photo"])
    last_uri, _ = _kit_photo(years[-1]["photo"])
    grid = [[_kit_photo(y["photo"])[0], y["year"]] for y in years]   # 글만 있는 판도 6년 치 사진을 한눈에
    trend = {"type": "mag", "image": last_uri, "pic": False, "grid": grid, "tag": "6년 동안 바뀐 것",
             "head": ["꽃다발에서", "**노트북 가방**으로"], "lines": doc["trend"]}
    ask = {"type": "mag", "image": first_uri, "pic": False, "grid": grid, "tag": "키트보다 먼저 볼 것",
           "head": ["면접 끝에", "**이걸** 물어보자"], "lines": [
               "**'입사 첫 주에 무엇을 하나요?'** — 온보딩이 키트보다 오래 간다",
               "노트북·모니터 사양은 물어봐도 되는 것",
               "계열사마다 다르다 — 카카오 ≠ 카카오페이 ≠ 카카오엔터",
               "제약·바이오 IT 는 품목 공개가 거의 없다"]}
    cta = {"type": "mag", "image": last_uri, "pic": False, "grid": grid, "tag": "댓글로 알려 주세요",
           "head": ["어느 해 키트가", "**제일 탐나요?**"], "sub": "저장해 두고 · 취준 중인 친구에게 보내 주세요",
           "lines": [f"품목은 출처 원문에 적힌 것만 · 확인 {_dot(doc['checked'])}"]}
    if fmt == "story":
        slides = [cover,
                  {"type": "mag", "image": last_uri, "pic": False, "grid": grid, "tag": span,
                   "head": ["6년 동안", "**뭐가 바뀌었을까?**"], "sub": "꽃다발에서 노트북 가방으로 — 새 게시물에서 다 보기"},
                  {**cta, "head": ["어느 해 키트가", "**제일 탐나요?**"], "sub": "투표 · 질문 스티커로 답해 주세요", "lines": None}]
    elif fmt == "reel":
        slides = [cover, *year_slides, trend, cta]
    else:
        slides = [cover, *year_slides, trend, ask]
    nl = chr(10)
    caption = (nl * 2).join([
        f"[첫 출근 웰컴키트] 입사하면 뭘 받을까? — {span} 변천사",
        nl.join(f"{y['year']} " + " · ".join(f"{k['company']}({k['items']})" for k in y["kits"][:2]) for y in years),
        nl.join(t.replace("**", "") for t in doc["trend"]),
        "어느 해 키트가 제일 탐나요? 받아 본 키트가 있다면 댓글로 알려 주세요. 저장해 두고 취준 중인 친구에게도 보내 주세요.",
        "품목은 회사 공식 글·제작사 사례·기사에 적힌 것만 옮겼습니다. 연도는 입사 기수가 적힌 경우 그 해, "
        "아니면 게시·제작 연도입니다. 사진은 각 장에 출처를 적었습니다.",
        "출처" + nl + nl.join(f"· {y['year']} {k['company']} — {k['src']}" for y in years for k in y["kits"]),
    ])
    suffix = {"feed": "", "reel": "-motion", "story": "-story"}[fmt]
    return {"kind": "kit", "id": f"kithistory-{doc['checked'].replace('-', '')}{suffix}", "title": doc["title"],
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.8,
            # 릴스는 장면마다 천천히 다가가고(정지 화면은 넘겨 버린다) 우리가 만든 소리를 깐다
            **({"motion": 0.05, "audio": str(LAB_DIR / "assets" / "audio" / "bed_calm.wav")} if fmt == "reel" else {})}


# --- 찍기 · 승인 ---------------------------------------------------------
def _api_facets(**q) -> dict:
    """뷰어 API(정본 DB) 의 칩 건수 — 메인·잡 리스트와 같은 숫자. 색인 파일이 아니라 DB 를 읽는 순간의 값."""
    import urllib.parse
    import urllib.request
    qs = urllib.parse.urlencode({"limit": 1, **q})
    with urllib.request.urlopen(f"{os.environ.get('VIEWER_API', 'http://127.0.0.1:8771')}/api/jobs?{qs}", timeout=30) as r:
        d = json.loads(r.read())
    return {"total": d["total"], "career": d["facets"]["careerCount"],
            "roles": {x["name"]: x["count"] for x in d["facets"]["roles"]}}


def _share_words(p: int) -> str:
    """비율을 말로 — 실제 값에 가까울 때만 'N 중 하나' 를 쓴다(36% 를 '절반' 이라 부르지 않게)."""
    for n, word in ((2, "둘"), (3, "셋"), (4, "넷"), (5, "다섯")):
        if abs(p - 100 / n) <= 4:
            return f"{word} 중 하나는"
    return f"{p}%가"


def build_ai_entry() -> dict:
    """[데이터로 본 채용] 신입 자리와 AI — 바깥 보도(신입 감소·AI 역량 요구)를 우리 모집중 공고로 확인한다.
    바깥 숫자는 출처를 판에 적고 원문을 옮기지 않는다. 우리 숫자는 만들 때 API 에서 다시 센다."""
    every, ai = _api_facets(), _api_facets(role="AI/ML")
    asof = date.today().isoformat()
    c = every["career"]
    order = ["신입/무관", "1-2년", "3-4년", "5-7년", "8년+"]
    stated = sum(c.get(k, 0) for k in order)
    entry, ai_entry = c.get("신입/무관", 0), ai["career"].get("신입/무관", 0)
    senior = sum(c.get(k, 0) for k in ("3-4년", "5-7년", "8년+"))
    pct = lambda a, b: round(100 * a / b) if b else 0
    note = (f"모집중 공고 {every['total']:,}건(해외 포함) · 경력 조건을 적은 {stated:,}건 기준 · {_dot(asof)} · "
            "AI/ML 은 제목·본문으로 가른 직군")
    src = "바깥 숫자: SPRi 보고서(잡플래닛 2026.9 인용) · 트위그 2026.1 보도(2024년 기준)"
    slides = [
        {"type": "cover", "big": f"{pct(ai_entry, entry)}", "big_unit": "%",
         "lines": ["신입 공고", _share_words(pct(ai_entry, entry)) + " AI 자리"],
         "sub": f"신입도 되는 공고 {entry:,}건 중 {ai_entry:,}건", "note": note},
        {"type": "bars", "title": "경력 조건별 공고 수", "sub": "경력 조건을 적은 공고만",
         "rows": [{"label": k.replace("/무관", "·무관"), "value": c.get(k, 0), "display": f"{c.get(k, 0):,}",
                   "unit": f"{pct(c.get(k, 0), stated)}%", "hi": k == "신입/무관"} for k in order], "note": note},
        {"type": "stat", "title": "경력 3년 이상을 요구하는 공고", "num": f"{pct(senior, stated)}", "unit": "%",
         "label": f"경력 조건을 적은 {stated:,}건 중 {senior:,}건",
         "explain": f"신입이 지원할 수 있는 곳은 **{pct(entry, stated)}%** 다. 그 신입 자리의 **{pct(ai_entry, entry)}%** 가 AI/ML 쪽이다.",
         "note": note},
        {"type": "table", "title": "밖에서 본 숫자와 우리 공고", "sub": "보도는 요약, 원문은 캡션의 링크",
         "head": ["어디서", "무엇", "숫자"],
         "rows": [["SPRi", "국내 SW 인력 1년 증가", "+0.2%"],
                  ["트위그", "3년 미만 개발자", "−9천 명"],
                  ["트위그", "3년 이상 개발자", "+4.2만 명"],
                  ["우리 공고", "신입 가능 비율", f"{pct(entry, stated)}%"],
                  ["우리 공고", "신입 자리 중 AI/ML", f"{pct(ai_entry, entry)}%"]],
         "hi_col": 2, "note": src},
        {"type": "end", "title": "신입이라면", "lines": [
            f"신입 자리는 **{entry:,}곳** — 줄었지만 없지 않다",
            f"그중 **{ai_entry:,}곳**이 AI/ML — 프로젝트에 AI 를 써 본 흔적을 남기자",
            "저장해 두고 지원할 때 다시 보세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"신입 공고 {_share_words(pct(ai_entry, entry))} AI 자리 — 모집중 {every['total']:,}건으로 확인했습니다.",
        f"· 경력 조건을 적은 {stated:,}건 중 신입 가능 {entry:,}건({pct(entry, stated)}%)\n"
        f"· 경력 3년 이상 요구 {senior:,}건({pct(senior, stated)}%)\n"
        f"· 신입 자리 중 AI/ML {ai_entry:,}건({pct(ai_entry, entry)}%)",
        "밖에서 나온 숫자도 같은 쪽을 가리킵니다 — 국내 SW 인력은 1년에 0.2% 느는 데 그쳤고(SPRi, 잡플래닛 인용), "
        "3년 미만 개발자는 9천 명 줄고 3년 이상은 4만 2천 명 늘었습니다(트위그).",
        "출처\nhttps://www.jobplanet.co.kr/contents/news-8452\nhttps://www.twig24.com/news/2026/01/07/20260107014003",
        f"{_dot(asof)} 우리 사이트(JD Viewer) 모집중 공고 기준. 전체 목록은 프로필 링크에서.",
    ])
    return {"kind": "insight", "id": f"insight-ai-entry-{asof.replace('-', '')}", "title": "신입 공고와 AI",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 3.0,
            "reel_lead": f"신입 공고 {_share_words(pct(ai_entry, entry))} AI 자리였다 — 저장해 두고 지원할 때 보세요"}


def build_game() -> dict:
    """[게임사 채용] 쇼츠 — 게임스컴 2026 에 나간 회사들(보도)과 지금 우리 메인의 '게임' 구역 공고를 견준다.
    짧게 끊어 넘기는 9:16 용이라 장마다 숫자 하나·말 한 줄. 국내 게임사만, 숫자는 만들 때 API 에서."""
    import urllib.parse
    import urllib.request
    base = os.environ.get("VIEWER_API", "http://127.0.0.1:8771")
    with urllib.request.urlopen(f"{base}/api/home?industry={urllib.parse.quote('게임')}&limit=200", timeout=30) as r:
        cos = [c for c in json.loads(r.read())["companies"] if c["size"] != "해외 기업"]
    cos.sort(key=lambda c: -c["active"])
    total, entry = sum(c["active"] for c in cos), sum(c["entry"] for c in cos)
    by = {c["name"]: c for c in cos}
    asof = date.today().isoformat()
    note = f"JD Viewer 모집중 IT 공고 · 국내 게임사 {len(cos)}곳 · {_dot(asof)} · 업종은 회사 이름으로 가른 추정"
    gs = [("크래프톤", "신작 포함 5종 출품"), ("엔씨", "B2B 부스"), ("펄어비스", "연사 참여")]
    slides = [
        {"type": "cover", "big": f"{total}", "big_unit": "건",
         "lines": ["게임스컴 끝난 지금", "게임사가 뽑는 개발자"], "sub": f"국내 게임사 {len(cos)}곳의 모집중 IT 공고", "note": note},
        {"type": "bars", "title": "가장 많이 뽑는 곳", "sub": "회사별 모집중 IT 공고",
         "rows": [{"label": c["name"], "value": c["active"], "display": f"{c['active']}", "unit": "건", "hi": i == 0}
                  for i, c in enumerate(cos[:6])], "note": note},
        {"type": "table", "title": "게임스컴 2026 에 나간 곳", "sub": "8월 쾰른 · 보도는 캡션의 링크",
         "head": ["회사", "게임스컴", "지금 공고"],
         "rows": [[n, what, f"{by[n]['active']}건" if n in by else "—"] for n, what in gs], "hi_col": 2,
         "note": "게임스컴 참가: 머니투데이방송 2026.6.25 보도"},
        {"type": "stat", "title": "신입도 되는 게임사 공고", "num": f"{entry}", "unit": "건",
         "label": f"{total}건 중 {round(100 * entry / total) if total else 0}%",
         "explain": "AI/ML·백엔드 자리가 많다. 게임 클라이언트만 보지 말고 **서버·데이터** 공고도 같이 보자.", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"**{cos[0]['name']}** {cos[0]['active']}건 · **{cos[1]['name']}** {cos[1]['active']}건 · **{cos[2]['name']}** {cos[2]['active']}건",
            "회사별 공고 전체는 프로필 링크에서", "게임 회사 가고 싶은 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"게임스컴 2026 이 끝났습니다. 그 무대에 선 게임사들, 지금 개발자를 얼마나 뽑고 있을까요?",
        f"국내 게임사 {len(cos)}곳에서 모집중인 IT 공고는 {total}건, 신입도 되는 공고는 {entry}건입니다.",
        "많이 뽑는 곳: " + " · ".join(f"{c['name']} {c['active']}건" for c in cos[:5]),
        "게임스컴 2026(8월, 쾰른)에는 크래프톤이 신작을 포함해 5종을 냈고, 엔씨는 B2B 부스를, 펄어비스는 연사로 참여했습니다"
        "(머니투데이방송 보도).",
        "출처\nhttps://news.mtn.co.kr/news-detail/2026062514114422335",
        f"{_dot(asof)} JD Viewer 모집중 공고 기준. 업종은 회사 이름으로 가른 추정입니다.",
    ])
    return {"kind": "game", "id": f"game-gamescom-{asof.replace('-', '')}", "title": "게임사 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "게임스컴 나간 그 회사들, 지금 이만큼 뽑는다 — 저장해 두세요"}


def _api_jobs_all(**q) -> list[dict]:
    """뷰어 API 공고 목록을 끝까지(페이지당 200건). 칩 건수만으로 안 되는 회사별 집계에 쓴다."""
    import urllib.parse
    import urllib.request
    base = os.environ.get("VIEWER_API", "http://127.0.0.1:8771")
    out, page = [], 1
    while True:
        qs = urllib.parse.urlencode({**q, "limit": 200, "page": page})
        with urllib.request.urlopen(f"{base}/api/jobs?{qs}", timeout=60) as r:
            d = json.loads(r.read())
        out += d["items"]
        if len(out) >= d["total"] or not d["items"] or page >= 20:
            return out
        page += 1


#: 같은 회사의 다른 표기 — 집계 전에 하나로(보안 공고에서 'SK쉴더스' 와 '에스케이쉴더스(주)' 가 갈렸다)
_SAME_CO = {"에스케이쉴더스": "SK쉴더스", "hybecareers": "하이브", "쿠팡coupang": "쿠팡",
            "엔에이치엔클라우드": "NHN클라우드", "nhn클라우드": "NHN클라우드", "엔씨": "엔씨소프트"}


def _co_name(name: str) -> str:
    k = re.sub(r"\(.*?\)|㈜|주식회사|\s+", "", name or "").lower()
    shown = re.sub(r"\s+", " ", re.sub(r"\(.*?\)|㈜|^주식회사", " ", name or "")).strip()   # 'SK(주) AX' → 'SK AX'
    return _SAME_CO.get(k, shown)


_SEC_KINDS = {"정보보호·보안 담당": r"정보보호|정보보안|보안\s*담당|ISMS|컴플라이언스",
              "관제": r"관제|SOC|모니터링", "취약점·모의해킹": r"취약점|모의해킹|침투|pentest|레드팀",
              "클라우드 보안": r"클라우드|cloud|AWS"}


def _security_mix(jobs: list[dict]) -> str:
    """신입 보안 공고 제목에서 센 갈래 — 판에 적는 말은 센 숫자로만(어림 말 금지)."""
    c = collections.Counter(k for j in jobs for k, rx in _SEC_KINDS.items() if re.search(rx, j["title"], re.I))
    if not c:
        return "공고 제목에 갈래가 드러나지 않은 곳이 많다."
    (top, n), rest = c.most_common(1)[0], c.most_common()[1:3]
    wj = "\u2060"   # 숫자와 '건' 사이에서 줄이 갈리지 않게(판에서 '관제 8 / 건' 으로 끊겼다)
    tail = " · ".join(f"{k}\u00a0{v}{wj}건" for k, v in rest)
    return f"**{top} {n}{wj}건**이 가장 많다." + (f"\n{tail}" if tail else "")


def build_security() -> dict:
    """[보안 채용] 릴스 — 2025 대형 해킹 사고를 '사람·관리 실패' 로 본 보도(보안뉴스)와, 지금 국내 보안 공고를 견준다.
    해외 근무 공고는 뺀다. 숫자는 만들 때 API 에서 다시 센다."""
    domestic = lambda j: (j.get("place") or {}).get("region") != "해외·원격"
    jobs = [j for j in _api_jobs_all(role="보안") if domestic(j)]
    entry = [j for j in _api_jobs_all(role="보안", career="신입/무관") if domestic(j)]
    cos = collections.Counter(_co_name(j["company"]) for j in jobs).most_common(6)
    n, ne = len(jobs), len(entry)
    asof = date.today().isoformat()
    note = f"JD Viewer 모집중 공고 중 보안 직군 · 국내 근무 {n:,}건 · {_dot(asof)} · 직군은 제목·본문으로 가른 것"
    slides = [
        {"type": "cover", "big": f"{n}", "big_unit": "건", "lines": ["해킹 사고 뒤", "지금 열린 보안 자리"],
         "sub": "국내 근무 보안 직군 모집중 공고", "note": note},
        {"type": "bars", "title": "보안을 가장 많이 뽑는 곳", "sub": "회사별 모집중 보안 공고",
         "rows": [{"label": c, "value": k, "display": f"{k}", "unit": "건", "hi": i == 0} for i, (c, k) in enumerate(cos)],
         "note": note},
        {"type": "table", "title": "사고는 기술보다 사람에서", "sub": "보도는 요약, 원문은 캡션의 링크",
         "head": ["어디서", "무엇", "숫자"],
         "rows": [["보안뉴스", "2025 대형 사고의 원인", "사람·관리"],
                  ["우리 공고", "국내 보안 직군 모집중", f"{n}건"],
                  ["우리 공고", "그중 신입 가능", f"{ne}건"]],
         "hi_col": 2, "note": "보안뉴스 '2026 보안 핫 키워드' 연재 요약"},
        {"type": "stat", "title": "신입이 넣을 수 있는 보안 공고", "num": f"{ne}", "unit": "건",
         "label": f"국내 보안 공고 {n}건 중 {round(100 * ne / n) if n else 0}%",
         "explain": _security_mix(entry), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{c}** {k}건" for c, k in cos[:3]),
            "회사별 공고 전체는 프로필 링크에서", "보안 쪽 준비하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"해킹 사고 뒤, 국내 보안 자리는 지금 {n}건 열려 있습니다(신입 가능 {ne}건).",
        "가장 많이 뽑는 곳: " + " · ".join(f"{c} {k}건" for c, k in cos),
        "보안뉴스는 2025년 대형 사고들을 고도화된 공격보다 사람과 관리의 실패로 봤고, 솔루션을 들이는 것만으로는 "
        "부족하다고 짚었습니다. 사람을 뽑는 자리가 그만큼 중요하다는 뜻이기도 합니다.",
        "출처\nhttps://m.boannews.com/html/detail.html?idx=141318",
        f"{_dot(asof)} JD Viewer 모집중 공고 중 보안 직군(국내 근무) 기준. 직군은 공고 제목·본문으로 가른 것입니다.",
    ])
    return {"kind": "security", "id": f"security-{asof.replace('-', '')}", "title": "보안 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.4,
            "reel_lead": "해킹 사고 뒤 보안 자리, 지금 이만큼 열려 있다 — 저장해 두세요"}


#: 이름으로 적힌 자격증만 센다 — '관련 자격증 우대' 같은 말이나 복지의 '자격증 취득 지원' 은 세지 않는다.
#: 'SAA' 는 SaaS 에, 'AWS 자격' 은 'AWS 자격요건' 에 걸려 낱말 경계를 둔다.
_CERTS = {"보안 자격증": r"정보보안\s*기사|CISSP|\bCISA\b|\bCISM\b",
          "정보처리기사": r"정보처리\s*기사",
          "CCNA·CCNP": r"CCNA|CCNP|CCIE|네트워크관리사",
          "CKA·CKAD": r"\bCKA\b|\bCKAD\b|\bCKS\b",
          "AWS 자격증": r"AWS\s*(공인|자격증|Certified)|Solutions?\s*Architect\s*(Associate|Professional)|\bSAA(-C0\d)?\b",
          "리눅스 자격증": r"리눅스\s*마스터|RHCSA|RHCE|LPIC",
          "Azure·GCP 자격증": r"\bAZ-\d{3}\b|Azure\s*(자격증|Certified)|Google\s*Cloud\s*(자격증|Certified)|Professional\s*Cloud"}


def _infra_rows() -> list[dict]:
    """국내 근무 DevOps/인프라 모집중 공고(사이트 간 사본 뺌) — 본문까지 봐야 해서 API 가 아니라 정본 DB 에서."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket,
                              coalesce(j.qualifications, '') AS qual, coalesce(j.preferences, '') AS pref,
                              concat_ws(E'\\n', j.qualifications, j.preferences, j.full_jd) AS body
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE 'DevOps/인프라' = ANY(f.roles) AND coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        return cur.fetchall()


def build_cert() -> dict:
    """[자격증 우대] 쇼츠 — 'IT 리더 87% 가 인프라·보안 인증 보유자를 우대'(로버트 하프 2026 연봉 가이드, 벤처스퀘어 보도)를
    지금 국내 인프라 공고 본문에서 자격증 이름이 몇 번 나오는지로 확인한다. 숫자는 만들 때 DB 에서 다시 센다."""
    rows = [r for r in _infra_rows() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})]
    hits = [(r, [k for k, rx in _CERTS.items() if re.search(rx, r["body"] or "", re.I)]) for r in rows]
    named = [(r, h) for r, h in hits if h]
    n, nn = len(rows), len(named)
    entry = [r for r in rows if r["career_bucket"] == "신입/무관"]
    entry_named = [r for r, h in named if r["career_bucket"] == "신입/무관"]
    by = collections.Counter(k for _, h in named for k in h).most_common()
    any_rx = "|".join(f"(?:{v})" for v in _CERTS.values())
    required = sum(1 for r, _ in named if re.search(any_rx, r["qual"], re.I))       # 자격요건 칸에 적은 곳
    pref_only = sum(1 for r, _ in named if re.search(any_rx, r["pref"], re.I) and not re.search(any_rx, r["qual"], re.I))
    cos = collections.Counter(_co_name(r["company"]) for r, _ in named).most_common(3)
    pct = lambda a, b: round(100 * a / b) if b else 0
    asof = date.today().isoformat()
    note = (f"JD Viewer 모집중 DevOps/인프라 공고 · 국내 근무 {n:,}건 · {_dot(asof)} · "
            "자격증 이름이 본문에 적힌 공고만 셈")
    src = "로버트 하프 2026 연봉 가이드(벤처스퀘어 2026.3.16 보도) · 조사 범위는 보도에 없음"
    slides = [
        {"type": "cover", "big": f"{pct(nn, n)}", "big_unit": "%",
         "lines": ["자격증, 정말 우대될까", "인프라 공고에서 세 봤다"],
         "sub": f"국내 인프라 공고 {n:,}건 중 자격증 이름을 적은 {nn}건", "note": note},
        {"type": "table", "title": "말과 공고는 달랐다", "sub": "보도는 요약, 원문은 캡션의 링크",
         "head": ["어디서", "무엇", "숫자"],
         "rows": [["로버트 하프", "인증 보유자 우대 IT 리더", "87%"],
                  ["우리 공고", "자격증 이름을 적은 공고", f"{pct(nn, n)}%"],
                  ["우리 공고", "신입 공고 중", f"{pct(len(entry_named), len(entry))}%"]],
         "hi_col": 2, "note": src},
        {"type": "bars", "title": "가장 많이 적힌 자격증", "sub": "그 자격증 이름이 나온 공고 수",
         "rows": [{"label": k, "value": v, "display": f"{v}", "unit": "건", "hi": i == 0}
                  for i, (k, v) in enumerate(by[:6])], "note": note},
        {"type": "stat", "title": "자격증을 적은 공고", "num": f"{nn}", "unit": "건",
         "label": f"국내 인프라 공고 {n:,}건 중",
         "explain": f"**{pref_only}건({pct(pref_only, nn)}%)**은 우대사항에만 적었다.\n자격요건에 적은 곳은 {required}\u2060건.",
         "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{c}** {k}건" for c, k in cos),
            "자격증을 적은 공고 전체는 프로필 링크에서", "자격증 고민하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"인프라·보안 자격증, 정말 우대될까요? 국내 인프라 공고 {n:,}건을 세 봤습니다.",
        f"· 자격증 이름을 본문에 적은 공고 {nn}건({pct(nn, n)}%)\n"
        f"· 신입도 되는 공고 {len(entry)}건 중 {len(entry_named)}건({pct(len(entry_named), len(entry))}%)\n"
        f"· 그중 우대사항에만 적은 곳 {pref_only}건, 자격요건에 적은 곳 {required}건\n"
        "· 많이 나온 자격증: " + " · ".join(f"{k} {v}건" for k, v in by[:4]),
        "벤처스퀘어는 로버트 하프 2026 연봉 가이드를 인용해 IT 리더의 87%가 인프라·보안 공인 인증 보유자에게 "
        "우대 점수를 준다고 전했습니다. 다만 공고에 자격증 이름까지 적는 곳은 그보다 훨씬 적었습니다.",
        "출처\nhttps://www.venturesquare.net/1054188/",
        f"{_dot(asof)} JD Viewer 모집중 공고 중 DevOps/인프라 직군(국내 근무) 기준. '관련 자격증 우대' 처럼 "
        "이름 없이 적은 것과 복지의 '자격증 취득 지원' 은 세지 않았습니다.",
    ])
    return {"kind": "cert", "id": f"cert-infra-{asof.replace('-', '')}", "title": "인프라 자격증 우대",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "자격증, 공고에는 몇 번이나 적혀 있을까 — 저장해 두세요"}


#: 이름으로 적힌 AI 코딩 도구. 'Cursor' 는 페이지네이션 커서와 겹쳐 그 뜻일 때를 뺀다.
#: 'AI 개발도구(pytorch…)' 같은 말은 코딩 도구가 아니라 일반 낱말에서 뺐다.
_AI_TOOLS = {"Claude Code": r"Claude\s*Code", "Cursor": r"\bCursor\b(?![\s-]*(기반|based|pagination|페이지))",
             "Codex": r"\bCodex\b", "ChatGPT": r"ChatGPT", "GitHub Copilot": r"Copilot",
             "AI 코딩 도구": r"AI\s*(코딩|페어\s*프로그래밍)|코딩\s*(어시스턴트|에이전트)|AI\s+coding|AI[- ]assisted\s+(coding|development)"}


def _all_rows() -> list[dict]:
    """국내 근무 모집중 공고(사본 뺌) — 자격요건·우대사항·복지를 칸별로."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket,
                              coalesce(j.qualifications, '') AS qual, coalesce(j.preferences, '') AS pref,
                              coalesce(j.benefits, '') AS perk
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        return [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})]


def build_aitool() -> dict:
    """[AI 코딩 도구] 릴스 — 넥슨·크래프톤이 코딩테스트 대신 AI 활용 과정을 본다는 보도(데일리안 2026.10.19)를,
    지금 국내 공고가 자격요건·우대사항에 AI 코딩 도구를 몇 번 적었는지로 받친다. 복지로 '도구를 대 준다' 는 따로 센다."""
    rows = _all_rows()
    rx = "|".join(f"(?:{v})" for v in _AI_TOOLS.values())
    asked = [r for r in rows if re.search(rx, r["qual"] + "\n" + r["pref"], re.I)]
    required = [r for r in asked if re.search(rx, r["qual"], re.I)]
    perk = [r for r in rows if re.search(rx, r["perk"], re.I) and r not in asked]
    entry = [r for r in asked if r["career_bucket"] == "신입/무관"]
    by = collections.Counter(k for r in asked for k, v in _AI_TOOLS.items()
                             if re.search(v, r["qual"] + "\n" + r["pref"], re.I)).most_common()
    cos = collections.Counter(_co_name(r["company"]) for r in asked).most_common(3)
    n, na = len(rows), len(asked)
    asof = date.today().isoformat()
    wj = "\u2060"
    note = (f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}건 · {_dot(asof)} · "
            "자격요건·우대사항에 도구 이름이 적힌 공고만 셈")
    slides = [
        {"type": "cover", "big": f"{na}", "big_unit": "건",
         "lines": ["코딩테스트 대신", "AI 쓰는 법을 본다"],
         "sub": f"자격요건·우대사항에 AI 코딩 도구를 적은 국내 공고", "note": note},
        {"type": "table", "title": "게임사가 먼저 바꿨다", "sub": "보도는 요약, 원문은 캡션의 링크",
         "head": ["어디서", "무엇", "어떻게"],
         "rows": [["넥슨", "인턴 넥토리얼", "코테 대신 AI 활용 평가"],
                  ["크래프톤", "신입 100명+", "AI 와 푸는 과정 평가"],
                  ["우리 공고", "AI 도구를 적은 곳", f"{na}{wj}건"]],
         "hi_col": 2, "note": "데일리안 2026.10.19 보도 요약"},
        {"type": "bars", "title": "공고에 적힌 도구", "sub": "자격요건·우대사항에 그 이름이 나온 공고 수",
         "rows": [{"label": k, "value": v, "display": f"{v}", "unit": "건", "hi": i == 0}
                  for i, (k, v) in enumerate(by[:6])], "note": note},
        {"type": "stat", "title": "자격요건에 넣은 곳", "num": f"{len(required)}", "unit": "건",
         "label": f"AI 도구를 적은 {na}건 중",
         "explain": f"신입도 되는 공고 중 **{len(entry)}{wj}건**이 AI 도구를 적었다.\n복지로 도구를 대 주는 곳은 따로 {len(perk)}{wj}건.",
         "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{c}** {k}건" for c, k in cos),
            "포트폴리오에 AI 를 어떻게 썼는지 남기자", "취준하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"코딩테스트 대신 AI 를 어떻게 쓰는지 본다 — 국내 IT 공고 {n:,}건에서 세 봤습니다.",
        f"· 자격요건·우대사항에 AI 코딩 도구를 적은 공고 {na}건\n"
        f"· 그중 자격요건에 넣은 곳 {len(required)}건, 신입도 되는 공고 {len(entry)}건\n"
        "· 많이 적힌 도구: " + " · ".join(f"{k} {v}건" for k, v in by[:4]) + "\n"
        f"· 복지로 도구를 대 주는 곳 {len(perk)}건(위 숫자와 겹치지 않게 셈)",
        "데일리안은 넥슨이 인턴십 '넥토리얼'에서 코딩테스트를 없애고 AI 활용 역량 평가를 들였고, 크래프톤은 "
        "AI 와 함께 문제를 정의하고 검증하는 과정을 보는 평가로 신입을 뽑는다고 전했습니다.",
        "출처\nhttps://www.dailian.co.kr/news/view/1703201/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 도구 이름이나 'AI 코딩' 처럼 적힌 것만 셌습니다.",
    ])
    return {"kind": "aitool", "id": f"aitool-{asof.replace('-', '')}", "title": "AI 코딩 도구를 적은 공고",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.2,
            "reel_lead": "이제 코딩테스트 대신 AI 쓰는 법을 본다 — 저장해 두세요"}


#: 같은 그룹 채용 포털의 긴 이름 — 판에서 줄인다
_MOB_NAME = {"현대자동차그룹 (HYUNDAI)": "현대차그룹", "포티투닷 (42dot)": "42dot"}


def build_mobility() -> dict:
    """[모빌리티 채용] 쇼츠 — 현대차가 SDV·AI·로보틱스 인재를 찾는 전 부문 신입 공채(9.1~14, 92개 공고)를 했다는 보도
    (사라경제 2026.8.24) 뒤, 지금 메인의 '자동차·모빌리티' 구역에 남은 국내 IT 공고를 센다."""
    import urllib.parse
    import urllib.request
    base = os.environ.get("VIEWER_API", "http://127.0.0.1:8771")
    q = urllib.parse.quote("자동차·모빌리티")
    with urllib.request.urlopen(f"{base}/api/home?industry={q}&limit=200", timeout=30) as r:
        cos = [c for c in json.loads(r.read())["companies"] if c["size"] != "해외 기업"]
    cos.sort(key=lambda c: -c["active"])
    total, entry = sum(c["active"] for c in cos), sum(c["entry"] for c in cos)
    name = lambda c: _MOB_NAME.get(c["name"], c["name"])
    entry_cos = sorted((c for c in cos if c["entry"]), key=lambda c: -c["entry"])
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 자동차·모빌리티 {len(cos)}곳 · {_dot(asof)} · 업종은 회사 이름으로 가른 추정"
    slides = [
        {"type": "cover", "big": f"{total}", "big_unit": "건", "lines": ["현대차 공채 끝난 뒤", "모빌리티가 뽑는 개발자"],
         "sub": f"국내 자동차·모빌리티 {len(cos)}곳의 모집중 IT 공고", "note": note},
        {"type": "table", "title": "9월에 있었던 일", "sub": "보도는 요약, 원문은 캡션의 링크",
         "head": ["무엇", "언제", "규모"],
         "rows": [["현대차 전 부문 신입 공채", "9.1~9.14", f"92{wj}개 공고"],
                  ["찾은 인재", "SDV·AI·로보틱스", "6개 부문"]],
         "hi_col": 2, "note": "사라경제 2026.8.24 보도"},
        {"type": "bars", "title": "지금 가장 많이 뽑는 곳", "sub": "회사별 모집중 IT 공고",
         "rows": [{"label": name(c), "value": c["active"], "display": f"{c['active']}", "unit": "건", "hi": i == 0}
                  for i, c in enumerate(cos[:6])], "note": note},
        {"type": "stat", "title": "신입도 되는 공고", "num": f"{entry}", "unit": "건",
         "label": f"{total}건 중 {round(100 * entry / total) if total else 0}%",
         "explain": "공채가 끝나면 남는 건 **경력 자리**다.\n신입이라면 " + " · ".join(
             f"{name(c)} {c['entry']}{wj}건" for c in entry_cos[:3]) + ".", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{name(c)}** {c['active']}건" for c in cos[:3]),
            "회사별 공고 전체는 프로필 링크에서", "모빌리티 회사 가고 싶은 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"현대차 신입 공채는 끝났습니다. 그럼 지금 자동차·모빌리티 회사는 개발자를 얼마나 뽑고 있을까요?",
        f"국내 자동차·모빌리티 {len(cos)}곳에서 모집중인 IT 공고는 {total}건, 신입도 되는 공고는 {entry}건입니다.",
        "많이 뽑는 곳: " + " · ".join(f"{name(c)} {c['active']}건" for c in cos[:5]),
        "사라경제는 현대차가 SDV·AI·로보틱스 인재를 찾으려 9월 1~14일 연구개발·IT 등 6개 부문 92개 공고로 "
        "전 부문 신입 공채를 했다고 전했습니다.",
        "출처\nhttps://sateconomy.co.kr/news/view/1065573166413873",
        f"{_dot(asof)} JD Viewer 모집중 공고 기준. 업종은 회사 이름으로 가른 추정입니다.",
    ])
    return {"kind": "mobility", "id": f"mobility-{asof.replace('-', '')}", "title": "모빌리티 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "현대차 공채 끝난 뒤, 모빌리티가 지금 뽑는 개발자 — 저장해 두세요"}


def build_pangyo() -> dict:
    """[판교 채용] 릴스 — 경기도 2025 판교테크노밸리 실태조사(입주 1,780곳·임직원 약 8만 3천 명, 경기일보 2025.12.25)와
    지금 성남시(판교·분당) 근무 모집중 IT 공고. 근무지를 '경기 성남시' 로만 적은 회사가 많아 구가 아니라 시로 센다."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket, f.region, f.district
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE f.region IN ('경기', '서울')
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        allr = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"])]
    rows = [r for r in allr if r["region"] == "경기" and r["district"] == "성남시"]
    gangnam = sum(1 for r in allr if r["region"] == "서울" and r["district"] == "강남구")
    n, entry = len(rows), sum(1 for r in rows if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in rows).most_common(6)
    stacks = collections.Counter(x for r in rows for x in (r["stacks"] or [])).most_common(3)
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 근무지 경기 성남시(판교·분당) {n:,}건 · {_dot(asof)} · 헤드헌팅 공고 뺌"
    slides = [
        {"type": "cover", "big": f"{n}", "big_unit": "건", "lines": ["8만 3천 명이 일하는 판교", "지금 열린 개발 자리"],
         "sub": "근무지가 성남시(판교·분당)인 모집중 IT 공고", "note": note},
        {"type": "table", "title": "판교는 지금", "sub": "경기도 실태조사 요약, 원문은 캡션의 링크",
         "head": ["무엇", "숫자", "변화"],
         "rows": [["입주 기업", f"1,780{wj}곳", "−23곳"],
                  ["임직원", f"약 8.3만{wj}명", "+6%"],
                  ["우리 공고(성남시)", f"{n}{wj}건", "지금"]],
         "hi_col": 1, "note": "경기도 2025 판교테크노밸리 실태조사 · 경기일보 2025.12.25 보도"},
        {"type": "bars", "title": "판교에서 많이 뽑는 곳", "sub": "회사별 모집중 IT 공고",
         "rows": [{"label": c, "value": k, "display": f"{k}", "unit": "건", "hi": i == 0} for i, (c, k) in enumerate(cos)],
         "note": note},
        {"type": "stat", "title": "신입도 되는 공고", "num": f"{entry}", "unit": "건",
         "label": f"{n}건 중 {round(100 * entry / n) if n else 0}%",
         "explain": "많이 적힌 기술은 " + " · ".join(f"**{k}**" for k, _ in stacks) + f".\n서울 강남구는 {gangnam:,}{wj}건이다.",
         "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{c}** {k}건" for c, k in cos[:3]),
            "회사별 공고 전체는 프로필 링크에서", "판교 출근 꿈꾸는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"판교에서 일하는 사람은 약 8만 3천 명. 지금 근무지가 성남시(판교·분당)인 IT 공고는 {n}건입니다.",
        f"· 신입도 되는 공고 {entry}건\n· 많이 뽑는 곳: " + " · ".join(f"{c} {k}건" for c, k in cos[:5]) + "\n"
        "· 많이 적힌 기술: " + " · ".join(k for k, _ in stacks) + f"\n· 견줘 보면 서울 강남구 {gangnam:,}건",
        "경기도의 2025 판교테크노밸리 실태조사에 따르면 제1·2판교 입주 기업은 1,780곳으로 23곳 줄었지만, 임직원은 "
        "약 8만 3천 명으로 6% 늘었습니다(경기일보 보도). 기업 수가 준 건 일부 앵커 기업이 신사옥으로 옮긴 영향이라고 합니다.",
        "출처\nhttps://www.kyeonggi.com/article/20251225580045",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고 기준. 근무지는 공고에 적힌 시·구로 셌고 헤드헌팅 공고는 뺐습니다.",
    ])
    return {"kind": "pangyo", "id": f"pangyo-{asof.replace('-', '')}", "title": "판교 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.2,
            "reel_lead": "8만 3천 명이 일하는 판교, 지금 열린 개발 자리 — 저장해 두세요"}


def _role_key(title: str) -> str:
    """같은 자리를 여러 사이트에 조금씩 다른 제목으로 올린 것을 하나로 — 채용 형태(병역특례·인턴)는 남긴다.
    넛지헬스케어는 같은 자리를 2~3곳에 올려 47건으로 잡혔다(2026-10-20)."""
    kind = "병특" if re.search(r"병역|산업기능", title) else "인턴" if "인턴" in title else ""
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", title)
    t = re.sub(r"병역\s*특[례레]|산업기능요원|대상자|모집|채용전환형|인턴|담당|채용|현역|보충역|개발자|개발|[/·\-]", " ", t)
    return re.sub(r"\s+", "", t).lower() + "|" + kind


def build_health() -> dict:
    """[헬스케어 채용] 쇼츠 — TIME·스태티스타 '세계 최고 헬스테크 기업 2026'(500곳)에 루닛 등 국내 기업이 든 보도
    (벤처스퀘어)와, 메인의 '바이오·헬스케어' 구역 국내 IT 공고. 같은 자리를 여러 사이트에 올린 것은 하나로 센다."""
    import urllib.parse
    import urllib.request
    base = os.environ.get("VIEWER_API", "http://127.0.0.1:8771")
    get = lambda path: json.loads(urllib.request.urlopen(base + path, timeout=30).read())
    cos = [c for c in get(f"/api/home?industry={urllib.parse.quote('바이오·헬스케어')}&limit=200")["companies"]
           if c["size"] != "해외 기업"]
    per, raw = {}, 0
    for c in cos:
        roles = {}
        for j in get(f"/api/home/company/{c['slug']}")["jobs"]:
            if _not_dev({"title": j["title"], "stack": j.get("stacks") or []}):
                continue
            raw += 1
            roles.setdefault(_role_key(j["title"]), j.get("career_bucket"))
        if roles:
            per[c["name"]] = roles
    total = sum(len(v) for v in per.values())
    entry = sum(1 for v in per.values() for b in v.values() if b == "신입/무관")
    top = sorted(per.items(), key=lambda kv: -len(kv[1]))[:6]
    name = lambda n: re.sub(r"에이아이$", "AI", _co_name(n))   # 막대 이름 칸에 '바이오리서치에이아이' 가 잘렸다
    lunit = next((len(v) for n, v in per.items() if "루닛" in n), 0)
    asof = date.today().isoformat()
    wj = "\u2060"
    note = (f"JD Viewer 모집중 IT 공고 · 국내 바이오·헬스케어 {len(per)}곳 · {_dot(asof)} · 같은 자리 중복 게시는 하나로 · "
            "업종은 회사 이름으로 가른 추정")
    slides = [
        {"type": "cover", "big": f"{total}", "big_unit": "개", "lines": ["세계가 꼽은 헬스테크", "국내에서 뽑는 개발 자리"],
         "sub": f"국내 바이오·헬스케어 {len(per)}곳의 모집중 IT 자리", "note": note},
        {"type": "table", "title": "TIME 이 꼽은 한국 헬스테크", "sub": "보도는 요약, 원문은 캡션의 링크",
         "head": ["회사", "분야", "지금 공고"],
         "rows": [["루닛", "진단", f"{lunit}{wj}개" if lunit else "—"],
                  ["스카이랩스", "의료기기·웨어러블", "—"],
                  ["우리 공고", "바이오·헬스케어", f"{total}{wj}개"]],
         "hi_col": 2, "note": "TIME·스태티스타 세계 최고 헬스테크 기업 2026(500곳) · 벤처스퀘어 2026.9.18·9.21 보도 · —는 우리 공고 없음"},
        {"type": "bars", "title": "많이 뽑는 곳", "sub": "회사별 모집중 IT 자리(중복 게시는 하나로)",
         "rows": [{"label": name(n), "value": len(v), "display": f"{len(v)}", "unit": "개", "hi": i == 0}
                  for i, (n, v) in enumerate(top)], "note": note},
        {"type": "stat", "title": "신입도 되는 자리", "num": f"{entry}", "unit": "개",
         "label": f"{total}개 중 {round(100 * entry / total) if total else 0}%",
         "explain": f"사이트마다 따로 센 공고는 {raw}{wj}건이었다.\n같은 자리를 여러 곳에 올린 것을 하나로 묶으면 {total}{wj}개.",
         "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{name(n)}** {len(v)}개" for n, v in top[:3]),
            "회사별 공고 전체는 프로필 링크에서", "의료·헬스케어 쪽 가고 싶은 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"TIME 이 꼽은 세계 최고 헬스테크 기업에 루닛이 들었습니다. 그럼 국내 바이오·헬스케어 회사는 지금 개발자를 얼마나 뽑을까요?",
        f"· 국내 바이오·헬스케어 {len(per)}곳의 모집중 IT 자리 {total}개(같은 자리를 여러 사이트에 올린 것은 하나로)\n"
        f"· 신입도 되는 자리 {entry}개\n· 많이 뽑는 곳: " + " · ".join(f"{name(n)} {len(v)}개" for n, v in top[:5]),
        "벤처스퀘어는 TIME 과 스태티스타가 30여 개국 500개 기업을 꼽은 '세계 최고 헬스테크 기업 2026'에 루닛이 진단 분야로 "
        "선정됐다고 전했습니다. 의료기기·웨어러블 분야에는 스카이랩스가 한국 기업으로 유일하게 들었습니다.",
        "출처\nhttps://www.venturesquare.net/1115045/\nhttps://www.venturesquare.net/1115416/",
        f"{_dot(asof)} JD Viewer 모집중 공고 기준. 업종은 회사 이름으로 가른 추정이고, 같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "health", "id": f"health-{asof.replace('-', '')}", "title": "헬스케어 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "TIME 이 꼽은 헬스테크, 국내에서 뽑는 개발 자리 — 저장해 두세요"}


def build_junior() -> dict:
    """[주니어 채용] 릴스 — 잡코리아 '주니어 편' 설문(1,000명, 2026.7.28: 공고가 줄었다 76.4%·서류에서 막힌다 67.5%)과
    지금 신입·1~2년차가 넣을 수 있는 국내 공고를 회사 규모로 나눠 센다. 헤드헌팅·인력 파견 공고는 뺀다."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket, f.company_size
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격' AND f.career_bucket IN ('신입/무관', '1-2년')
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"])]
    n = len(rows)
    entry = sum(1 for r in rows if r["career_bucket"] == "신입/무관")
    size = collections.Counter(r["company_size"] or "규모 모름" for r in rows)
    order = ["대기업", "중견기업", "중소기업"]
    big = [r for r in rows if r["company_size"] == "대기업"]
    big_cos = collections.Counter(_co_name(r["company"]) for r in big).most_common(3)
    pct = lambda a: round(100 * a / n) if n else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = (f"JD Viewer 모집중 IT 공고 · 국내 근무 · 경력 조건 신입·1~2년 · {_dot(asof)} · 헤드헌팅·파견 공고 뺌 · "
            "규모를 모르는 회사는 중소기업으로 셈")
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "건", "lines": ["공고가 줄었다는 주니어", "지금 넣을 수 있는 곳"],
         "sub": f"신입 {entry:,}건 · 1~2년차 {n - entry:,}건", "note": note},
        {"type": "table", "title": "주니어가 느끼는 시장", "sub": "잡코리아 설문 요약, 원문은 캡션의 링크",
         "head": ["무엇", "응답", ""],
         "rows": [["공고 자체가 줄었다", f"76.4{wj}%", ""],
                  ["서류에서 막힌다", f"67.5{wj}%", ""],
                  ["면접까지 간 곳이 없다", f"35.0{wj}%", ""]],
         "hi_col": 1, "note": "잡코리아 2026 하반기 개발자 취업 현황 리포트 · 주니어 편(2026.7.28, 1,000명)"},
        {"type": "bars", "title": "어디에 열려 있나", "sub": "회사 규모별 주니어 공고",
         "rows": [{"label": k, "value": size.get(k, 0), "display": f"{size.get(k, 0):,}", "unit": f"{pct(size.get(k, 0))}%",
                   "hi": k == "중소기업"} for k in order], "note": note},
        {"type": "stat", "title": "대기업 주니어 자리", "num": f"{len(big)}", "unit": "건",
         "label": f"{n:,}건 중 {pct(len(big))}%",
         "explain": "서류에서 막힌다면 **중견·중소** 공고까지 넓혀 보자.\n대기업 쪽은 " + " · ".join(
             f"{c} {k}{wj}건" for c, k in big_cos) + ".", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"신입 **{entry:,}건** · 1~2년차 **{n - entry:,}건**",
            "규모별 공고 전체는 프로필 링크에서", "취준하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"주니어 4명 중 3명은 '공고 자체가 줄었다'고 느낍니다. 그래도 지금 신입·1~2년차가 넣을 수 있는 국내 IT 공고는 {n:,}건입니다.",
        f"· 신입 {entry:,}건 · 1~2년차 {n - entry:,}건\n· 회사 규모: " + " · ".join(f"{k} {size.get(k, 0):,}건" for k in order) + "\n"
        "· 대기업에서 주니어를 많이 뽑는 곳: " + " · ".join(f"{c} {k}건" for c, k in big_cos),
        "잡코리아가 경력 3년 이하 개발자 1,000명에게 물었더니 76.4%가 공고 자체가 줄었다고 했고, 67.5%는 서류에서 가장 많이 "
        "막힌다고 답했습니다. 면접까지 간 곳이 한 곳도 없다는 응답도 35.0%였습니다.",
        "출처\nhttps://www.jobkorea.co.kr/recruit/careers/articles/junior-developer-2026",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무, 경력 조건 신입·1~2년) 기준. 헤드헌팅·파견 공고는 뺐습니다.",
    ])
    return {"kind": "junior", "id": f"junior-{asof.replace('-', '')}", "title": "주니어 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.2,
            "reel_lead": "공고가 줄었다는 주니어, 지금 넣을 수 있는 곳 — 저장해 두세요"}


_AI_TITLE = re.compile(r"(?<![A-Za-z])AI(?![A-Za-z])|인공지능|LLM|머신\s*러닝|딥\s*러닝|(?<![A-Za-z])ML(?![A-Za-z])|생성형", re.I)


def build_usvs() -> dict:
    """[미국 vs 우리] 쇼츠 — Indeed 미국 소프트웨어 개발 공고(CIO 2026.7.13: 팬데믹 전보다 27.5% 적고, 2025.2 이후 15% 늘었고,
    늘어난 것의 71% 가 시니어, 37% 가 제목에 AI)를 지금 국내 모집중 IT 공고의 같은 두 잣대(5년 이상 비중·제목에 AI)로 견준다.
    미국 숫자는 '늘어난 공고 중' 비중이고 우리 숫자는 '지금 열린 공고 중' 비중이라 같은 잣대가 아니다 — 판에 그렇게 적는다."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"])]
    n = len(rows)
    c = collections.Counter(r["career_bucket"] for r in rows)
    order = ["신입/무관", "1-2년", "3-4년", "5-7년", "8년+"]
    stated = sum(c.get(k, 0) for k in order)
    senior = c.get("5-7년", 0) + c.get("8년+", 0)
    ai = sum(1 for r in rows if _AI_TITLE.search(r["title"]))
    pct = lambda a, b: round(100 * a / b) if b else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}건 · {_dot(asof)} · 경력 비중은 경력 조건을 적은 {stated:,}건 기준"
    slides = [
        {"type": "cover", "big": f"{pct(ai, n)}", "big_unit": "%", "lines": ["미국은 AI 자리가 늘었다", "우리 공고는?"],
         "sub": f"국내 IT 공고 {n:,}건 중 제목에 AI 가 든 {ai:,}건", "note": note},
        {"type": "table", "title": "미국 개발 공고(Indeed)", "sub": "보도 요약 · 미국 기준", "head": ["무엇", "숫자", ""],
         "rows": [["팬데믹 전보다", f"−27.5{wj}%", ""], ["2025.2 이후", f"+15{wj}%", ""],
                  ["늘어난 것 중 시니어", f"71{wj}%", ""], ["늘어난 것 중 제목에 AI", f"37{wj}%", ""]],
         "hi_col": 1, "note": "CIO 2026.7.13 보도(Indeed Hiring Lab 데이터) 요약"},
        {"type": "bars", "title": "우리 공고의 경력 조건", "sub": "지금 열린 국내 IT 공고",
         "rows": [{"label": k.replace("/무관", "·무관"), "value": c.get(k, 0), "display": f"{c.get(k, 0):,}",
                   "unit": f"{pct(c.get(k, 0), stated)}%", "hi": k in ("5-7년", "8년+")} for k in order], "note": note},
        {"type": "stat", "title": "5년 이상을 찾는 공고", "num": f"{pct(senior, stated)}", "unit": "%",
         "label": f"경력 조건을 적은 {stated:,}건 중 {senior:,}건",
         "explain": f"미국 숫자는 '늘어난 공고' 중 비중이고 이건 '지금 열린 공고' 중 비중이다.\n제목에 AI 가 든 공고는 {ai:,}{wj}건({pct(ai, n)}%).",
         "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"제목에 AI **{pct(ai, n)}%** · 5년 이상 **{pct(senior, stated)}%**",
            "경력별 공고 전체는 프로필 링크에서", "이직 고민하는 동료에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"미국은 개발 공고가 다시 늘고 있고, 늘어난 자리의 37%가 제목에 AI 를 달았습니다. 우리 공고는 {pct(ai, n)}%입니다.",
        f"· 국내 IT 공고 {n:,}건 중 제목에 AI 가 든 공고 {ai:,}건({pct(ai, n)}%)\n"
        f"· 경력 조건을 적은 {stated:,}건 중 5년 이상 {senior:,}건({pct(senior, stated)}%), 신입 가능 {c.get('신입/무관', 0):,}건"
        f"({pct(c.get('신입/무관', 0), stated)}%)",
        "CIO 는 Indeed 데이터를 인용해 미국 소프트웨어 개발 공고가 팬데믹 이전보다 27.5% 적지만 2025년 2월 이후 15% 늘었고, "
        "2025년 5월부터 1년 동안 늘어난 공고의 71%가 시니어, 37%가 제목에 AI 를 단 자리였다고 전했습니다.",
        "미국 숫자는 '늘어난 공고' 중 비중, 우리 숫자는 '지금 열린 공고' 중 비중이라 같은 잣대는 아닙니다.",
        "출처\nhttps://www.cio.com/article/4195780/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준.",
    ])
    return {"kind": "usvs", "id": f"usvs-{asof.replace('-', '')}", "title": "미국 vs 우리 개발 공고",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "미국은 AI 자리가 늘었다, 우리 공고는? — 저장해 두세요"}


def build_gap() -> dict:
    """[신입 vs 경력] 릴스 — 산업부 '산업기술인력 수급 실태조사'(경향신문 2025.12.31: 2026 채용 예상 경력 +3.7%·신입 −5.2%)를
    우리 메인 화면의 신입·경력 구역 숫자와 대기업 신입 자리로 받친다. 숫자는 /api/home 의 메인 화면 그대로."""
    import urllib.request
    base = os.environ.get("VIEWER_API", "http://127.0.0.1:8771")
    home = json.loads(urllib.request.urlopen(base + "/api/home", timeout=30).read())
    sec = {x["key"]: x for x in home["sections"]}
    entry, exp = sec["entry"]["total"], sec["experienced"]["total"]
    big = [j for j in sec["entry"]["jobs"] if j["size"] == "대기업" and not _not_dev({"title": j["title"], "stack": j.get("stacks") or []})]
    big_cos = list(dict.fromkeys(_co_name(j["company"]).replace(" Careers", "") for j in big))   # 센 수 그대로 — 자르지 않는다
    shown = len(sec["entry"]["jobs"])
    ratio = exp / entry if entry else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 메인 화면 '신입'·'경력' 구역 · 모집중 IT 공고 · {_dot(asof)}"
    slides = [
        {"type": "cover", "big": f"1 : {ratio:.1f}", "big_unit": "", "lines": ["신입 한 자리에", "경력 자리는 이만큼"],
         "sub": f"신입 {entry:,}건 · 경력 {exp:,}건", "note": note},
        {"type": "table", "title": "2026년 채용 계획", "sub": "산업부 실태조사 요약, 원문은 캡션의 링크",
         "head": ["누구", "작년보다", "인원"],
         "rows": [["경력자", f"+3.7{wj}%", f"+1,338{wj}명"], ["신입", f"−5.2{wj}%", f"−1,430{wj}명"]],
         "hi_col": 1, "note": "산업통상부 산업기술인력 수급 실태조사 · 경향신문 2025.12.31 보도"},
        {"type": "bars", "title": "지금 열린 자리", "sub": "메인 화면 구역별 모집중 IT 공고",
         "rows": [{"label": "경력", "value": exp, "display": f"{exp:,}", "unit": "건", "hi": False},
                  {"label": "신입", "value": entry, "display": f"{entry:,}", "unit": "건", "hi": True}], "note": note},
        {"type": "stat", "title": "그래도 대기업 신입 자리는 있다", "num": f"{len(big_cos)}", "unit": "곳",
         "label": f"메인 '신입 인기' TOP {shown} 에 든 대기업",
         "explain": " · ".join(f"**{c}**" for c in big_cos[:3]) + "\n" + " · ".join(big_cos[3:6]), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"신입 **{entry:,}건** · 경력 **{exp:,}건**", "신입 공고 전체는 프로필 링크에서", "취준하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"신입 한 자리에 경력 자리는 {ratio:.1f}개. 지금 열린 IT 공고는 신입 {entry:,}건, 경력 {exp:,}건입니다.",
        "산업부의 '산업기술인력 수급 실태조사'에 따르면 2026년 채용 예상 인원은 경력자가 3.7%(1,338명) 늘고 신입은 "
        "5.2%(1,430명) 줄어듭니다(경향신문 보도).",
        f"그래도 메인 '신입 인기' TOP {shown} 에 대기업 {len(big_cos)}곳이 있습니다: " + " · ".join(big_cos),
        "출처\nhttps://www.khan.co.kr/article/202512312007015/",
        f"{_dot(asof)} JD Viewer 메인 화면 '신입'·'경력' 구역 기준.",
    ])
    return {"kind": "gap", "id": f"gap-{asof.replace('-', '')}", "title": "신입 vs 경력",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "신입 한 자리에 경력 자리는 이만큼 — 저장해 두세요"}


def build_cloud() -> dict:
    """[클라우드 채용] 쇼츠 — AWS 한국 누적 투자 12조 6천억 원·신규 일자리 1만 2,300명(아이뉴스24 2026.5.20, AWS 서밋 서울)을
    지금 국내 IT 공고가 적은 클라우드(AWS·Azure·GCP)로 받친다. 기술은 공고 본문에서 뽑은 스택."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"])]
    n = len(rows)
    has = lambda r, k: k in (r["stacks"] or [])
    clouds = {k: sum(1 for r in rows if has(r, k)) for k in ("AWS", "Azure", "GCP")}
    anyc = [r for r in rows if any(has(r, k) for k in clouds)]
    aws = [r for r in rows if has(r, "AWS")]
    entry = sum(1 for r in aws if r["career_bucket"] == "신입/무관")
    # 같은 자리를 여러 사이트에 올린 회사가 앞에 서지 않게 — 회사별로는 자리(_role_key)를 센다(넛지헬스케어 39 → 실제 자리 수)
    cos = collections.Counter(c for c, _ in {(_co_name(r["company"]), _role_key(r["title"])) for r in aws}).most_common(3)
    pct = lambda a, b: round(100 * a / b) if b else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}건 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것"
    slides = [
        {"type": "cover", "big": f"{len(aws):,}", "big_unit": "건", "lines": ["AWS 가 12조 넣는 한국", "AWS 를 쓰는 개발 자리"],
         "sub": f"국내 IT 공고 {n:,}건 중 {pct(len(aws), n)}%", "note": note},
        {"type": "table", "title": "AWS 의 한국 투자", "sub": "보도 요약, 원문은 캡션의 링크", "head": ["무엇", "숫자", ""],
         "rows": [["누적 투자(2018~2031)", f"12.6조{wj}원", ""], ["신규 일자리", f"1만 2,300{wj}명", ""],
                  ["AI·클라우드 교육", f"30만{wj}명+", ""]],
         "hi_col": 1, "note": "아이뉴스24 2026.5.20(AWS 서밋 서울) 보도 요약"},
        {"type": "bars", "title": "공고에 적힌 클라우드", "sub": "그 이름이 나온 국내 IT 공고 수",
         "rows": [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v, n)}%", "hi": k == "AWS"}
                  for k, v in sorted(clouds.items(), key=lambda kv: -kv[1])], "note": note},
        {"type": "stat", "title": "신입도 되는 AWS 자리", "num": f"{entry}", "unit": "건",
         "label": f"AWS 를 적은 {len(aws):,}건 중 {pct(entry, len(aws))}%",
         "explain": f"셋 중 하나라도 적은 공고는 {len(anyc):,}{wj}건({pct(len(anyc), n)}%).\n많이 뽑는 곳은 " +
                    " · ".join(f"{c} {k}{wj}자리" for c, k in cos) + ".", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v:,}건" for k, v in sorted(clouds.items(), key=lambda kv: -kv[1])),
            "클라우드 공고 전체는 프로필 링크에서", "클라우드 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"AWS 가 한국에 12조 6천억 원을 넣습니다. 지금 AWS 를 적은 국내 IT 공고는 {len(aws):,}건({pct(len(aws), n)}%)입니다.",
        "· 공고에 적힌 클라우드: " + " · ".join(f"{k} {v:,}건" for k, v in sorted(clouds.items(), key=lambda kv: -kv[1])) + "\n"
        f"· AWS 공고 중 신입 가능 {entry}건\n· AWS 를 많이 적은 곳(같은 자리 중복 게시는 하나로): " + " · ".join(f"{c} {k}자리" for c, k in cos),
        "아이뉴스24 는 AWS 서밋 서울에서 AWS 가 2018~2031년 한국 누적 투자 규모를 12조 6천억 원으로 밝혔고, 이 투자가 "
        "신규 일자리 1만 2,300명과 30만 명 이상의 AI·클라우드 교육으로 이어진다고 전했습니다.",
        "출처\nhttps://inews24.com/view/1970128",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것입니다.",
    ])
    return {"kind": "cloud", "id": f"cloud-{asof.replace('-', '')}", "title": "클라우드 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "AWS 가 12조 넣는 한국, AWS 쓰는 개발 자리 — 저장해 두세요"}


def build_paywish() -> dict:
    """[희망 초봉 vs 공고] 릴스 — 인크루트 설문(디지털데일리 2026.4.22, 504명: 희망 초봉 4,196만·마지노선 3,611만)과
    지금 모집중인 신입 개발 공고가 숫자로 적은 신입 연봉을 견준다. 세는 법은 build_pay_newgrad 와 같고 모집중만 본다."""
    parse = _parse_pay()
    allj = _source()
    today = date.today()
    found = {}
    for j in allj:
        if j.get("status") != "active" or "신입" not in (j.get("career") or "") or _not_dev(j):
            continue
        if (d := _deadline(j, today)) and d < today:
            continue
        p = parse("\n".join(j.get(k) or "" for k in ("benefits", "full_jd")))
        if not p or re.search(r"\$|USD|달러|환율", p["text"]):
            continue
        if "신입" not in p["text"] and not re.fullmatch(r"\s*신입(/무관)?\s*", j.get("career") or ""):
            continue
        mid = (p["low"] + p["high"]) // 2 if p.get("high") else p["low"]
        if _company(j) != NO_CO and 1500 <= mid <= 15000:     # 월급·오타로 읽힌 값은 뺀다
            found.setdefault((_company(j), mid), (j, mid))
    rows = list(found.values())
    n = len(rows)
    mids = sorted(m for _, m in rows)
    med = mids[n // 2] if n else 0
    over_wish = sum(1 for m in mids if m >= 4196)
    over_floor = sum(1 for m in mids if m >= 3611)
    pct = lambda a: round(100 * a / n) if n else 0
    top = sorted(rows, key=lambda r: -r[1])[:3]
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 신입 개발 공고 중 신입 연봉을 숫자로 적은 {n}곳(회사·금액 중복 제외) · {_dot(asof)} · 범위는 가운데 값"
    slides = [
        {"type": "cover", "big": f"{med:,}", "big_unit": "만원", "lines": ["바라는 초봉 4,196만", "공고에 적힌 신입 연봉은"],
         "sub": f"지금 모집중, 신입 연봉을 숫자로 적은 {n}곳의 가운데 값", "note": note},
        {"type": "table", "title": "신입이 바라는 연봉", "sub": "인크루트 설문 요약, 원문은 캡션의 링크",
         "head": ["무엇", "평균", "작년보다"],
         "rows": [["희망 초봉", f"4,196{wj}만", f"+56{wj}만"], ["마지노선", f"3,611{wj}만", f"−26{wj}만"]],
         "hi_col": 1, "note": "인크루트 2026 신입 희망 초봉 설문(504명) · 디지털데일리 2026.4.22 보도"},
        {"type": "bars", "title": "공고에 적힌 신입 연봉", "sub": f"{n}곳 · 설문의 두 선과 견줘",
         "rows": [{"label": "희망 이상", "value": over_wish, "display": f"{over_wish}", "unit": f"{pct(over_wish)}%", "hi": True},
                  {"label": "마지노선~희망", "value": over_floor - over_wish, "display": f"{over_floor - over_wish}",
                   "unit": f"{pct(over_floor - over_wish)}%", "hi": False},
                  {"label": "마지노선 미만", "value": n - over_floor, "display": f"{n - over_floor}",
                   "unit": f"{pct(n - over_floor)}%", "hi": False}], "note": note},
        {"type": "stat", "title": "희망 초봉을 넘게 적은 곳", "num": f"{over_wish}", "unit": "곳",
         "label": f"숫자를 적은 {n}곳 중 {pct(over_wish)}%",
         "explain": "높게 적은 곳: " + " · ".join(f"**{_company(j)}** {m:,}{wj}만" for j, m in top) +
                    "\n큰 회사일수록 숫자를 안 적는다 — 적어 둔 곳들의 값이다.", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"공고 가운데 값 **{med:,}만** · 희망 **4,196만** · 마지노선 **3,611만**",
            "연봉 적은 공고 전체는 프로필 링크에서", "취준하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"신입이 바라는 초봉은 4,196만 원. 지금 신입 개발 공고에 숫자로 적힌 신입 연봉의 가운데 값은 {med:,}만 원입니다.",
        f"· 신입 연봉을 숫자로 적은 모집중 공고 {n}곳(회사·금액 중복 제외)\n· 희망 초봉 이상 {over_wish}곳({pct(over_wish)}%), "
        f"마지노선 이상 {over_floor}곳({pct(over_floor)}%)",
        "디지털데일리는 인크루트가 졸업 예정자와 구직자 504명에게 물은 결과 희망 초봉 평균이 4,196만 원(작년보다 56만 원 ↑), "
        "마지노선은 3,611만 원(26만 원 ↓)이었다고 전했습니다.",
        "큰 회사일수록 공고에 연봉을 적지 않습니다 — '적어 둔 곳들의 값' 으로 읽어 주세요.",
        "출처\nhttps://www.ddaily.co.kr/page/view/2026042210565982915",
        f"{_dot(asof)} JD Viewer 모집중 신입 개발 공고 기준. 범위는 가운데 값, '이상' 은 하한으로 셌습니다.",
    ])
    return {"kind": "wish", "id": f"paywish-{asof.replace('-', '')}", "title": "희망 초봉 vs 공고",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.2,
            "reel_lead": "바라는 초봉 4,196만, 공고에 적힌 신입 연봉은? — 저장해 두세요"}


_ROBOT = re.compile(r"로봇|로보틱스|robot|휴머노이드|humanoid|(?<![A-Za-z])ROS2?(?![A-Za-z])|매니퓰레이터|자율\s*주행\s*로봇|AMR", re.I)


def build_robot() -> dict:
    """[로봇 채용] 쇼츠 — 휴머노이드 특성화 대학원 하반기 신설(연 30억 원 안팎·최대 5년, 산업통상부 보도자료 2026.7.2)을
    지금 제목에 로봇을 단 국내 IT 공고로 받친다. 같은 자리를 여러 사이트에 올린 것은 하나로 센다."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    from .newscard import _NOT_JOB          # 교육생·국비 과정은 일자리가 아니다
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket, f.region
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if _ROBOT.search(r["title"])
                and not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"]) and not _NOT_JOB.search(r["title"])]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co_name(r["company"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    entry = sum(1 for r in rows if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in rows).most_common(6)
    stacks = collections.Counter(x for r in rows for x in (r["stacks"] or [])).most_common(4)
    pct = lambda a: round(100 * a / n) if n else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 중 제목에 로봇·로보틱스·ROS 가 든 국내 근무 자리 · {_dot(asof)} · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "big": f"{n}", "big_unit": "개", "lines": ["휴머노이드 대학원 생기는 해", "로봇 개발 자리는"],
         "sub": "제목에 로봇·로보틱스·ROS 가 든 모집중 IT 자리", "note": note},
        {"type": "table", "title": "정부가 키우는 로봇 인재", "sub": "보도자료 요약, 원문은 캡션의 링크", "head": ["무엇", "규모", ""],
         "rows": [["휴머노이드 특성화 대학원", f"올해 하반기 신설", ""], ["지원", f"연 30억{wj}원 안팎", ""],
                  ["기간", f"최대 5{wj}년", ""]],
         "hi_col": 1, "note": "산업통상부 보도자료 2026.7.2 요약"},
        {"type": "bars", "title": "로봇 자리 많은 곳", "sub": "회사별 모집중 자리(중복 게시는 하나로)",
         "rows": [{"label": c, "value": k, "display": f"{k}", "unit": "개", "hi": i == 0} for i, (c, k) in enumerate(cos)],
         "note": note},
        {"type": "stat", "title": "신입도 되는 로봇 자리", "num": f"{entry}", "unit": "개", "label": f"{n}개 중 {pct(entry)}%",
         "explain": "많이 적힌 기술은 " + " · ".join(f"**{k}**" for k, _ in stacks) + ".", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{c}** {k}개" for c, k in cos[:3]),
            "로봇 공고 전체는 프로필 링크에서", "로봇 만들고 싶은 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"휴머노이드 특성화 대학원이 올해 하반기 처음 생깁니다. 지금 로봇 개발 자리는 {n}개 열려 있어요.",
        f"· 신입도 되는 자리 {entry}개\n· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos[:5]) + "\n"
        "· 많이 적힌 기술: " + " · ".join(k for k, _ in stacks),
        "산업통상부는 국제로보컵·휴머노이드 챌린지에 맞춰, 올해 하반기 휴머노이드 특성화 대학원을 처음 만들고 연 30억 원 안팎을 "
        "최대 5년 지원한다고 밝혔습니다.",
        "출처\nhttps://www.motir.go.kr/kor/article/ATCL3f49a5a8c/171994/view",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고 중 제목에 로봇·로보틱스·ROS 가 든 국내 근무 자리. 같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "robot", "id": f"robot-{asof.replace('-', '')}", "title": "로봇 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "휴머노이드 대학원 생기는 해, 로봇 개발 자리는 — 저장해 두세요"}


def build_spring() -> dict:
    """[스프링 채용] 릴스 — Spring Boot 4.0.0 정식판(spring.io 2025.11.20, 지금 4.1.1)이 나온 지 11달,
    국내 공고는 어느 버전을 적나. 본문에 'Spring Boot N' 과 'Java N' 이 적힌 공고만 센다(대부분은 버전을 적지 않는다)."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket,
                              concat_ws(' ', j.qualifications, j.preferences, j.full_jd) AS body
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"])]
    spring = [r for r in rows if re.search(r"spring", r["body"] or "", re.I)]
    boot = collections.Counter(v for r in spring for v in set(re.findall(r"Spring\s*Boot\s*([234])(?:\.\d+)?", r["body"] or "", re.I)))
    java = collections.Counter(v for r in rows for v in set(re.findall(r"(?:Java|JDK|자바)\s*(8|11|17|21|25)(?!\d)", r["body"] or "", re.I)))
    named = sum(boot.values())
    entry = sum(1 for r in spring if r["career_bucket"] == "신입/무관")
    n = len(spring)
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 · 본문에 Spring 이 든 {n:,}건 · {_dot(asof)} · 버전은 본문에 적힌 것만"
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "건", "lines": ["Spring Boot 4 나온 지 11달", "공고는 몇 버전을 쓸까"],
         "sub": "본문에 Spring 이 든 국내 IT 공고", "note": note},
        {"type": "table", "title": "Spring Boot 는 지금", "sub": "spring.io 발표", "head": ["무엇", "언제", ""],
         "rows": [["4.0.0 정식판", f"2025.11.20", ""], ["지금 최신", f"4.1.1", ""]],
         "hi_col": 1, "note": "spring.io 블로그 'Spring Boot 4.0.0 available now' · spring.io 프로젝트 페이지"},
        {"type": "bars", "title": "공고에 적힌 Spring Boot 버전", "sub": f"버전을 적은 공고는 {named}{wj}건뿐",
         "rows": [{"label": f"Boot {v}.x", "value": boot.get(v, 0), "display": f"{boot.get(v, 0)}", "unit": "건", "hi": v == "4"}
                  for v in ("4", "3", "2")], "note": note},
        {"type": "bars", "title": "공고에 적힌 Java 버전", "sub": "본문에 'Java N' 이 든 공고 수",
         "rows": [{"label": f"Java {v}", "value": java.get(v, 0), "display": f"{java.get(v, 0)}", "unit": "건", "hi": v == "21"}
                  for v in ("25", "21", "17", "11", "8") if java.get(v, 0)], "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"Spring 공고 **{n:,}건** · 신입 가능 **{entry}건**",
            f"버전을 적은 곳은 **Boot 3.x** 가 가장 많다({boot.get('3', 0)}건)", "스프링 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"Spring Boot 4.0 정식판이 나온 지 11달. 국내 IT 공고 중 본문에 Spring 이 든 곳은 {n:,}건(신입 가능 {entry}건)입니다.",
        f"· 버전을 적은 공고는 {named}건뿐: " + " · ".join(f"Boot {v}.x {boot.get(v, 0)}건" for v in ("4", "3", "2")) + "\n"
        "· Java 버전: " + " · ".join(f"Java {v} {java[v]}건" for v in ("25", "21", "17", "11", "8") if java.get(v)),
        "spring.io 는 2025년 11월 20일 Spring Boot 4.0.0 정식판을 발표했고, 지금 최신은 4.1.1 입니다. "
        "공고 대부분은 버전을 적지 않으니, 면접에서 쓰는 버전을 물어보는 것도 방법입니다.",
        "출처\nhttps://spring.io/blog/2025/11/20/spring-boot-4-0-0-available-now/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 버전은 공고 본문에 'Spring Boot N'·'Java N' 으로 적힌 것만 셌습니다.",
    ])
    return {"kind": "spring", "id": f"spring-{asof.replace('-', '')}", "title": "스프링 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Spring Boot 4 나온 지 11달, 공고는 몇 버전을 쓸까 — 저장해 두세요"}


def build_vc() -> dict:
    """[투자와 채용] 쇼츠 — 상반기 벤처투자 8조 8,676억 원·AI 업종 51.2%·게임 76.3% 감소(뉴시스 2026.8.19, 중기부 발표)를
    지금 중소·중견기업의 국내 IT 공고에서 AI/ML·게임 직군 비중으로 받친다. 같은 자리 중복 게시는 하나로."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY, _GROUPS, _group
    from .newscard import _NOT_JOB
    big = lambda c: _group(c) in _GROUPS     # 규모 칸이 비어 중소로 잡힌 대기업 계열(SK AX 등)은 뺀다
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, f.roles, co.display_name AS company, j.title, f.career_bucket
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격' AND f.company_size IN ('중소기업', '중견기업')
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"]) and not _NOT_JOB.search(r["title"])
                and not big(r["company"])]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co_name(r["company"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    ai = [r for r in rows if "AI/ML" in (r["roles"] or [])]
    game = [r for r in rows if "게임" in (r["roles"] or [])]
    ai_entry = sum(1 for r in ai if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in ai).most_common(3)
    pct = lambda a: round(100 * a / n) if n else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = (f"JD Viewer 모집중 IT 공고 · 국내 근무 중소·중견기업 {n:,}자리 · {_dot(asof)} · 같은 자리 중복 게시는 하나로 · "
            "직군은 제목·본문으로 가른 것(한 자리가 여러 직군일 수 있음)")
    slides = [
        {"type": "cover", "big": f"{pct(len(ai))}", "big_unit": "%", "lines": ["투자 절반이 AI 로 갔다", "중소·중견 채용은?"],
         "sub": f"중소·중견기업 IT 자리 {n:,}개 중 AI/ML 직군 {len(ai):,}개", "note": note},
        {"type": "table", "title": "상반기 벤처투자", "sub": "중기부 발표 · 뉴시스 보도 요약", "head": ["무엇", "숫자", ""],
         "rows": [["신규 투자", f"8.9조{wj}원", ""], ["작년보다", f"+54.3{wj}%", ""],
                  ["AI 업종 비중", f"51.2{wj}%", ""], ["게임 업종", f"−76.3{wj}%", ""]],
         "hi_col": 1, "note": "뉴시스 2026.8.19 보도(중소벤처기업부 2026 상반기 벤처투자 동향) 요약"},
        {"type": "bars", "title": "중소·중견 IT 자리 중", "sub": "직군별 모집중 자리(중복 게시는 하나로)",
         "rows": [{"label": "AI/ML", "value": len(ai), "display": f"{len(ai):,}", "unit": f"{pct(len(ai))}%", "hi": True},
                  {"label": "게임", "value": len(game), "display": f"{len(game):,}", "unit": f"{pct(len(game))}%", "hi": False}],
         "note": note},
        {"type": "stat", "title": "신입도 되는 AI 자리", "num": f"{ai_entry}", "unit": "개",
         "label": f"중소·중견 AI/ML 자리 {len(ai):,}개 중",
         "explain": "AI 자리가 많은 곳: " + " · ".join(f"**{c}** {k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"AI/ML **{len(ai):,}개** · 게임 **{len(game)}개**",
            "중소·중견 공고 전체는 프로필 링크에서", "스타트업 가고 싶은 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"상반기 벤처투자의 절반이 AI 로 갔습니다. 지금 중소·중견기업 IT 자리 {n:,}개 중 AI/ML 직군은 {len(ai):,}개({pct(len(ai))}%)입니다.",
        f"· 신입도 되는 AI 자리 {ai_entry}개\n· 게임 직군 {len(game)}개({pct(len(game))}%)\n"
        "· AI 자리가 많은 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "뉴시스는 중소벤처기업부 발표를 인용해 상반기 신규 벤처투자가 8조 8,676억 원으로 작년보다 54.3% 늘었고, "
        "그중 51.2%가 AI 업종에 쏠린 반면 게임 업종은 76.3% 줄었다고 전했습니다.",
        "출처\nhttps://www.newsis.com/view/NISX20260819_0003754109",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무, 중소·중견기업) 기준. 직군은 공고 제목·본문으로 가른 것이고, "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "vc", "id": f"vc-{asof.replace('-', '')}", "title": "투자와 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "투자 절반이 AI 로 갔다, 중소·중견 채용은? — 저장해 두세요"}


#: AI 에이전트 쪽 말 — 그냥 'agent' 는 모니터링 에이전트·user agent 와 겹쳐 AI·LLM 이 붙거나 개발·설계와 함께일 때만 센다
_AGENT_KW = {"AI 에이전트": r"AI\s*(에이전트|agent)|LLM\s*(에이전트|agent)|agentic|(멀티|다중)\s*에이전트|multi[- ]agent|"
                           r"에이전트\s*(개발|설계|구축|오케스트)|agent\s*(개발|설계|구축|orchestrat|framework)",
             "RAG": r"(?<![A-Za-z])RAG(?![A-Za-z])|GraphRAG",
             "MCP": r"(?<![A-Za-z])MCP(?![A-Za-z])|Model\s*Context\s*Protocol",
             "LangChain 계열": r"LangChain|LangGraph"}       # 막대 이름 칸에 'LangChain·LangGraph' 가 잘렸다


def build_agent() -> dict:
    """[AI 에이전트 채용] 릴스 — 리눅스재단이 MCP·goose·AGENTS.md 로 Agentic AI Foundation 을 세운 발표(2025.12.9)와,
    지금 국내 IT 공고의 제목·업무·자격·우대에 에이전트·RAG·MCP 를 적은 자리. 같은 자리 중복 게시는 하나로."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    from .newscard import _NOT_JOB
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket,
                              concat_ws(' ', j.title, j.main_tasks, j.qualifications, j.preferences) AS body
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"]) and not _NOT_JOB.search(r["title"])]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co_name(r["company"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    hit = {k: [r for r in rows if re.search(rx, r["body"] or "", re.I)] for k, rx in _AGENT_KW.items()}
    anyr = [r for r in rows if any(re.search(rx, r["body"] or "", re.I) for rx in _AGENT_KW.values())]
    entry = sum(1 for r in anyr if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in anyr).most_common(3)
    pct = lambda a: round(100 * a / n) if n else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}자리 · {_dot(asof)} · 제목·업무·자격·우대에 적힌 것만 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "big": f"{len(anyr):,}", "big_unit": "개", "lines": ["에이전트 표준이 생긴 해", "에이전트 개발 자리"],
         "sub": f"AI 에이전트·RAG·MCP·LangChain 을 적은 국내 IT 자리 ({pct(len(anyr))}%)", "note": note},
        {"type": "table", "title": "Agentic AI Foundation", "sub": "리눅스재단 발표 요약", "head": ["무엇", "내용", ""],
         "rows": [["언제", "2025.12.9", ""], ["창립 프로젝트", "MCP · goose · AGENTS.md", ""], ["만든 곳", "Anthropic · Block · OpenAI", ""]],
         "hi_col": 1, "note": "Linux Foundation 보도자료 2025.12.9 요약"},
        {"type": "bars", "title": "공고에 적힌 말", "sub": "그 말이 나온 국내 IT 자리 수",
         "rows": [{"label": k, "value": len(v), "display": f"{len(v):,}", "unit": "개", "hi": k == "MCP"}
                  for k, v in sorted(hit.items(), key=lambda kv: -len(kv[1]))], "note": note},
        {"type": "stat", "title": "신입도 되는 에이전트 자리", "num": f"{entry}", "unit": "개", "label": f"{len(anyr):,}개 중",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}** {k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {len(v):,}" for k, v in sorted(hit.items(), key=lambda kv: -len(kv[1]))[:3]),
            "에이전트 공고 전체는 프로필 링크에서", "LLM 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"AI 에이전트·RAG·MCP·LangChain 을 적은 국내 IT 자리는 지금 {len(anyr):,}개({pct(len(anyr))}%)입니다(신입 가능 {entry}개).",
        "· 적힌 말: " + " · ".join(f"{k} {len(v):,}개" for k, v in sorted(hit.items(), key=lambda kv: -len(kv[1]))) + "\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "리눅스재단은 2025년 12월 9일 Anthropic 의 MCP, Block 의 goose, OpenAI 의 AGENTS.md 를 창립 프로젝트로 하는 "
        "Agentic AI Foundation 을 세운다고 발표했습니다. 에이전트를 만드는 방식에 공통 표준이 생기기 시작한 셈입니다.",
        "출처\nhttps://linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 제목·주요업무·자격요건·우대사항에 적힌 것만, 같은 자리 중복 게시는 하나로 셌습니다.",
    ])
    return {"kind": "agent", "id": f"agent-{asof.replace('-', '')}", "title": "AI 에이전트 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "에이전트 표준이 생긴 해, 에이전트 개발 자리는 — 저장해 두세요"}


#: TIOBE 2026년 10월 상위 6개 언어와 점수(%) — tiobe.com/tiobe-index 에서 옮긴 값. 공고 스택 이름은 우리 사전 표기로.
_TIOBE = [("Python", 19.23, ("Python",)), ("C", 11.33, ("C", "C/C++")), ("C++", 8.87, ("C++", "C/C++")),
          ("Java", 8.41, ("Java",)), ("C#", 3.79, ("C#",)), ("JavaScript", 2.77, ("JavaScript", "TypeScript"))]


def build_lang() -> dict:
    """[언어 순위 vs 공고] 쇼츠 — TIOBE 2026년 10월 순위(Python 19.23% 1위)와, 국내 IT 공고가 실제로 적은 언어.
    JavaScript 는 TypeScript 를 함께 센다(같은 생태계). 같은 자리 중복 게시는 하나로."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY
    from .newscard import _NOT_JOB
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"]) and not _NOT_JOB.search(r["title"])]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co_name(r["company"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    ours = {name: sum(1 for r in rows if set(r["stacks"] or []) & set(keys)) for name, _, keys in _TIOBE}
    rank = sorted(ours.items(), key=lambda kv: -kv[1])
    pct = lambda a: round(100 * a / n) if n else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = (f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · "
            "JavaScript 는 TypeScript 포함 · 같은 자리 중복 게시는 하나로")
    slides = [
        {"type": "cover", "big": "19.23", "big_unit": "%", "lines": ["인기 1위 Python", "국내 공고에서는?"],
         "sub": "TIOBE 2026년 10월 Python 점수", "note": "TIOBE Index 2026년 10월"},
        {"type": "table", "title": "TIOBE 10월 순위", "sub": "검색 엔진 기반 인기 지수", "head": ["순위", "언어", "점수"],
         "rows": [[f"{i}", name, f"{score}{wj}%"] for i, (name, score, _) in enumerate(_TIOBE, 1)],
         "hi_col": 2, "note": "tiobe.com/tiobe-index · 2026년 10월"},
        {"type": "bars", "title": "국내 공고가 적은 언어", "sub": "그 언어를 적은 국내 IT 자리 수",
         "rows": [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0}
                  for i, (k, v) in enumerate(rank)], "note": note},
        {"type": "stat", "title": f"국내 1위는 {rank[0][0]}", "num": f"{pct(rank[0][1])}", "unit": "%",
         "label": f"국내 IT 자리 {n:,}개 중 {rank[0][1]:,}개",
         "explain": f"TIOBE 2위 C 는 국내 공고에서 {[k for k, _ in rank].index('C') + 1}위"
                    f"({ours['C']:,}{wj}개). 세계 인기와 국내 채용은 다르다.", "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v:,}" for k, v in rank[:3]),
            "언어별 공고 전체는 프로필 링크에서", "어떤 언어 공부할지 고민하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"TIOBE 10월 순위에서 Python 이 19.23%로 1위입니다. 국내 IT 공고 {n:,}자리가 적은 언어로 다시 줄을 세웠어요.",
        "· 국내 공고: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in rank),
        "· TIOBE 2026년 10월: " + " · ".join(f"{i}. {name} {score}%" for i, (name, score, _) in enumerate(_TIOBE, 1)),
        "TIOBE 는 검색 엔진 결과로 매기는 인기 지수라 채용 수요와는 다릅니다. 이달 TIOBE 는 Julia 가 다시 20위 안에 들었다고 짚었습니다.",
        "출처\nhttps://www.tiobe.com/tiobe-index/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, JavaScript 는 TypeScript 를 함께, "
        "C·C++ 는 'C/C++' 표기를 양쪽에 셌습니다.",
    ])
    return {"kind": "lang", "id": f"lang-{asof.replace('-', '')}", "title": "언어 순위 vs 공고",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 1.8,
            "reel_lead": "인기 1위 Python, 국내 공고에서는? — 저장해 두세요"}


#: 모바일 공고의 기술 — 우리 스택 사전 표기
#: Swift 만 세면 iOS 를 'iOS' 로만 적은 공고가 빠진다 — 플랫폼 단위로 묶는다
_MOBILE_STACK = [("Android", ("Android", "Kotlin")), ("iOS", ("iOS", "Swift")), ("Flutter", ("Flutter", "Dart")),
                 ("React Native", ("React Native",))]


def build_mobile() -> dict:
    """[모바일 채용] 릴스 — Kotlin 최신 2.4.21(kotlinlang.org 2026.10.8)을 계기로, 지금 국내 모바일 직군 공고가
    어떤 기술을 적었나(Kotlin·Swift·Flutter·React Native). 같은 자리 중복 게시는 하나로."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY, _SI_STAFF
    from .newscard import _NOT_JOB
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, co.display_name AS company, j.title, f.career_bucket
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE '모바일' = ANY(f.roles) AND coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"]) and not _NOT_JOB.search(r["title"])
                and not (_SI_STAFF.search(r["title"]) and "정규직" not in r["title"])]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co_name(r["company"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    by = {name: sum(1 for r in rows if set(r["stacks"] or []) & set(keys)) for name, keys in _MOBILE_STACK}
    rank = sorted(by.items(), key=lambda kv: -kv[1])
    entry = sum(1 for r in rows if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in rows).most_common(3)
    pct = lambda a: round(100 * a / n) if n else 0
    asof = date.today().isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 모바일 직군 공고 · 국내 근무 {n:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["Kotlin 2.4.21 나온 달", "모바일 개발 자리는"],
         "sub": "국내 근무 모바일 직군 모집중 자리", "note": note},
        {"type": "table", "title": "Kotlin 은 지금", "sub": "kotlinlang.org 릴리스 기록", "head": ["무엇", "언제", ""],
         "rows": [["최신 안정판", "2.4.21", ""], ["나온 날", "2026.10.8", ""]],
         "hi_col": 1, "note": "kotlinlang.org/docs/releases"},
        {"type": "bars", "title": "모바일 공고가 적은 플랫폼", "sub": "Android=Android·Kotlin, iOS=iOS·Swift 를 적은 자리",
         "rows": [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0}
                  for i, (k, v) in enumerate(rank)], "note": note},
        {"type": "stat", "title": "신입도 되는 모바일 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}** {k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v:,}" for k, v in rank[:3]),
            "모바일 공고 전체는 프로필 링크에서", "앱 개발 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"Kotlin 2.4.21 이 10월 8일 나왔습니다. 지금 국내 모바일 개발 자리는 {n:,}개(신입 가능 {entry}개)입니다.",
        "· 모바일 공고에 적힌 플랫폼: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in rank) + "\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "kotlinlang.org 릴리스 기록에 따르면 지금 최신 안정판은 2.4.21(2.4.20 의 버그 수정판)입니다.",
        "출처\nhttps://kotlinlang.org/docs/releases.html",
        f"{_dot(asof)} JD Viewer 모집중 모바일 직군 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고 Android 는 Kotlin, iOS 는 Swift, Flutter 는 Dart 를 함께 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "mobile", "id": f"mobile-{asof.replace('-', '')}", "title": "모바일 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Kotlin 2.4.21 나온 달, 모바일 개발 자리는 — 저장해 두세요"}


def _it_rows() -> list[dict]:
    """지금 모집중인 국내 근무 IT 공고(헤드헌팅·SI 투입·비 IT·마감 지난 것 빼고, 같은 자리 중복은 하나로)."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    from .collection import _AGENCY, _FOREIGN_TAG, _SI_STAFF
    from .newscard import _NOT_JOB
    today = date.today()
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT f.stacks, f.roles, co.display_name AS company, j.title, f.career_bucket, j.deadline_on,
                              f.company_size AS size, j.id AS job_id
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                         JOIN job_facet f ON f.job_id = j.id JOIN company co ON co.id = j.company_id
                        WHERE coalesce(f.region, '') <> '해외·원격'
                          AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""")
        rows = [r for r in cur.fetchall() if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []})
                and not _AGENCY.search(r["company"] + " " + r["title"]) and not _NOT_JOB.search(r["title"])
                and not _FOREIGN_TAG.match(r["title"])
                and not (_SI_STAFF.search(r["title"]) and "정규직" not in r["title"])
                and not (r["deadline_on"] and r["deadline_on"] < today)]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co_name(r["company"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    return rows


def build_python() -> dict:
    """[파이썬 채용] 쇼츠 — Python 3.15.0(python.org 2026.10.9)을 계기로, 지금 국내 IT 공고 중 Python 을 적은 자리와
    그 자리가 어느 직군인가(한 자리가 여러 직군이면 각각 센다). 같은 자리 중복 게시는 하나로."""
    today = date.today()
    rows = _it_rows()
    total = len(rows)
    py = [r for r in rows if "Python" in (r["stacks"] or [])]
    n = len(py)
    roles = collections.Counter(x for r in py for x in set(r["roles"] or []) if x != "기타").most_common(6)
    entry = sum(1 for r in py if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in py).most_common(3)
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["Python 3.15 나온 달", "Python 을 적은 자리는"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}%", "note": note},
        {"type": "table", "title": "Python 은 지금", "sub": "python.org 내려받기 페이지", "head": ["무엇", "언제", ""],
         "rows": [["새 판", "3.15.0", ""], ["나온 날", "2026.10.9", ""], ["3.14 줄 최신", "3.14.8", ""]],
         "hi_col": 1, "note": "python.org/downloads"},
        {"type": "bars", "title": "Python 자리는 어느 직군", "sub": "한 자리가 여러 직군이면 각각 셌다",
         "rows": [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0}
                  for i, (k, v) in enumerate(roles)], "note": note},
        {"type": "stat", "title": "신입도 되는 Python 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}**\u00a0{k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v:,}" for k, v in roles[:3]),
            "Python 공고 전체는 프로필 링크에서", "파이썬 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"Python 3.15.0 이 10월 9일 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Python 을 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 어느 직군: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in roles) + "\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "python.org 내려받기 페이지에 따르면 3.15.0 은 10월 9일 나왔고, 3.14 줄은 9월 30일 3.14.8 이 최신입니다.",
        "출처\nhttps://www.python.org/downloads/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 한 자리가 여러 직군에 걸치면 각각 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "python", "id": f"python-{asof.replace('-', '')}", "title": "파이썬 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Python 3.15 나온 달, Python 을 적은 자리는 — 저장해 두세요"}


_NODE = ("Node.js", "NestJS", "Express")
_JS_SIDE = {"JavaScript", "TypeScript", "React", "Vue.js", "Vue", "Next.js", "Nuxt", "React Native", "GraphQL", "Angular", "Svelte"}


def build_node() -> dict:
    """[Node.js 채용] 릴스 — Node.js 릴리스 표(nodejs.org: 26 Current 2026.5.5 · 24·22 LTS)를 계기로, 지금 국내 IT 공고 중
    Node.js(NestJS·Express 포함)를 적은 자리와 직군·같이 적은 기술. 같은 자리 중복 게시는 하나로."""
    today = date.today()
    rows = _it_rows()
    total = len(rows)
    # 'PCI Express' 를 Express 로 뽑은 반도체 공고(엑시나 SoC 설계·CXL, 2026-10-20)가 10건 섞였다.
    # Express 는 Node.js 나 JS 쪽 기술과 같이 적었을 때만 센다.
    nd = [r for r in rows if set(r["stacks"] or []) & {"Node.js", "NestJS"}
          or ("Express" in (r["stacks"] or []) and set(r["stacks"] or []) & _JS_SIDE)]
    n = len(nd)
    roles = collections.Counter(x for r in nd for x in set(r["roles"] or []) if x != "기타").most_common(5)
    with_ = collections.Counter(x for r in nd for x in set(r["stacks"] or []) if x not in _NODE).most_common(5)
    entry = sum(1 for r in nd if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in nd).most_common(3)
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    bars = lambda rs: [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0} for i, (k, v) in enumerate(rs)]
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["Node.js 26 시대", "Node.js 를 적은 자리는"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}% · NestJS·Express 포함", "note": note},
        {"type": "table", "title": "Node.js 는 지금", "sub": "nodejs.org 릴리스 표", "head": ["판", "상태", ""],
         "rows": [["26", "Current · 2026.5.5 첫 출시", ""], ["24 Krypton", "LTS", ""], ["22 Jod", "LTS", ""]],
         "hi_col": 1, "note": "nodejs.org/en/about/previous-releases"},
        {"type": "bars", "title": "Node.js 자리는 어느 직군", "sub": "한 자리가 여러 직군이면 각각 셌다", "rows": bars(roles), "note": note},
        {"type": "bars", "title": "같이 적은 기술", "sub": f"Node.js 자리 {n:,}개 중", "rows": bars(with_), "note": note},
        {"type": "stat", "title": "신입도 되는 Node.js 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}**\u00a0{k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v:,}" for k, v in with_[:3]),
            "Node.js 공고 전체는 프로필 링크에서", "JS 백엔드 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"지금 국내 IT 자리 {total:,}개 중 Node.js(NestJS·Express 포함)를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 어느 직군: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in roles) + "\n"
        "· 같이 적은 기술: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in with_) + "\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "nodejs.org 릴리스 표에 따르면 지금 Current 는 2026년 5월 5일 처음 나온 Node.js 26 이고, 24(Krypton)·22(Jod)가 LTS 입니다.",
        "출처\nhttps://nodejs.org/en/about/previous-releases",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 한 자리가 여러 직군에 걸치면 각각 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "node", "id": f"node-{asof.replace('-', '')}", "title": "Node.js 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Node.js 26 시대, Node.js 를 적은 자리는 — 저장해 두세요"}


_LANGS = ("Python", "Java", "C++", "Go", "Kotlin", "Rust")


def build_rust() -> dict:
    """[Rust 채용] 쇼츠 — Rust 1.99.0(2026.10.1)·1.99.1(10.15, blog.rust-lang.org)을 계기로, 지금 국내 IT 공고 중
    Rust 를 적은 자리가 다른 언어에 견줘 얼마나 되나 · 같이 적은 기술 · 신입 가능. 같은 자리 중복 게시는 하나로."""
    today = date.today()
    rows = _it_rows()
    total = len(rows)
    has = lambda r, k: k in (r["stacks"] or []) or (k == "C++" and "C/C++" in (r["stacks"] or []))
    langs = sorted(((k, sum(1 for r in rows if has(r, k))) for k in _LANGS), key=lambda kv: -kv[1])
    rs = [r for r in rows if has(r, "Rust")]
    n = len(rs)
    with_ = collections.Counter(x for r in rs for x in set(r["stacks"] or []) if x not in ("Rust", "C/C++")).most_common(5)
    entry = sum(1 for r in rs if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in rs).most_common(3)
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    bars = lambda xs, base: [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v, base)}%", "hi": k == "Rust" or (base == n and i == 0)}
                             for i, (k, v) in enumerate(xs)]
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["Rust 1.99 나온 달", "Rust 를 적은 자리는"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}%", "note": note},
        {"type": "table", "title": "Rust 는 지금", "sub": "Rust 공식 블로그 릴리스 글", "head": ["판", "나온 날", ""],
         "rows": [["1.99.0", "2026.10.1", ""], ["1.99.1", "2026.10.15", ""]],
         "hi_col": 1, "note": "blog.rust-lang.org/releases"},
        {"type": "bars", "title": "언어별로 견주면", "sub": "그 언어를 적은 국내 IT 자리", "rows": bars(langs, total), "note": note},
        {"type": "bars", "title": "Rust 와 같이 적은 기술", "sub": f"Rust 자리 {n:,}개 중", "rows": bars(with_, n), "note": note},
        {"type": "stat", "title": "신입도 되는 Rust 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}**\u00a0{k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v:,}" for k, v in with_[:3]),
            "Rust 공고 전체는 프로필 링크에서", "Rust 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"Rust 1.99 가 10월에 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Rust 를 적은 자리는 {n:,}개({pct(n, total)}%), 그중 신입 가능 {entry}개입니다.",
        "· 언어별 자리: " + " · ".join(f"{k} {v:,}개" for k, v in langs) + "\n"
        "· Rust 와 같이 적은 기술: " + " · ".join(f"{k} {v}개" for k, v in with_) + "\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "Rust 공식 블로그에 따르면 1.99.0 은 10월 1일, 1.99.1 은 10월 15일 나왔습니다.",
        "출처\nhttps://blog.rust-lang.org/releases/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, C++ 는 C/C++ 표기를 함께 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "rust", "id": f"rust-{asof.replace('-', '')}", "title": "Rust 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Rust 1.99 나온 달, Rust 를 적은 자리는 — 저장해 두세요"}


def build_java() -> dict:
    """[Java 채용] 릴스 — JDK 27 정식판(openjdk.org, 2026.9.15)을 계기로, 지금 국내 IT 공고 중 Java 를 적은 자리·직군·
    같이 적은 기술·신입 가능. 같은 자리 중복 게시는 하나로."""
    today = date.today()
    rows = _it_rows()
    total = len(rows)
    jv = [r for r in rows if "Java" in (r["stacks"] or [])]
    n = len(jv)
    roles = collections.Counter(x for r in jv for x in set(r["roles"] or []) if x != "기타").most_common(5)
    with_ = collections.Counter(x for r in jv for x in set(r["stacks"] or []) if x != "Java").most_common(5)
    kt = sum(1 for r in jv if "Kotlin" in (r["stacks"] or []))
    entry = sum(1 for r in jv if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in jv).most_common(3)
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    bars = lambda xs: [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0} for i, (k, v) in enumerate(xs)]
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["JDK 27 나온 가을", "Java 를 적은 자리는"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}%", "note": note},
        {"type": "table", "title": "Java 는 지금", "sub": "OpenJDK 프로젝트 페이지", "head": ["판", "상태", ""],
         "rows": [["JDK 27", "정식판 · 2026.9.15", ""], ["JDK 28", "개발 중", ""]],
         "hi_col": 1, "note": "openjdk.org/projects/jdk"},
        {"type": "bars", "title": "Java 자리는 어느 직군", "sub": "한 자리가 여러 직군이면 각각 셌다", "rows": bars(roles), "note": note},
        {"type": "bars", "title": "Java 와 같이 적은 기술", "sub": f"Java 자리 {n:,}개 중", "rows": bars(with_), "note": note},
        {"type": "stat", "title": "신입도 되는 Java 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}**\u00a0{k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"Java 자리 중 Kotlin 도 적은 곳 **{kt:,}**개({pct(kt)}%)",
            "Java 공고 전체는 프로필 링크에서", "자바 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"JDK 27 이 9월 15일 정식판으로 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Java 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 어느 직군: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in roles) + "\n"
        "· 같이 적은 기술: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in with_) + "\n"
        f"· Kotlin 도 함께 적은 자리: {kt:,}개({pct(kt)}%)\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "OpenJDK 프로젝트 페이지에 따르면 JDK 27 은 2026년 9월 15일 정식판(GA)이 됐고, 지금은 JDK 28 을 만들고 있습니다.",
        "출처\nhttps://openjdk.org/projects/jdk/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 한 자리가 여러 직군에 걸치면 각각 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "java", "id": f"java-{asof.replace('-', '')}", "title": "Java 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "JDK 27 나온 가을, Java 를 적은 자리는 — 저장해 두세요"}


#: 공고 글에서 찾는 iOS 도구 — 기술 칩(job_facet.stacks)에는 SwiftUI·UIKit 같은 칸이 없다
_IOS_TOOLS = [("Objective-C", r"Objective[- ]?C"), ("SwiftUI", r"SwiftUI"), ("Tuist", r"Tuist"),
              ("async/await", r"async\s*/\s*await|Swift\s*Concurrency"), ("RxSwift", r"RxSwift"),
              ("UIKit", r"UIKit"), ("Combine", r"\bCombine\b")]


def build_swift() -> dict:
    """[Swift 채용] 쇼츠 — Swift 6.4(swift.org 2026.9.15)를 계기로, 지금 국내 IT 공고 중 Swift 를 적은 자리와 그 공고 글에
    적힌 iOS 도구(SwiftUI·UIKit·Objective-C…). 기술 칩에 'iOS' 만 붙은 크로스플랫폼·SDK 공고는 빼고, 글이나 칩에 Swift 가
    있는 자리만 센다. 같은 자리 중복 게시는 하나로."""
    sys.path.insert(0, str(ROOT / "catch_capture"))
    from store.db.conn import cursor
    today = date.today()
    rows = _it_rows()
    total = len(rows)
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT id, concat_ws(' ', title, main_tasks::text, qualifications::text, preferences::text, full_jd) AS t
                         FROM job WHERE id = ANY(%s)""", ([r["job_id"] for r in rows],))
        text = {r["id"]: r["t"] or "" for r in cur.fetchall()}
    sw = [r for r in rows if "Swift" in (r["stacks"] or []) or re.search(r"\bSwift(UI)?\b", text.get(r["job_id"], ""))]
    n = len(sw)
    tools = sorted(((k, sum(1 for r in sw if re.search(rx, text.get(r["job_id"], ""), re.I if k != "Combine" else 0)))
                    for k, rx in _IOS_TOOLS), key=lambda kv: -kv[1])
    entry = sum(1 for r in sw if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in sw).most_common(3)
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {_dot(asof)} · 공고 글에 적힌 낱말로 셈 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["Swift 6.4 나온 가을", "Swift 를 적은 자리는"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}%", "note": note},
        {"type": "table", "title": "Swift 는 지금", "sub": "swift.org 블로그", "head": ["무엇", "언제", ""],
         "rows": [["Swift 6.4 출시", "2026.9.15", ""], ["9월 소식 정리 글", "2026.10.8", ""]],
         "hi_col": 1, "note": "swift.org/blog"},
        {"type": "bars", "title": "Swift 공고 글에 적힌 도구", "sub": f"Swift 자리 {n:,}개 중 그 낱말이 나온 곳",
         "rows": [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0} for i, (k, v) in enumerate(tools)],
         "note": note},
        {"type": "stat", "title": "신입도 되는 Swift 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}**\u00a0{k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            " · ".join(f"**{k}** {v}" for k, v in tools[:3]),
            "iOS 공고 전체는 프로필 링크에서", "iOS 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"Swift 6.4 가 9월 15일 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Swift 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 그 공고 글에 적힌 도구: " + " · ".join(f"{k} {v}개({pct(v)}%)" for k, v in tools) + "\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "swift.org 블로그에 따르면 Swift 6.4 는 9월 15일 나왔고, 10월 8일에 9월 소식 정리 글이 올라왔습니다.",
        "출처\nhttps://www.swift.org/blog/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 공고 제목·본문이나 기술 칩에 Swift 가 있는 자리만 셌고(기술 칩에 iOS 만 붙은 "
        "크로스플랫폼·SDK 공고는 뺐습니다), 도구는 공고 글에 그 낱말이 나온 자리입니다. 같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "swift", "id": f"swift-{asof.replace('-', '')}", "title": "Swift 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Swift 6.4 나온 가을, Swift 를 적은 자리는 — 저장해 두세요"}


def build_docker() -> dict:
    """[Docker 채용] 릴스 — Docker Engine 29.9.0(2026.10.8)·29.9.1(10.14, docs.docker.com 릴리스 노트)을 계기로, 지금 국내 IT
    공고 중 Docker 를 적은 자리·직군·같이 적은 기술(그중 Kubernetes 까지 적은 자리)·신입 가능. 같은 자리 중복 게시는 하나로."""
    today = date.today()
    rows = _it_rows()
    total = len(rows)
    dk = [r for r in rows if "Docker" in (r["stacks"] or [])]
    n = len(dk)
    roles = collections.Counter(x for r in dk for x in set(r["roles"] or []) if x != "기타").most_common(5)
    with_ = collections.Counter(x for r in dk for x in set(r["stacks"] or []) if x != "Docker").most_common(5)
    k8 = sum(1 for r in dk if "Kubernetes" in (r["stacks"] or []))
    entry = sum(1 for r in dk if r["career_bucket"] == "신입/무관")
    cos = collections.Counter(_co_name(r["company"]) for r in dk).most_common(3)
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    asof = today.isoformat()
    wj = "\u2060"
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {_dot(asof)} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    bars = lambda xs: [{"label": k, "value": v, "display": f"{v:,}", "unit": f"{pct(v)}%", "hi": i == 0} for i, (k, v) in enumerate(xs)]
    slides = [
        {"type": "cover", "big": f"{n:,}", "big_unit": "개", "lines": ["Docker 29.9 나온 달", "Docker 를 적은 자리는"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}%", "note": note},
        {"type": "table", "title": "Docker Engine 은 지금", "sub": "docs.docker.com 릴리스 노트", "head": ["판", "나온 날", ""],
         "rows": [["29.9.1", "2026.10.14", ""], ["29.9.0", "2026.10.8", ""], ["29.8.2", "2026.9.30", ""]],
         "hi_col": 1, "note": "docs.docker.com/engine/release-notes"},
        {"type": "bars", "title": "Docker 자리는 어느 직군", "sub": "한 자리가 여러 직군이면 각각 셌다", "rows": bars(roles), "note": note},
        {"type": "bars", "title": "Docker 와 같이 적은 기술", "sub": f"Docker 자리 {n:,}개 중", "rows": bars(with_), "note": note},
        {"type": "stat", "title": "신입도 되는 Docker 자리", "num": f"{entry}", "unit": "개", "label": f"{n:,}개 중 {pct(entry)}%",
         "explain": "많이 뽑는 곳: " + " · ".join(f"**{c}**\u00a0{k}{wj}개" for c, k in cos), "note": note},
        {"type": "end", "title": "저장해 두고", "lines": [
            f"Docker 자리 중 Kubernetes 까지 적은 곳 **{k8:,}**개({pct(k8)}%)",
            "Docker 공고 전체는 프로필 링크에서", "컨테이너 공부하는 친구에게 보내 주세요"], "note": note},
    ]
    caption = "\n\n".join([
        f"Docker Engine 29.9 가 10월에 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Docker 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 어느 직군: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in roles) + "\n"
        "· 같이 적은 기술: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in with_) + "\n"
        f"· Kubernetes 까지 적은 자리: {k8:,}개({pct(k8)}%)\n"
        "· 많이 뽑는 곳: " + " · ".join(f"{c} {k}개" for c, k in cos),
        "Docker 릴리스 노트에 따르면 Engine 29.9.0 은 10월 8일, 29.9.1 은 10월 14일 나왔습니다.",
        "출처\nhttps://docs.docker.com/engine/release-notes/",
        f"{_dot(asof)} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 한 자리가 여러 직군에 걸치면 각각 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"kind": "docker", "id": f"docker-{asof.replace('-', '')}", "title": "Docker 채용",
            "slides": slides, "caption": caption, "jobs": [], "reel_hold": 2.0,
            "reel_lead": "Docker 29.9 나온 달, Docker 를 적은 자리는 — 저장해 두세요"}


REEL = (1080, 1920)   # 릴스는 9:16 으로 다시 찍는다 — 4:5 판을 영상에 얹으면 위아래가 검은 띠가 된다


def render(post: dict, size: tuple[int, int] = (1080, 1350)) -> list[Path]:
    from .render import _page_maker
    theme, series = THEMES[post["kind"]], SERIES[post["kind"]]
    dest = OUT / (post["id"] + ("-reel" if size == REEL else ""))
    dest.mkdir(parents=True, exist_ok=True)
    paths, n = [], len(post["slides"])
    for i, s in enumerate(post["slides"], 1):
        data = {"theme": theme, "series": series, "page": f"{i} / {n}", "slide": s, "size": list(size)}
        html = TEMPLATE.read_text(encoding="utf-8").replace(
            "/*__DATA__*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
        page = _page_maker().new_page(viewport={"width": size[0], "height": size[1]})
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
    ap.add_argument("kind", choices=["stack", "rates", "guide", "term", "interview", "qa", "jd", "same", "roadmap",
                                     "weekly", "signal", "talent", "pay", "perk", "map", "welcome", "gongchae", "lunch", "kit",
                                     "contra", "ai-entry", "game", "security", "cert", "aitool", "mobility", "pangyo", "health", "junior", "usvs", "gap", "cloud", "paywish", "robot", "spring", "vc", "agent", "lang", "mobile", "python", "node", "rust", "java", "swift", "docker"])
    ap.add_argument("company", nargs="?", default="")
    ap.add_argument("--dry", action="store_true", help="찍기만 하고 승인함에 넣지 않는다")
    ap.add_argument("--reel", action="store_true",
                    help="9:16 으로 다시 찍어 릴스 mp4 를 만든다(같은 내용을 캐러셀로도 올리면 중복 게시다)")
    ap.add_argument("--story", action="store_true", help="9:16 스토리 판으로 찍는다(영상 아님 · 승인함에 넣지 않는다)")
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
    elif args.kind == "map":
        a, _, b = (args.company or "판교·분당:성수").partition(":")
        post = build_commute(a, b or "성수")
    elif args.kind == "lunch":
        post = build_lunch(args.company or "pangyo")
    elif args.kind == "kit":
        post = (build_kit_history("reel" if args.reel else "story" if args.story else "feed")
                if args.company == "history" else build_welcomekit())
    elif args.kind == "ai-entry":
        post = build_ai_entry()
    elif args.kind == "game":
        post = build_game()
    elif args.kind == "security":
        post = build_security()
    elif args.kind == "cert":
        post = build_cert()
    elif args.kind == "aitool":
        post = build_aitool()
    elif args.kind == "mobility":
        post = build_mobility()
    elif args.kind == "pangyo":
        post = build_pangyo()
    elif args.kind == "health":
        post = build_health()
    elif args.kind == "junior":
        post = build_junior()
    elif args.kind == "usvs":
        post = build_usvs()
    elif args.kind == "gap":
        post = build_gap()
    elif args.kind == "cloud":
        post = build_cloud()
    elif args.kind == "paywish":
        post = build_paywish()
    elif args.kind == "robot":
        post = build_robot()
    elif args.kind == "spring":
        post = build_spring()
    elif args.kind == "vc":
        post = build_vc()
    elif args.kind == "agent":
        post = build_agent()
    elif args.kind == "lang":
        post = build_lang()
    elif args.kind == "mobile":
        post = build_mobile()
    elif args.kind == "python":
        post = build_python()
    elif args.kind == "node":
        post = build_node()
    elif args.kind == "rust":
        post = build_rust()
    elif args.kind == "java":
        post = build_java()
    elif args.kind == "swift":
        post = build_swift()
    elif args.kind == "docker":
        post = build_docker()
    elif args.kind in ("pay", "perk", "welcome", "gongchae", "contra"):
        post = {"pay": build_pay_newgrad, "perk": build_perks, "welcome": build_welcome,
                "gongchae": build_gongchae, "contra": build_contra}[args.kind]()
    elif args.kind in ("jd", "same", "roadmap", "weekly", "signal"):
        post = {"jd": build_jd_translate, "same": build_same_role, "roadmap": build_roadmap,
                "weekly": build_weekly, "signal": build_signals}[args.kind]()
    else:
        post = build_stack() if args.kind == "stack" else build_rates()
    if args.reel and post.get("reel_slides"):   # 릴스는 따로 줄인 판이 있으면 그것으로
        post = {**post, "slides": post["reel_slides"]}
    if args.reel and post.get("reel_lead"):     # 릴스 캡션 첫 줄 — 영상이 부른 행동(저장·댓글)을 캡션이 이어받는다
        post = {**post, "caption": post["reel_lead"] + "\n\n" + post["caption"]}
    try:
        paths = render(post, REEL if (args.reel or args.story) else (1080, 1350))
    finally:
        shutdown()
    if args.reel:
        from .video import build
        hold = post.get("reel_hold", 2.6)   # 데이터 판은 공고 판보다 글이 많다 — 1.8초면 못 읽는다
        mp4 = build(paths, paths[0].parent / "reel.mp4", hold=hold, motion=post.get("motion", 0.0),
                    audio=Path(post["audio"]) if post.get("audio") else None)
        print(f"[series] 릴스 → {mp4}")
    print(f"[series] {post['id']} {len(paths)}장 → {paths[0].parent}")
    # 손으로 올릴 때(앱·웹) 붙여 넣을 캡션 — 승인함에 넣는 것과 같은 글.
    tags = " ".join(f"#{t}" for t in TAGS[post["kind"]])
    (paths[0].parent / "caption.txt").write_text(f"{post['caption']}\n\n{tags}", encoding="utf-8")
    if not args.dry and not args.story:
        print(f"[series] 승인함 → {approve(post, paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
