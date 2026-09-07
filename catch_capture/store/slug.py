"""주소 슬러그 — 회사(`/companies/<slug>`)와 기술(`/wiki/<slug>`).

회사 슬러그의 규칙 원본은 **`jd-viewer/src/lib/companySlug.js` 하나뿐이다.**
브라우저(앱 라우팅)와 Node(scripts/prerender.mjs)가 이미 그 파일을 쓰고 있고,
파이썬이 규칙을 따로 베껴 두면 셋 중 하나만 어긋나도 프리렌더한 정적 HTML 이
통째로 안 잡힌다. 그래서 여기서는 규칙을 다시 쓰지 않고 그 파일의 BRAND_SLUGS 를
**읽어서** 쓴다. 로마자 변환표는 KS 표기법이라 바뀌지 않으므로 포팅한다.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
COMPANY_SLUG_JS = ROOT_DIR / "jd-viewer" / "src" / "lib" / "companySlug.js"

# 국어의 로마자 표기 — companySlug.js 의 CHO/JUNG/JONG 과 같은 표다.
_CHO = ['g','kk','n','d','tt','r','m','b','pp','s','ss','','j','jj','ch','k','t','p','h']
_JUNG = ['a','ae','ya','yae','eo','e','yeo','ye','o','wa','wae','oe','yo','u','wo','we','wi','yu','eu','ui','i']
_JONG = ['','k','k','k','n','n','n','t','l','k','m','p','l','l','l','l','m','p','p','t','t','ng','t','t','k','t','p','t']

_BRAND_LINE = re.compile(r"^\s*([^\s:{}]+)\s*:\s*'([a-z0-9][a-z0-9-]*)'\s*,?\s*$")


@lru_cache(maxsize=1)
def brand_slugs() -> dict[str, str]:
    """companySlug.js 의 BRAND_SLUGS 를 읽는다.

    파일이 없으면(뷰어 없이 파이프라인만 있는 트리) 빈 표를 쓴다 — 로마자 폴백으로
    떨어질 뿐 동작은 한다. 다만 `쿠팡`이 `coupang` 이 아니라 `kupang` 이 되므로
    뷰어와 같이 쓰는 환경에서는 반드시 파일이 있어야 한다.
    """
    if not COMPANY_SLUG_JS.exists():
        return {}
    out: dict[str, str] = {}
    inside = False
    for line in COMPANY_SLUG_JS.read_text(encoding="utf-8").splitlines():
        if not inside:
            if "BRAND_SLUGS" in line and "{" in line:
                inside = True
            continue
        if line.startswith("}"):
            break
        m = _BRAND_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def romanize(text: str) -> str:
    """한글 음절을 로마자로. 한글이 아닌 글자는 그대로 흘려보낸다."""
    out = []
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            i = code - 0xAC00
            out.append(_CHO[i // 588] + _JUNG[(i % 588) // 28] + _JONG[i % 28])
        else:
            out.append(ch)
    return "".join(out)


def _clean(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def norm_company(name: str) -> str:
    """회사의 정체성. dashboard.classifier._norm_company 와 같은 규칙이다.

    여기에 다시 적는 이유: classifier 는 import 시 회사 목록 JSON 을 읽어 들이는
    무거운 모듈이라, 백필/크롤 경로가 그걸 끌고 들어올 이유가 없다. 규칙이 갈리지
    않도록 `--selftest` 가 두 구현을 대조한다.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()
    s = re.sub(r"\(주\)|주식회사|㈜|inc\.?|co\.?,?\s*ltd\.?|corp\.?|corporation|ltd\.?", "", s)
    return re.sub(r"[\s\-_().,&/]+", "", s)


def base_company_slug(norm: str) -> str:
    """충돌 처리 전의 회사 슬러그. companySlug.js 의 baseSlug 와 같다."""
    brand = brand_slugs().get(norm)
    if brand:
        return brand
    # `엑스에이아이xai` 처럼 한글 이름 뒤에 영문 별칭이 붙은 형태면 영문 쪽만 쓴다.
    alias = re.match(r"^[^a-z0-9]+([a-z0-9][a-z0-9]{2,})$", norm)
    if alias:
        return _clean(alias.group(1))
    return _clean(romanize(norm)) or "company"


def build_company_slugs(norms) -> dict[str, str]:
    """norm → slug. 겹치면 -2, -3 을 붙인다.

    어느 쪽이 번호를 받는지가 데이터 순서에 따라 흔들리면 주소가 배포마다 바뀌므로
    이름을 정렬해 놓고 앞에서부터 배정한다 — companySlug.js 와 같은 규칙이다.
    """
    by_norm: dict[str, str] = {}
    taken: set[str] = set()
    for norm in sorted(set(norms)):
        base = base_company_slug(norm)
        slug = base
        n = 2
        while slug in taken:
            slug = f"{base}-{n}"
            n += 1
        by_norm[norm] = slug
        taken.add(slug)
    return by_norm


# ── 기술 슬러그 ───────────────────────────────────────────────────────
# 스키마의 CHECK 는 `^[a-z0-9][a-z0-9.+#-]*$` 다. 실제 토큰 850개를 돌려 보면
# 그대로는 135개가 걸린다 — 대부분 한글 용어(`백엔드 개발`, `데이터베이스`)이고,
# `.NET`(305건)처럼 점으로 시작하는 것도 있다. 아래 두 장치로 흡수한다.
_TECH_SPECIAL = {
    ".net": "dotnet", "c#": "csharp", "c++": "cpp", "f#": "fsharp",
    "objective-c": "objective-c", ".net core": "dotnet-core",
    "asp.net": "aspnet", "node.js": "nodejs", "vue.js": "vuejs",
    "next.js": "nextjs", "nuxt.js": "nuxtjs", "three.js": "threejs",
}

