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
TEMPLATES: dict[str, dict] = {
    "role_hero": {
        "file": "role_hero.html",
        "name": "직군이 주인공",
        "ref": "hire-03 (imago.xyz)",
        "note": "직군명을 화면 절반으로 키우고 위에 마감 한 줄. 회사는 오른쪽에 작게.",
    },
    "swiss_white": {
        "file": "swiss_white.html",
        "name": "여백이 브랜드",
        "ref": "hire-04 (df.designfever)",
        "note": "가운데 마크 하나, 정보는 네 귀퉁이로 흩는다. 정보량 적은 공고용.",
    },
    "info_grid": {
        "file": "info_grid.html",
        "name": "항목 그대로",
        "ref": "hire-05 (sddaejeon)",
        "note": "지원자격·우대사항·담당업무 라벨을 예쁜 말로 안 바꾸고 그대로 세운다.",
    },
    "point_cards": {
        "file": "point_cards.html",
        "name": "번호 카드",
        "ref": "detail-04 (design_j_d)",
        "note": "Point.01/02/03 으로 위치를 알려 준다. 캐러셀 2~4번째 장에 쓴다.",
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
