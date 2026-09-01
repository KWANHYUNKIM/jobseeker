#!/usr/bin/env python3
"""역설계 산출물 검증 — 사이트가 읽기 전에 형식이 깨졌는지 본다.

index.json 은 공개 사이트 메인이 통째로 읽는다. 한 글자 깨지면 회사 목록이 아니라
빈 화면이 뜨므로, 엔진이 매 사이클 끝에 이걸 돌린다.

    python engine/validate.py            # 전체 검사
    python engine/validate.py toss       # 회사 하나만
    python engine/validate.py --gaps     # 다음 사이클이 채울 곳 (대상 1건 + 참고 5건)
    python engine/validate.py --gaps-all # 보강 후보 전량

검사하는 것:
  - JSON 파싱, 필수 필드, enum 값(country/category/status/confidence)
  - index.companies 와 companies/*.json 의 불일치(누락·고아·필드 어긋남)
  - confidence=confirmed 인데 sources 가 비어 있는 주장 (PROMPT.md 5단계 규칙)
  - decisions 의 tradeoff 누락 (품질 규칙: 트레이드오프 없는 설명 금지)
  - connections 가 가리키는 feature key 가 실재하는지
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVENG = ROOT / "jd-viewer" / "public" / "reveng"
INDEX = REVENG / "index.json"
COMPANIES = REVENG / "companies"

COUNTRIES = {"KR", "US", "CN", "JP", "EU", "CA", "AU", "SG", "IN", "AE", "NG", "기타"}
CATEGORIES = {"핀테크", "커머스", "소셜", "메시징", "스트리밍", "검색", "광고",
              "모빌리티", "게임", "SaaS", "기타"}
STATUSES = {"in_progress", "done"}
CONFIDENCE = {"confirmed", "inferred", "unknown"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# index.companies[] 가 회사 파일과 일치해야 하는 필드. 사이트 메인이 이 값만 보고
# 카드를 그리므로, 상세와 어긋나면 목록과 상세가 다른 말을 하게 된다.
MIRRORED = ("name", "name_en", "country", "category", "status", "updated_at")


# 보강 후보의 우선순위 — PROMPT.md 2′단계의 사다리와 같은 순서다.
# 루프로 도는 엔진이 "다음에 뭘 하지"를 사람에게 묻지 않고 정하려면, 무엇이 얇은지를
# 기계가 같은 기준으로 매번 정렬해 줘야 한다.
# --gaps 가 대상 하나 말고 몇 건을 더 보여줄지. 루프의 맥락을 아끼려고 짧게 끊는다.
SHOW_NEXT = 5

# 이 날수가 지난 회사는 다시 들여다볼 때가 된 것으로 본다.
#
# 이 단이 있어야 루프가 루프다. 나머지 단은 전부 유한한 목록을 줄이는 일이라
# 다 줄이고 나면 돌 이유가 없어진다 — 그건 느린 배치 작업이지 루프가 아니다.
# 바깥(회사가 새로 쓰는 글)이 변하기 때문에 다시 볼 값이 생기는 것이고,
# 그 변화를 엔진이 알아채는 자리가 여기다.
STALE_DAYS = 14

# 큐에 유지할 회사 수.
#
# 후보 조사를 '큐가 비었을 때만' 돌리면 큐가 앞서 나가지 못한다 — 바닥 → 한 사이클
# 써서 하나 채움 → 다시 바닥이 반복되고, 팔 회사가 떨어질 때마다 사이클을 버린다.
# 재고를 미리 채워 두는 것과 같은 이치라 목표 수량을 두고 그 아래로 내려가면 채운다.
QUEUE_TARGET = 3
QUEUE_MD = ROOT / "engine" / "state" / "QUEUE.md"


def _queue_depth() -> int | None:
    """QUEUE.md 의 '## 대기' 표에 몇 곳이 남았는지. 못 읽으면 None.

    '## 보류' 와 '## 완료' 는 세지 않는다 — 지금 팔 수 있는 것만 큐다.
    """
    if not QUEUE_MD.exists():
        return None
    rows = 0
    in_wait = False
    for line in QUEUE_MD.read_text(encoding="utf-8").splitlines():
        st = line.strip()
        if st.startswith("## "):
            in_wait = st == "## 대기"
            continue
        if st.startswith("### "):      # '확인해 둔 후보' 는 검증 전이라 큐가 아니다
            in_wait = False
            continue
        if not in_wait or not st.startswith("|"):
            continue
        cells = [c.strip() for c in st.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set(cells[0]) <= {"-", ":", " "}:   # 표 구분선
            continue
        if cells[0] in ("회사",):               # 머리글
            continue
        rows += 1
    return rows

GAP_KINDS = {
    "decisions": (1, "결정을 쪼갠다 (STYLE.md 3번)"),
    "failure":   (2, "실패 경로 그림을 그린다 (STYLE.md 1번)"),
    "thinking":  (3, "결론 앞의 생각을 남긴다 (STYLE.md 5번)"),
    "tech":      (5, "도메인을 무슨 기술로 풀었는지까지 내린다 (STYLE.md 2번)"),
    "sources":   (6, "링크를 찾거나 등급을 inferred 로 내린다"),
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        # (우선순위, 종류, 위치, 무엇이 모자란가)
        self.gaps: list[tuple[int, str, str, str]] = []
        # 진행 중인 회사의 아직 안 판 도메인. 사다리에서 보강보다 위라 따로 담는다.
        self.wip: list[tuple[str, str]] = []
        # 다시 들여다볼 때가 된 회사 — (slug, updated_at, 지난 날수)
        self.stale: list[tuple[str, str, int]] = []
        # 지금 검사 중인 회사가 보류 상태인가. gap() 이 이 값을 보고 걸러 낸다.
        self._held = False

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    def gap(self, kind: str, where: str, msg: str) -> None:
        """보강 후보. 형식이 깨진 건 아니지만 아직 얇은 자리."""
        if self._held:
            return  # 보류 중인 회사는 손대지 않기로 한 곳이다
        self.gaps.append((GAP_KINDS[kind][0], kind, where, msg))


def _load(path: Path, r: Report) -> dict | None:
    if not path.exists():
        r.err(str(path.relative_to(ROOT)), "파일 없음")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.err(str(path.relative_to(ROOT)), f"JSON 파싱 실패 — {e}")
        return None


def _check_sources(node: dict, where: str, r: Report) -> None:
    """confirmed 주장에는 링크가 반드시 있어야 한다(PROMPT.md 5단계)."""
    conf = node.get("confidence")
    if conf is not None and conf not in CONFIDENCE:
        r.err(where, f"confidence 값이 이상하다: {conf!r}")
    if conf == "confirmed" and not node.get("sources"):
        r.err(where, "confirmed 인데 sources 가 비어 있다")
    for i, s in enumerate(node.get("sources") or []):
        if not s.get("url"):
            r.err(f"{where}.sources[{i}]", "url 없음")
        if not s.get("summary"):
            r.warn(f"{where}.sources[{i}]", "한 줄 요약 없음")


UI_ELEMENT_TYPES = {
    "appbar", "label", "text", "input", "chips", "amount",
    "button", "rows", "tabs", "card", "divider", "spacer",
}


def _check_ui(ui: dict, where: str, r: Report) -> None:
    """화면 도해(UiSketch) — 사용자가 보는 자리에 설명을 거는 그림.

    실제 화면 캡처가 아니라 재구성이라, 형식이 열려 있으면 회사마다 제각각이 되고
    그 순간 이 도해는 '그 회사 화면' 이 아니라 '그린 사람의 취향' 이 된다.
    그래서 요소 종류를 뷰어가 아는 것으로 묶어 두고, 번호가 서로 맞는지만 본다.
    """
    if not ui.get("title"):
        r.err(where, "title 없음")
    if not ui.get("question"):
        r.warn(where, "이 도해가 답하는 질문이 없다 — 없으면 그 그림은 뺀다(STYLE.md 1번)")

    pins = ui.get("pins") or []
    if not pins:
        r.err(where, "pins 가 없다 — 번호에 걸 설명이 없으면 그냥 그림이다")
    nums = [p.get("n") for p in pins]
    if len(set(nums)) != len(nums):
        r.err(f"{where}.pins", f"번호가 겹친다: {nums}")
    for i, p in enumerate(pins):
        pw = f"{where}.pins[{i}]"
        if not p.get("title") or not p.get("what"):
            r.err(pw, "title 또는 what 이 비어 있다")
        _check_sources(p, pw, r)

    screen = ui.get("screen") or []
    if not screen:
        r.err(where, "screen 이 비어 있다")
    used = set()
    for i, el in enumerate(screen):
        ew = f"{where}.screen[{i}]"
        t = el.get("type")
        if t not in UI_ELEMENT_TYPES:
            r.err(ew, f"뷰어가 모르는 요소 종류다: {t!r} (가능: {', '.join(sorted(UI_ELEMENT_TYPES))})")
        if el.get("pin") is not None:
            used.add(el["pin"])
            if el["pin"] not in nums:
                r.err(ew, f"pin {el['pin']} 번에 해당하는 설명이 없다")
    for n in nums:
        if n not in used:
            r.warn(f"{where}.pins", f"{n}번 설명이 화면의 어느 자리에도 안 걸려 있다")


def _check_research(feat: dict, fw: str, r: Report) -> None:
    """STYLE.md 7번 — 회사 밖의 근거(논문·표준)와 아직 아무도 못 푼 것.

    비어 있는 것 자체는 오류가 아니다(억지로 채우지 않는다). 다만 보강 후보로는 올린다.
    쓰기로 했다면 칸이 다 차 있어야 한다 — 제목만 있는 논문 줄은 아무 정보도 아니다.
    """
    res = feat.get("research") or {}
    papers = res.get("papers") or []
    hard = res.get("hard_problems") or []

    for j, pp in enumerate(papers):
        pw = f"{fw}.research.papers[{j}]"
        if not pp.get("title"):
            r.err(pw, "title 없음")
        if not pp.get("url"):
            r.err(pw, "url 없음 — 링크 없는 논문 인용은 확인할 길이 없다")
        if not pp.get("takeaway"):
            r.err(pw, "takeaway 없음 — 논문 요약이 아니라 '이 회사가 무엇을 가져다 썼는가'를 쓴다")
        conf = pp.get("confidence")
        if conf not in CONFIDENCE:
            r.err(pw, f"confidence 값이 이상하다: {conf!r}")
        # 회사가 직접 언급한 게 아니면 inferred 여야 한다. 닮았다는 이유로 단정하지 않는다.
        if conf == "confirmed" and not (feat.get("sources") or pp.get("sources")):
            r.err(pw, "confirmed 인데 그 언급이 있는 회사 자료 링크가 없다")

    for j, hp in enumerate(hard):
        hw = f"{fw}.research.hard_problems[{j}]"
        if not hp.get("problem"):
            r.err(hw, "problem 없음")
        if not hp.get("why_hard"):
            r.err(hw, "why_hard 없음 — 이 칸이 난제 항목의 본체다(STYLE.md 7번)")
        if not hp.get("current_best"):
            r.warn(hw, "current_best 없음 — 차선책과 그 차선책이 감수하는 것을 함께 쓴다")
        _check_sources(hp, hw, r)

    # 비어 있는 것은 결함이 아니다(STYLE.md 7번: 억지로 채우지 않는다).
    # 여기를 보강 후보로 올리면 도구가 '채워라'라고 지목하게 되고, 그러면 있지도
    # 않은 논문을 만들어 개수를 맞추게 된다. research 는 확장 사이클에서 자료를
    # 열어 둔 채로 쓰는 것이지, 뒤늦게 채워 넣는 항목이 아니다.


MD_EMPHASIS = re.compile(r"\*\*|`")

# 강조 기호를 쓰면 안 되는 필드들 — **식별자이거나 무언가와 대조되는 값**이다.
#
# 표시만 하는 문장 필드는 화면이 마크다운으로 렌더하므로 강조를 써도 된다. 문제는
# 이 목록의 필드들인데, 여기 붙은 별표·백틱은 화면에 그대로 새어 나올 뿐 아니라
# 값끼리의 대조를 깨뜨린다 — domains[].name 은 features[].domain 과 글자 그대로
# 맞춰 보고, connections[].to 는 feature key 와 맞춰 본다.
PLAIN_FIELDS = (
    ("one_liner", lambda c: [c.get("one_liner")]),
    ("products", lambda c: c.get("products") or []),
    ("domains[].name", lambda c: [d.get("name") for d in (c.get("domains") or [])]),
    ("features[].name", lambda c: [f.get("name") for f in (c.get("features") or [])]),
    ("features[].domain", lambda c: [f.get("domain") for f in (c.get("features") or [])]),
    ("features[].connections[].to", lambda c: [x.get("to") for f in (c.get("features") or [])
                                                for x in (f.get("connections") or [])]),
)


def _check_plain_text(data: dict, w: str, r: Report) -> None:
    """마크다운으로 렌더되지 않는 필드에 강조 기호를 쓰지 않았는지."""
    for label, pick in PLAIN_FIELDS:
        for v in pick(data):
            if isinstance(v, str) and MD_EMPHASIS.search(v):
                r.warn(f"{w}.{label}",
                       "식별자·대조에 쓰이는 필드다 — 강조 기호를 넣으면 화면에 새어 나오고 "
                       "값끼리의 대조가 깨진다. 강조는 문장 필드(why·tradeoff·thought 등)에 쓴다")
                break


def check_company(data: dict, r: Report) -> None:
    slug = data.get("slug", "?")
    w = f"companies/{slug}.json"
    r._held = bool(data.get("hold_reason"))

    for f in ("slug", "name", "name_en", "country", "category", "status",
              "updated_at", "business_model", "products", "one_liner"):
        if not data.get(f):
            r.err(w, f"필수 필드 없음: {f}")
    if not SLUG_RE.match(str(data.get("slug", ""))):
        r.err(w, f"slug 형식 위반(영문 소문자·숫자·하이픈): {data.get('slug')!r}")
    if data.get("country") not in COUNTRIES:
        r.err(w, f"country 값이 이상하다: {data.get('country')!r}")
    if data.get("category") not in CATEGORIES:
        r.err(w, f"category 값이 이상하다: {data.get('category')!r}")
    if data.get("status") not in STATUSES:
        r.err(w, f"status 값이 이상하다: {data.get('status')!r}")
    if not DATE_RE.match(str(data.get("updated_at", ""))):
        r.err(w, f"updated_at 형식(YYYY-MM-DD) 위반: {data.get('updated_at')!r}")

    # 수익 구성 막대는 share 를 그대로 폭으로 쓴다. 합이 100 을 넘으면 그림이
    # 거짓말이 되므로 여기서 막는다. 보도의 반올림값(34.6+30.7+…)을 그대로
    # 옮기면 실제로 100.1 이 되는 일이 있었다 — 금액에서 다시 계산해야 한다.
    shares = []
    for i, rs in enumerate(data.get("revenue_streams") or []):
        _check_sources(rs, f"{w}.revenue_streams[{i}]", r)
        sh = rs.get("share")
        if sh is None:
            continue
        if not isinstance(sh, (int, float)) or isinstance(sh, bool):
            r.err(w, f"revenue_streams[{i}].share 는 숫자여야 한다: {sh!r}")
            continue
        if not 0 < sh <= 100:
            r.err(w, f"revenue_streams[{i}].share 범위 위반(0 초과 100 이하): {sh}")
        if not rs.get("amount"):
            r.warn(w, f"revenue_streams[{i}].share 가 있는데 amount 가 없다 — 원문 금액을 같이 적는다")
        shares.append(sh)
    if shares:
        total = round(sum(shares), 1)
        if total > 100:
            r.err(w, f"revenue_streams 의 share 합이 100 을 넘는다: {total}")
        if not data.get("revenue_total"):
            r.warn(w, "share 를 적었으면 revenue_total(표시용 총매출 한 줄)도 적는다")

    if data.get("ui_map"):
        _check_ui(data["ui_map"], f"{w}.ui_map", r)

    if not (data.get("domain_map") or {}).get("code"):
        r.warn(w, "domain_map 이 없다 — STYLE.md 1번은 회사마다 도메인 지도 한 장을 요구한다")

    domain_names = {d.get("name") for d in (data.get("domains") or [])}
    if not domain_names:
        r.warn(w, "domains 가 비어 있다 — 3단계(회사 프로파일)가 아직 안 끝났다")

    for dom in data.get("domains") or []:
        dw = f"{w}.domains[{dom.get('name')}]"
        techs = dom.get("tech") or []
        if not techs and not dom.get("hold_reason"):
            r.warn(dw, "tech 가 비어 있다 — STYLE.md 2번: 어떤 기술로 풀었는지까지 내려간다")
            r.gap("tech", dw, "tech 0개")
        for j, t in enumerate(techs):
            tw = f"{dw}.tech[{j}]"
            if not t.get("solves"):
                r.err(tw, "solves 없음 — 기술 이름만 나열하지 않는다")
            if not t.get("limits"):
                r.err(tw, "limits 없음 — 그 기술이 못 하는 것을 함께 쓴다(STYLE.md 2번)")
            _check_sources(t, tw, r)

    keys: set[str] = set()
    for i, feat in enumerate(data.get("features") or []):
        fw = f"{w}.features[{feat.get('key', i)}]"
        key = feat.get("key")
        if not key or not SLUG_RE.match(str(key)):
            r.err(fw, f"key 형식 위반: {key!r}")
        elif key in keys:
            r.err(fw, f"key 중복: {key}")
        else:
            keys.add(key)
        if feat.get("domain") not in domain_names:
            r.err(fw, f"domains 에 없는 도메인: {feat.get('domain')!r}")
        if not (feat.get("business") or {}).get("why"):
            r.err(fw, "business.why 없음 — 왜 존재하는 기능인지가 이 데이터의 핵심이다")

        for j, m in enumerate((feat.get("business") or {}).get("metrics") or []):
            _check_sources(m, f"{fw}.business.metrics[{j}]", r)

        impl = feat.get("implementation") or {}
        if not impl.get("flow"):
            r.warn(fw, "implementation.flow 가 비어 있다")
        decisions = impl.get("decisions") or []
        if not decisions:
            r.err(fw, "decisions 없음 — 의사결정 없는 기술 나열은 이 엔진의 산출물이 아니다")
        elif len(decisions) < 5:
            r.warn(fw, f"decisions {len(decisions)}개 — STYLE.md 3번 기준(보통 5~8개)에 못 미친다. 큰 결정 안에 숨은 작은 결정을 쪼갠다")
            r.gap("decisions", fw, f"결정 {len(decisions)}개 (기준 5)")
        for j, d in enumerate(decisions):
            dw = f"{fw}.decisions[{j}]"
            if not d.get("tradeoff"):
                r.err(dw, "tradeoff 없음 (품질 규칙: 트레이드오프 없는 설명 금지)")
            _check_sources(d, dw, r)
        for j, s in enumerate(impl.get("stack") or []):
            sw = f"{fw}.stack[{j}]"
            if not s.get("role"):
                r.err(sw, "role 없음 — 기술 이름만 나열하지 않는다")
            _check_sources(s, sw, r)

        if feat.get("ui"):
            _check_ui(feat["ui"], f"{fw}.ui", r)

        diagrams = feat.get("diagrams") or []
        if not diagrams:
            if feat.get("diagram"):
                r.warn(fw, "그림이 구버전 diagram 한 장뿐 — STYLE.md 1번은 흐름/상태/실패 경로를 나눠 그리길 요구한다")
            else:
                r.err(fw, "그림이 없다")
        for j, dg in enumerate(diagrams):
            gw = f"{fw}.diagrams[{j}]"
            if not dg.get("code"):
                r.err(gw, "mermaid code 없음")
            if not dg.get("title"):
                r.err(gw, "title 없음")
            if not dg.get("question"):
                r.warn(gw, "이 그림이 답하는 질문이 없다 — 없으면 그 그림은 뺀다(STYLE.md 1번)")
        if diagrams and not any(d.get("kind") == "failure" for d in diagrams):
            r.warn(fw, "실패 경로 그림이 없다 — 정상 흐름만 그린 기능은 절반만 설명한 것이다")
            r.gap("failure", fw, "실패 경로 그림 없음")

        # 엔티티는 {name, what} 객체다. 초기 사이클들이 "이름 — 설명" 한 문자열로 적은 게
        # 남아 있어 화면이 양쪽을 다 읽지만, 형식이 둘이면 다음에 쓰는 사람이 어느 쪽이
        # 맞는지 알 수 없다. 보강 사이클이 지나가며 객체로 바꾼다.
        ents = (feat.get("domain_model") or {}).get("entities") or []
        n_str = sum(1 for e in ents if isinstance(e, str))
        if n_str:
            r.warn(f"{fw}.domain_model.entities",
                   f"엔티티 {n_str}개가 문자열이다 — 스키마는 {{name, what}} 객체다. "
                   "화면은 ' — ' 로 갈라 읽지만 형식을 하나로 모은다")
        for j, e in enumerate(ents):
            if isinstance(e, dict) and not e.get("name"):
                r.err(f"{fw}.domain_model.entities[{j}]", "name 없음")

        for j, t in enumerate(feat.get("thinking") or []):
            tw = f"{fw}.thinking[{j}]"
            if not t.get("at") or not t.get("thought"):
                r.err(tw, "at/thought 가 비었다")
            if t.get("confidence") not in CONFIDENCE:
                r.err(tw, f"confidence 값이 이상하다: {t.get('confidence')!r}")
        if not feat.get("thinking"):
            r.warn(fw, "thinking 이 없다 — STYLE.md 5번: 결론 앞의 생각을 남긴다")
            r.gap("thinking", fw, "thinking 없음")

        _check_research(feat, fw, r)

        _check_sources(feat, fw, r)

    # 연결이 실재하는 기능을 가리키는지. 오타 하나로 그래프가 끊긴다.
    for feat in data.get("features") or []:
        for c in feat.get("connections") or []:
            to = c.get("to")
            if to in keys or to is None:
                continue
            if not c.get("via"):
                r.err(f"{w}.features[{feat.get('key')}].connections", f"via 없음 (to={to!r})")
            # 외부 시스템이면 feature key 가 아니어도 된다 — 경고로만 남긴다.
            if SLUG_RE.match(str(to)) and to not in keys:
                r.warn(f"{w}.features[{feat.get('key')}].connections",
                       f"feature key 처럼 생겼는데 그런 기능이 없다: {to!r}")


    # 진행 중인 회사에서 아직 기능이 하나도 없는 도메인 — PROMPT.md 2단계 사다리의
    # 2순위다. 회사를 갈아타지 않는다는 규칙이 여기서 나온다.
    if data.get("status") == "in_progress" and not data.get("hold_reason"):
        for dom in data.get("domains") or []:
            if dom.get("hold_reason"):
                continue  # 이 도메인만 막혔다 — 회사는 계속 판다
            if not [f for f in (data.get("features") or []) if f.get("domain") == dom.get("name")]:
                r.wip.append((slug, str(dom.get("name"))))

    # 다시 들여다볼 때가 됐는가. 보류(hold_reason)인 회사는 세지 않는다 — 새 단서가
    # 생기기 전엔 다시 파지 않기로 한 곳이라, 날짜만으로 부르면 같은 벽을 또 친다.
    if not data.get("hold_reason"):
        try:
            y, m, dd = (int(x) for x in str(data.get("updated_at", "")).split("-"))
            days = (date.today() - date(y, m, dd)).days
            if days >= STALE_DAYS:
                r.stale.append((slug, str(data.get("updated_at")), days))
        except (ValueError, TypeError):
            pass  # updated_at 형식 오류는 위에서 이미 err 로 잡힌다

    _check_plain_text(data, w, r)


def check_index(index: dict, companies: dict[str, dict], r: Report) -> None:
    w = "index.json"
    if not DATE_RE.match(str(index.get("updated_at", ""))):
        r.err(w, f"updated_at 형식(YYYY-MM-DD) 위반: {index.get('updated_at')!r}")
    if not isinstance(index.get("countries"), dict) or not index["countries"]:
        r.err(w, "countries 맵이 없다 — 사이트가 국가 필터를 못 그린다")

    listed = set()
    for i, c in enumerate(index.get("companies") or []):
        slug = c.get("slug")
        cw = f"{w}.companies[{slug or i}]"
        if not slug:
            r.err(cw, "slug 없음")
            continue
        listed.add(slug)
        if not c.get("one_liner"):
            r.err(cw, "one_liner 없음 — 디렉토리 카드가 빈 칸이 된다")
        if not isinstance(c.get("features_done"), int):
            r.err(cw, f"features_done 이 정수가 아니다: {c.get('features_done')!r}")
        full = companies.get(slug)
        if full is None:
            r.err(cw, f"목록에 있는데 companies/{slug}.json 이 없다")
            continue
        for f in MIRRORED:
            if c.get(f) != full.get(f):
                r.err(cw, f"{f} 가 상세와 다르다: {c.get(f)!r} vs {full.get(f)!r}")
        n = len(full.get("features") or [])
        if c.get("features_done") != n:
            r.err(cw, f"features_done={c.get('features_done')} 인데 상세엔 {n}개")

    for slug in companies:
        if slug not in listed:
            r.err(w, f"companies/{slug}.json 이 index 에 없다 — 사이트에 안 뜬다")

    known = {d.get("name") for c in companies.values() for d in (c.get("domains") or [])}
    missing = known - set(index.get("domains") or [])
    if missing:
        r.err(w, f"domains 배열에 빠진 도메인: {sorted(missing)}")


def _print_gaps(r: Report) -> int:
    """루프가 읽는 출력. '무엇이 깨졌나'와 '다음에 뭘 채우나'를 순서대로 준다.

    PROMPT.md 2단계의 사다리가 이 출력을 그대로 위에서부터 훑는다.
    """
    if r.errors:
        print("## 오류 — 이것부터 고친다 (보강보다 먼저)")
        for line in r.errors:
            print(f"  ✗ {line}")
        print()

    # 큐 잔량은 어느 단으로 가든 보인다. 파는 쪽과 채우는 쪽은 별개의 일이고,
    # 채우는 쪽이 밀리고 있다는 사실이 파는 사이클에서도 눈에 띄어야 한다.
    depth = _queue_depth()
    if depth is None:
        print("## 큐 — QUEUE.md 를 읽지 못했다")
    else:
        mark = "비었다" if depth == 0 else ("목표 미달" if depth < QUEUE_TARGET else "충분")
        print(f"## 큐 잔량 {depth}/{QUEUE_TARGET} — {mark}")
    print()

    ordered = sorted(r.gaps, key=lambda g: (g[0], g[2]))

    # 사다리(PROMPT.md 2단계) 그대로 이번 대상을 정해 준다. 루프가 판단하지 않아도
    # 되게 하는 것이 이 출력의 목적이다 — 판단이 끼면 매번 쉬운 것만 고르게 된다.
    if r.wip:
        slug, dom = r.wip[0]
        print("### 이번 사이클의 대상 — 확장 (사다리 2순위)")
        print(f"  [확장] {slug} — 도메인 '{dom}' 에 기능이 없다")
        print("  할 일: 이 도메인의 기능 하나를 끝까지 판다 (PROMPT.md 4단계)")
        if len(r.wip) > 1:
            print()
            print(f"  진행 중인 빈 도메인 {len(r.wip)}개 중 첫 번째다:")
            for s2, d2 in r.wip[1:]:
                print(f"    · {s2} — '{d2}'")
        print()
        print(f"  보강 후보 {len(ordered)}건은 **이 회사가 done 이 된 뒤에** 본다 —")
        print("  회사를 갈아타지 않는다는 규칙이 보강보다 위다.")
        return 1 if r.errors else 0

    # 큐가 비었고 진행 중인 회사도 없으면, '파는 쪽' 트랙이 통째로 멈춰 있다.
    # 재방문·보강은 계속 돌 수 있지만 그것만 돌면 새 회사는 영영 안 들어온다.
    if depth == 0:
        print("### 이번 사이클의 대상 — 후보 조사 (큐가 비었다)")
        print("  할 일: PROMPT.md 2⁗단계. 회사를 파지 말고 **팔 수 있는지 확인해 적기만** 한다.")
        print("         QUEUE.md 의 '확인해 둔 후보'부터 보고, 1차 자료가 의사결정과")
        print("         대가를 말하는지 확인한 뒤 '## 대기' 표로 올린다.")
        print(f"         목표는 {QUEUE_TARGET}곳이다 — 한 사이클에 여러 곳을 올려도 된다.")
        print("         (이 사이클은 회사를 파는 게 아니라 큐를 채우는 것이므로,")
        print("          '한 사이클 = 한 대상' 은 '한 사이클 = 한 번의 조사' 로 읽는다.)")
        if r.stale:
            print()
            print(f"  참고: 다시 볼 때가 된 회사도 {len(r.stale)}곳 있다(재방문, 그 아래 단).")
        return 1 if r.errors else 0

    # 재방문 — 진행 중인 회사가 없을 때 사다리의 다음 단.
    # 이 단만이 바깥을 본다. 나머지는 전부 이미 가진 것을 정리하는 일이다.
    if r.stale:
        r.stale.sort(key=lambda x: -x[2])
        slug, when, days = r.stale[0]
        print("### 이번 사이클의 대상 — 재방문 (사다리 3순위)")
        print(f"  [재방문] {slug} — 마지막 갱신 {when} ({days}일 전)")
        print("  할 일: 그 회사가 그 뒤로 낸 공개 자료를 찾는다.")
        print("         새 기능이 나오면 확장, 기존 서술과 어긋나면 PROMPT.md 2″단계(정정),")
        print("         아무것도 없으면 **그 사실만 기록하고 끝낸다** — 없는 일을 만들지 않는다.")
        if len(r.stale) > 1:
            print()
            print(f"  다시 볼 때가 된 회사 {len(r.stale)}곳 중 가장 오래된 것이다:")
            for s2, w2, d2 in r.stale[1:1 + SHOW_NEXT]:
                print(f"    · {s2} — {w2} ({d2}일 전)")
            if len(r.stale) > 1 + SHOW_NEXT:
                print(f"    … 외 {len(r.stale) - 1 - SHOW_NEXT}곳")
        print()
        print(f"  (보강 후보 {len(ordered)}건은 그 아래 단이다.)")
        return 1 if r.errors else 0

    # 여기까지 왔는데 보강 후보도 없으면, 사다리는 이미 가진 것을 정리하는 단을
    # 다 지난 것이다. 아래 단은 전부 '바깥에서 가져오는' 일이다.
    if not ordered:
        print("## 정리할 것이 없다 — 사다리를 더 내려간다")
        if depth:
            print("  이번 사이클의 대상 — **신규**: QUEUE.md '## 대기' 맨 위 회사를")
            print("  in_progress 로 만들고 PROMPT.md 3단계(회사 프로파일)부터 판다.")
            if depth < QUEUE_TARGET:
                print()
                print(f"  (큐가 {depth}/{QUEUE_TARGET} 로 목표에 못 미친다. 이 회사를 다 판 뒤")
                print("   후보 조사 사이클을 한 번 끼워 버퍼를 채운다 — 바닥을 치고 나서")
                print("   채우면 팔 회사가 떨어질 때마다 사이클을 하나씩 버리게 된다.)")
        else:
            print("  큐도 비었다 → 후보 조사 사이클(PROMPT.md 2⁗단계).")
        print()
        print("  그것도 아니면 같은 도메인을 두 회사 이상에서 채웠는지 보고 비교 문서를 쓴다.")
        print("  아무것도 아니면 그 사실만 STATE.md 에 적고 끝낸다 —")
        print("  채울 게 없을 때 지어내는 것이 이 데이터를 망치는 가장 빠른 길이다.")
        return 1 if r.errors else 0

    # 종류별 집계를 먼저 준다. 루프는 매 사이클 이 출력을 읽으므로 전량을 쏟으면
    # 그것만으로 맥락이 찬다. 고를 것은 어차피 하나다.
    by_kind: dict[str, int] = {}
    for _, kind, _, _ in ordered:
        by_kind[kind] = by_kind.get(kind, 0) + 1
    summary = " · ".join(
        f"{k} {by_kind[k]}" for k in sorted(by_kind, key=lambda k: GAP_KINDS[k][0])
    )
    print(f"## 보강 후보 {len(ordered)}건 — {summary}")
    print()

    top = ordered[0]
    print("### 이번 사이클의 대상 (사다리 맨 위)")
    print(f"  [{top[1]}] {top[2]}")
    print(f"  모자란 것: {top[3]}")
    print(f"  할 일: {GAP_KINDS[top[1]][1]}")

    rest = ordered[1:1 + SHOW_NEXT]
    if rest:
        print()
        print(f"### 그 다음 {len(rest)}건 (참고 — 이번엔 손대지 않는다)")
        for prio, kind, where, msg in rest:
            print(f"  {prio}. [{kind}] {where} — {msg}")
    if len(ordered) > 1 + SHOW_NEXT:
        print(f"  … 외 {len(ordered) - 1 - SHOW_NEXT}건. 전량은 --gaps-all 로 본다.")
    return 1 if r.errors else 0


def main() -> int:
    args = [a for a in sys.argv[1:]]
    want_gaps = "--gaps" in args or "--gaps-all" in args
    if "--gaps-all" in args:
        globals()["SHOW_NEXT"] = 10 ** 9
    args = [a for a in args if not a.startswith("--")]
    only = args[0] if args else None
    r = Report()

    companies: dict[str, dict] = {}
    for path in sorted(COMPANIES.glob("*.json")):
        if only and path.stem != only:
            continue
        data = _load(path, r)
        if data is None:
            continue
        companies[path.stem] = data
        if data.get("slug") != path.stem:
            r.err(f"companies/{path.name}", f"파일명과 slug 불일치: {data.get('slug')!r}")
        check_company(data, r)

    index = _load(INDEX, r)
    if index is not None and not only:
        check_index(index, companies, r)

    if want_gaps:
        return _print_gaps(r)

    for line in r.warnings:
        print(f"  ! {line}")
    for line in r.errors:
        print(f"  ✗ {line}")
    n = len(companies)
    if r.errors:
        print(f"\n실패 — 회사 {n}개 · 오류 {len(r.errors)}건 · 경고 {len(r.warnings)}건")
        return 1
    print(f"\n통과 — 회사 {n}개 · 경고 {len(r.warnings)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