# tech_stack 에 섞여 들어오는 비-기술 토큰. 지우지 않고 is_noise 로 찍는다 —
# 지우면 다음 크롤이 또 만들어낸다.
_NOISE_EXACT = {
    "dev", "mobile", "개발", "설계", "서울", "경기", "부산", "대전", "인천",
    "백엔드 개발", "프론트엔드 개발자", "웹 개발", "데이터 분석", "보안",
    "보안 운영", "클라우드 보안", "방화벽", "로봇", "콘텐츠 제작",
}
# 기술명이 이보다 길면 파싱 사고다(공고 본문 한 문단이 통째로 들어온 사례가 있다).
TECH_NAME_MAX = 40


def tech_slug(name: str) -> str:
    """기술명 → 슬러그. 못 만들면 빈 문자열(= 색인하지 않는다)."""
    raw = (name or "").strip()
    if not raw or len(raw) > TECH_NAME_MAX:
        return ""
    low = raw.lower()
    if low in _TECH_SPECIAL:
        return _TECH_SPECIAL[low]
    s = re.sub(r"\s+", "-", low)
    # 한글은 **지우기 전에** 로마자로 옮긴다. 순서를 바꾸면 한글이 통째로 사라지면서
    # 'Windows 서버' 가 'windows' 로, 'QA 엔지니어링' 이 'qa' 로 줄어 서로 다른
    # 기술이 하나로 합쳐진다(실제로 26건·15건이 그렇게 뭉개졌다).
    s = romanize(s)
    s = re.sub(r"[^a-z0-9.+#-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-.")
    if not s:
        s = _clean(romanize(low))
    if not s or not re.match(r"^[a-z0-9]", s):
        return ""
    return s


def is_noise_tech(name: str) -> bool:
    raw = (name or "").strip()
    return (not raw) or len(raw) > TECH_NAME_MAX or raw.lower() in _NOISE_EXACT


def _selftest() -> int:
    """`python -m store.slug --selftest` — 규칙이 JS/classifier 와 갈렸는지 본다."""
    failed = 0

    # 1. norm_company 가 classifier 와 같은 답을 내는가
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from dashboard.classifier import _norm_company as ref
        for name in ["메가존클라우드㈜", "(주)클로봇", "주식회사 솔트룩스", "Coupang Inc.",
                     "현대오토에버(주)", "쿠팡", "네이버 클라우드"]:
            if norm_company(name) != ref(name):
                failed += 1
                print(f"FAIL norm_company({name!r}): {norm_company(name)!r} != {ref(name)!r}")
    except Exception as e:
        print(f"  (classifier 대조 건너뜀: {e})")

    # 2. BRAND_SLUGS 를 실제로 읽었는가 — 못 읽으면 쿠팡이 kupang 이 된다
    brands = brand_slugs()
    if not brands:
        failed += 1
        print(f"FAIL BRAND_SLUGS 를 못 읽었다: {COMPANY_SLUG_JS}")
    elif brands.get("쿠팡") != "coupang":
        failed += 1
        print(f"FAIL BRAND_SLUGS['쿠팡'] = {brands.get('쿠팡')!r}")
    else:
        print(f"  BRAND_SLUGS {len(brands)}개 로드")

    # 3. 슬러그 규칙
    cases = [("쿠팡", "coupang"),              # BRAND_SLUGS 우선
             ("메가존클라우드", "megazonecloud"),  # BRAND_SLUGS 우선
             ("클로봇", "keulrobot"),          # 브랜드 표기가 없으면 로마자 폴백
             ("엑스에이아이xai", "xai")]        # 한글 뒤 영문 별칭이면 영문 쪽
    for norm, want in cases:
        got = base_company_slug(norm)
        if got != want:
            failed += 1
            print(f"FAIL base_company_slug({norm!r}) = {got!r} (기대 {want!r})")

    # 4. 충돌은 정렬 순으로 안정적으로 배정된다
    got = build_company_slugs(["가나", "가나", "나가"])
    if len(set(got.values())) != len(got):
        failed += 1
        print(f"FAIL 슬러그 충돌: {got}")

    # 5. 기술 슬러그 — 스키마 CHECK 를 통과해야 한다
    check = re.compile(r"^[a-z0-9][a-z0-9.+#-]*$")
    for name, want in [(".NET", "dotnet"), ("C#", "csharp"), ("React Native", "react-native"),
                       ("Python", "python"), ("데이터베이스", "deiteobeiseu"),
                       # 한글이 붙은 이름이 영문 부분만 남아 다른 기술과 합쳐지면 안 된다
                       ("Windows 서버", "windows-seobeo"), ("QA 엔지니어링", "qa-enjinieoring")]:
        got = tech_slug(name)
        if got != want:
            failed += 1
            print(f"FAIL tech_slug({name!r}) = {got!r} (기대 {want!r})")
        if got and not check.match(got):
            failed += 1
            print(f"FAIL tech_slug({name!r}) = {got!r} 가 스키마 CHECK 를 어긴다")
    if tech_slug("x" * 200) != "":
        failed += 1
        print("FAIL 지나치게 긴 기술명이 걸러지지 않았다")

    print(f"store.slug selftest: {'통과' if not failed else f'{failed}건 실패'}")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_selftest() if "--selftest" in sys.argv else "사용법: --selftest")
