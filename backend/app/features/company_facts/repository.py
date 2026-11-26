"""회사 사실 — company_fact · company_posting_salary · market_wage(_size) (020, 파이프라인 store/ingest/company_facts.py 가 쓴다)."""
from __future__ import annotations

from app.db.session import fetch_all, fetch_one


def fact(key: str) -> dict | None:
    return fetch_one("SELECT * FROM company_fact WHERE company_key = %s", (key,))


def salaries(key: str) -> list[dict]:
    return fetch_all("SELECT job_key, title, url, pay_min, pay_max, kind, career, quote, seen_on FROM company_posting_salary "
                     "WHERE company_key = %s ORDER BY seen_on DESC NULLS LAST, pay_min DESC LIMIT 8", (key,))


def latest_wage_year() -> int | None:
    r = fetch_one("SELECT max(year) AS y FROM market_wage")
    return r["y"] if r else None


def wage(year: int) -> list[dict]:
    return fetch_all("SELECT occ_code, occ_name, career, annual_pay, workers FROM market_wage WHERE year = %s", (year,))


def wage_size(year: int) -> list[dict]:
    return fetch_all("SELECT size, age, annual_pay, tenure_years FROM market_wage_size WHERE year = %s", (year,))
