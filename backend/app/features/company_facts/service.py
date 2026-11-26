"""회사 사실 → 화면 모양.

표(company_fact 등)는 숫자만 들고 있고, 문장·출처 번호·표 줄은 여기서 만든다 — 뷰어의 RolePayBenefits·
RoleLocation 이 공고 풀이(roles/items)와 같은 모양으로 그린다. 키는 engine/roles/validate.py 의 co_norm 과 같다.
"""
from __future__ import annotations

import re
import urllib.parse

from app.core.exceptions import NotFound
from app.features.company_facts import repository as repo

NPS_URL = "https://www.data.go.kr/data/15083277/fileData.do"
WAGE_URL = "https://kosis.kr/statHtml/statHtml.do?orgId=118&tblId=DT_118N_PAYM47"


def co_norm(s: str) -> str:
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "").lower()


def _fmt(man: int) -> str:
    return f"{man // 10000}억 {man % 10000:,}만원".replace(" 0만원", "원") if man >= 10000 else f"{man:,}만원"


def _salary_value(s: dict) -> str:
    if s["kind"] == "범위" and s.get("pay_max"):
        return f"{_fmt(s['pay_min'])} ~ {_fmt(s['pay_max'])}"
    return _fmt(s["pay_min"]) + (" 이상" if s["kind"] == "이상" else "")


def company(name: str) -> dict:
    key = co_norm(name)
    f = repo.fact(key)
    if not f:
        bare = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", key)
        f = repo.fact(bare) if bare and bare != key else None
    if not f:
        raise NotFound(f"회사 사실 없음: {name}")
    return build(f, repo.salaries(f["company_key"]))


def build(f: dict, sal: list[dict]) -> dict:
    sources: list[dict] = []

    def src(title: str, url: str, kind: str, date) -> int:
        sources.append({"n": len(sources) + 1, "title": title, "url": url, "kind": kind, "date": str(date or "")[:10]})
        return len(sources)

    w = src(f"원티드 기업정보 — {f['name']}", f["wanted_url"], "reference", f["wanted_pay_updated"]) if f.get("wanted_url") else None
    n = src(f"국민연금 가입 사업장 내역({f['nps_month']})", NPS_URL, "reference", f["nps_month"]) if f.get("nps_month") else None

    prow = []
    for s in sal:
        i = src(f"공고 — {s['title']}", s["url"], "posting", s.get("seen_on"))
        prow.append({"label": f"공고 연봉 · {s.get('career') or '경력 무관'}", "value": _salary_value(s), "amount": s["pay_min"],
                     "basis": "공고에 적힌 값", "note": f"「{s.get('quote') or ''}」 — {s['title']} [{i}]"})
    avg = []
    if f.get("wanted_avg_pay"):
        avg.append({"label": "직원 평균 연봉", "value": "약 " + _fmt(f["wanted_avg_pay"]), "amount": f["wanted_avg_pay"],
                    "basis": "공공데이터 집계", "note": f"원티드가 국민연금 자료로 계산한 회사 전체 평균이다 — 신입 초봉이 아니다 [{w}]"})
    if f.get("nps_annual_est"):
        avg.append({"label": "국민연금 기준 추정", "value": "약 " + _fmt(f["nps_annual_est"]), "amount": f["nps_annual_est"],
                    "basis": f"국민연금 · {f['nps_month']}",
                    "note": f"가입자 {f['nps_members']:,}명의 월 고지금액 ÷ 보험료율로 거꾸로 계산했다 [{n}]"})
    emp = f.get("employees")
    pay = None
    if prow:
        pay = {"summary": f"공고에 적힌 연봉은 **{prow[0]['value']}**({prow[0]['label'].split('· ')[-1]})"
                          + (f", 직원 평균은 **{avg[0]['value']}**" if avg else "") + " — 공고 값은 회사가 직접 밝힌 숫자다",
               "rows": prow + avg,
               "how": "공고 연봉은 그 자리·경력 기준으로 회사가 적은 값이다(‘이상’은 최저선). 평균 연봉은 국민연금 자료로 계산한 "
                      "회사 전체 평균이라 경력·비개발 직군이 섞여 있고, 보험료 소득 상한 때문에 고연봉 회사일수록 낮게 나온다."}
    elif avg:
        pay = {"summary": f"직원 평균은 **{avg[0]['value']}**" + (f", 인원 **{emp:,}명**" if emp else "") + " — 공개 자료로 계산한 회사 전체 평균이다",
               "rows": avg,
               "how": "국민연금 보험료는 소득 상한까지만 매겨서 연봉이 높은 회사일수록 실제보다 낮게 나온다. 경력·비개발 직군이 섞인 평균이라 이 자리의 제안 연봉과 다르다."}

    tags = f.get("benefit_tags") or []
    benefits = {"items": [{"name": t, "detail": ""} for t in tags],
                "note": f"원티드 기업정보의 복지 태그 [{w}] — 조건·금액은 위 공고의 복지 칸을 본다."} if tags and w else None

    location = None
    if f.get("address"):
        from_wanted = f.get("address_source") == "wanted"
        location = {"name": f["name"], "address": f["address"],
                    "map_url": "https://map.naver.com/p/search/" + urllib.parse.quote(f["address"].split(",")[0]),
                    "note": (f"원티드 기업정보의 주소 [{w}]" if from_wanted else f"국민연금 사업장 주소(번지 없음) [{n}]") + " — 팀 자리는 다를 수 있다."}

    return {"company": f["name"], "sources": sources, "employees": emp, "industry": f.get("industry"),
            "founded": f.get("founded"), "pay": pay, "benefits": benefits, "location": location,
            "updated_at": f["updated_at"].isoformat() if f.get("updated_at") else None}


def market_wage() -> dict:
    y = repo.latest_wage_year()
    if not y:
        raise NotFound("연차별 시세가 아직 없다(crawl_company_facts wage 가 DB 에 쓰기 전)")
    occ: dict = {}
    for r in repo.wage(y):
        o = occ.setdefault(r["occ_code"], {"name": r["occ_name"], "careers": {}})
        o["careers"][r["career"]] = {"annual_만원": r["annual_pay"], "workers": r["workers"]}
    sizes: dict = {}
    for r in repo.wage_size(y):
        sizes.setdefault(r["size"], {})[r["age"]] = {"annual_만원": r["annual_pay"], "tenure_years": r["tenure_years"]}
    return {"year": str(y),
            "source": {"title": f"고용노동부 고용형태별노동실태조사 {y}년 — 직종·경력년수·성별 / 규모·학력·연령계층·성별 임금", "url": WAGE_URL},
            "note": "월임금총액(정액·초과급여 + 전년도 특별급여 ÷12) × 12 로 연봉을 셈했다. 6월 급여 기준, 회사별이 아니라 전국 직종·규모 평균이다.",
            "occupations": occ, "sizes_college": sizes}
