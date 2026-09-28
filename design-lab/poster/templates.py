"""템플릿 레지스트리 + 아주 작은 치환기.

템플릿은 그냥 HTML 파일이다(브라우저로 바로 열어 볼 수 있게). 문법은 셋뿐:
    {{key}} / {{a.b}}          값
    {{#if key}} ... {{/if}}    비어 있으면 통째로 지움 — '없는 정보는 안 그린다'
    {{#unless key}} ... {{/unless}}   그 반대(로고가 없을 때 이니셜 같은 대체물)
    {{#each list}} {{.}} {{/each}}   반복. {{@index}} 로 번호(1부터).
치수는 전부 vw/vh 라 캔버스 크기만 바꾸면 모든 포맷에 같은 판이 늘어난다.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

TPL_DIR = Path(__file__).resolve().parent / "templates"

# id → (파일, 이름, 출처가 된 레퍼런스, 한 줄 설명)
#
# 2026-09-17: 처음 네 틀(role_hero/swiss_white/info_grid/point_cards)을 여기서 뺐다.
# 레퍼런스를 그대로 옮긴 범용 판이라 회사가 색·글꼴로만 남았고, 그건 이 랩이
# "너무 AI 스럽다" 로 이미 한 번 버린 판이다(BRAND_RESEARCH.md 0절). 스튜디오에는
# 그 절차를 끝까지 밟은 회사 전용 판만 올린다. HTML 파일은 templates/ 에 그대로 두었다.
# engine:"frame" 은 /*__DATA__*/ + _frame.js 로 그리는 판이다. 치환기로는 못 그리므로
# render.html_for 가 carousel 로 넘긴다. company 는 이 판을 쓸 수 있는 공고의 회사 표기
# (jobs_index 의 company 와 정확히 같아야 한다 — 스튜디오가 이걸로 칩을 잠근다).
TEMPLATES: dict[str, dict] = {
    "brand_tossplace": {
        "file": "brand_tossplace.html",
        "engine": "frame",
        "company": ["토스플레이스"],
        "name": "토스플레이스",
        "ref": "front2-standing-screen",
        "note": "판이 토스 프론트 2 의 세로 화면이 된다. 하우징이 판을 두르고 위에 카메라 눈, 아래에 카드 삽입구.",
    },
    "brand_42dot": {
        "file": "brand_42dot.html",
        "engine": "frame",
        "company": ["포티투닷(42dot)", "포티투닷 (42dot)", "포티투닷"],
        "name": "포티투닷",
        "ref": "ascii-42-asterisk",
        "note": "About 페이지의 ASCII 코드표. Code 42 에서 멈추고 그 자리 글자가 * 로 드러난다 — 회사 이름이 곧 이 장치다.",
    },
    "brand_ridi": {
        "file": "brand_ridi.html",
        "engine": "frame",
        "company": ["리디(RIDI)", "리디"],
        "name": "리디",
        "ref": "ridibatang-typesetting",
        "note": "판 전체가 리디바탕으로 짜인다. 리디가 전자책을 위해 직접 만들어 푼 서체 — 굵기가 하나뿐이라 위계는 크기·여백으로만.",
    },
    "brand_bithumb": {
        "file": "brand_bithumb.html",
        "engine": "frame",
        "company": ["빗썸", "주식회사 빗썸"],
        "name": "빗썸",
        "ref": "locked-digit-slots",
        "note": "숫자가 자리칸에 잠긴다. Bithumb Trading Sans 는 숫자 열 개 폭이 전부 596/1000 로 같다 — 시세가 흔들리지 않게 깎은 서체다.",
    },
    "brand_miridih": {
        "file": "brand_miridih.html",
        "engine": "frame",
        "company": ["미리디", "(주)미리디"],
        "name": "미리디",
        "ref": "size-first-canvas",
        "note": "판이 자기 치수를 밝힌다. 미리캔버스에서 맨 처음 정하는 것은 그림도 글도 아니고 판의 크기다 — 자리가 글보다 먼저 있다.",
    },
    "brand_cjenm": {
        "file": "brand_cjenm.html",
        "engine": "frame",
        "company": ["씨제이이엔엠(CJ ENM)", "CJ ENM", "씨제이이엔엠"],
        "name": "씨제이이엔엠",
        "ref": "hypercube-structure",
        "note": "MAMA 트로피 하이퍼큐브의 구조 — 큐브 자리를 공고가 채우고 X 교차 기둥과 계단 받침이 받친다. 로고타이프는 그리지 않는다.",
    },
}

_VAR = re.compile(r"\{\{\s*([\w.@]+)\s*\}\}")
_IF = re.compile(r"\{\{#if\s+([\w.]+)\s*\}\}(.*?)\{\{/if\}\}", re.S)
_UNLESS = re.compile(r"\{\{#unless\s+([\w.]+)\s*\}\}(.*?)\{\{/unless\}\}", re.S)
_EACH = re.compile(r"\{\{#each\s+([\w.]+)\s*\}\}(.*?)\{\{/each\}\}", re.S)


def _lookup(ctx: dict, path: str):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _esc(v) -> str:
    if v is None or v is False:
        return ""
    if isinstance(v, (list, dict)):
        return html.escape(json.dumps(v, ensure_ascii=False))
    return html.escape(str(v))


def render_string(tpl: str, ctx: dict) -> str:
    def each(m):
        items = _lookup(ctx, m.group(1)) or []
        body = m.group(2)
        out = []
        for i, item in enumerate(items, 1):
            scope = dict(ctx)
            if isinstance(item, dict):
                scope.update(item)
            scope["."] = item
            scope["@index"] = i
            chunk = body.replace("{{.}}", _esc(item)).replace("{{@index}}", f"{i:02d}")
            out.append(render_string(chunk, scope))
        return "".join(out)

    def cond(m):
        val = _lookup(ctx, m.group(1))
        return render_string(m.group(2), ctx) if val else ""

    def anti(m):
        val = _lookup(ctx, m.group(1))
        return "" if val else render_string(m.group(2), ctx)

    tpl = _EACH.sub(each, tpl)
    tpl = _UNLESS.sub(anti, tpl)
    tpl = _IF.sub(cond, tpl)
    return _VAR.sub(lambda m: _esc(_lookup(ctx, m.group(1))), tpl)


def render(template_id: str, spec: dict, fmt: dict) -> str:
    """포스터 HTML 한 장. fmt 는 model.FORMATS 의 항목({'w','h'})."""
    meta = TEMPLATES.get(template_id)
    if not meta:
        raise KeyError(f"모르는 템플릿: {template_id}")
    tpl = (TPL_DIR / meta["file"]).read_text(encoding="utf-8")
    ctx = dict(spec)
    ctx["fmt"] = fmt
    ctx["orient"] = "landscape" if fmt["w"] >= fmt["h"] else "portrait"
    return render_string(tpl, ctx)


def listing() -> list[dict]:
    return [{"id": k, **v} for k, v in TEMPLATES.items()]
