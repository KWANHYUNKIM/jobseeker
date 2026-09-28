#!/usr/bin/env python3
"""Build a Korean salary_data.json from jobseeker's data (jobseeker addition).

The upstream salary tool expects a user-supplied dataset (Danish union statistics).
Korea has no equivalent open table, so this builds one from what jobseeker already
collects:

  * researched salary bands from the employment briefs (guide-engine) — with
    sources and a confidence label; often an all-staff average from pension data,
    which is NOT a starting salary;
  * salaries that postings state in their own text (a minority — most say
    '회사 내규에 따름' or '면접 후 결정');
  * a market reference: p25 / median / p75 of those stated salaries by career
    stage x company size.

Parsing lives in one place — catch_capture/agent_mcp/data.py — and this script
imports it, so the MCP tool `salary_benchmark` and the offline lookup give the
same numbers.

Usage (from ai-job-search/):
    python tools/build_salary_kr.py                  # writes ./salary_data.json
    python tools/build_salary_kr.py --jobseeker-root ../ --out salary_data.json
Then:
    python salary_lookup.py "재미스튜디오" --career 신입
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def _load_data_module(root: Path):
    catch = root / "catch_capture"
    if not (catch / "agent_mcp" / "data.py").exists():
        sys.exit(f"jobseeker data layer not found under {catch} — pass --jobseeker-root")
    sys.path.insert(0, str(catch))
    from agent_mcp import data  # noqa: PLC0415
    return data


def build(data) -> dict:
    jobs = data.jobs()["by_key"]
    sizes = data._sizes()
    companies: dict[str, dict] = {}

    def entry_for(name: str) -> dict:
        key = data.norm(name)
        if key not in companies:
            companies[key] = {"company": name, "city": None,
                              "salary_kr": {"size": sizes.get(key), "bands": [], "posted": []}}
        return companies[key]

    for s in jobs.values():
        p = s.get("pay")
        if not p or not s.get("company"):
            continue
        e = entry_for(s["company"])
        if not e["city"] and s.get("region") not in (None, "지역 표기 없음", "기타"):
            e["city"] = s["region"]
        e["salary_kr"]["posted"].append({
            "id": s["id"], "title": s.get("title"), "career": s.get("career"), "status": s.get("status"),
            "low": p["low"], "high": p.get("high"), "monthly": p.get("monthly"), "text": p.get("text"),
        })

    idx = data._load("guide/index.json") or {}
    for c in idx.get("companies") or []:
        doc = data._load(f"guide/companies/{c['slug']}.json") or {}
        sal = doc.get("salary") or {}
        if not sal.get("bands"):
            continue
        e = entry_for(doc.get("name") or c.get("name"))
        e["salary_kr"]["bands"] = sal["bands"]
        e["salary_kr"]["band_note"] = sal.get("note")
        e["salary_kr"]["as_of"] = sal.get("as_of")
        if doc.get("aliases"):
            e["aliases"] = doc["aliases"]

    market = data.salary_benchmark()["market"]
    for e in companies.values():
        e["salary_kr"]["posted"].sort(key=lambda p: (p.get("status") == "closed", -(p.get("low") or 0)))
        e["salary_kr"]["posted"] = e["salary_kr"]["posted"][:10]
        if e["city"] is None:
            del e["city"]

    return {
        "metadata": {
            "country": "KR",
            "unit": "만원/년",
            "source": "jobseeker — employment briefs + salaries stated in postings",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "market": market,
            # Company size for companies not in `companies` (no band, no stated salary) —
            # lets the lookup still pick the right market row.
            "sizes": {c.get("name"): c.get("size")
                      for c in (data._load("company_stacks.json") or {}).get("companies") or []
                      if c.get("name") and c.get("size")},
            "caveats": data.SALARY_CAVEATS,
        },
        "companies": sorted(companies.values(), key=lambda e: e["company"]),
    }


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "reconfigure", None):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Build Korean salary_data.json from jobseeker data")
    ap.add_argument("--jobseeker-root", type=Path, default=HERE.parent,
                    help="jobseeker repository root (default: the folder containing ai-job-search)")
    ap.add_argument("--out", type=Path, default=HERE / "salary_data.json")
    args = ap.parse_args(argv)
    out = build(_load_data_module(args.jobseeker_root.resolve()))
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_b = sum(1 for e in out["companies"] if e["salary_kr"]["bands"])
    n_p = sum(1 for e in out["companies"] if e["salary_kr"]["posted"])
    print(f"wrote {args.out} — {len(out['companies'])} companies "
          f"({n_b} with researched bands, {n_p} with stated salaries), {len(out['metadata']['market'])} market rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
