"""공고 API(store.api)가 뷰어의 브라우저 필터(filter.ts)와 같은 답을 내는지 대조한다.

목록·칩 건수를 서버로 옮기면서 규칙이 두 곳에 생겼다 — 화면 쪽 원본(filter.ts·
region.ts·classify.ts·career.ts)과 SQL·파이썬 쪽(store.facets·store.api). 이 스크립트는
DB 의 공고 전량을 두고 여러 필터 조합을 양쪽에 똑같이 넣어 건수·첫 페이지 순서·
칩 건수가 같은지 본다. node 로 TS 원본을 직접 돌린다(node 22.6+).

    python -m store.api_parity        # 불일치가 있으면 종료 코드 1

규칙을 한쪽만 고치면 여기서 걸린다.
"""
from __future__ import annotations

import json
import subprocess
import sys as _sys
import tempfile
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VIEWER = Path(__file__).resolve().parents[2] / "jd-viewer"

CASES: list[dict] = [
    {}, {"closed": "show"}, {"closed": "only"}, {"unverified": "hide"},
    {"regions": ["서울"]}, {"regions": ["서울"], "districts": ["강남구"]}, {"regions": ["경기", "서울"]},
    {"roles": ["백엔드"]}, {"roles": ["백엔드", "프론트엔드"], "careers": ["3-4년"]},
    {"stacks": ["Java", "Spring"]}, {"stacks": ["react"]}, {"sizes": ["대기업"]},
    {"sites": ["wanted", "saramin"], "careers": ["신입/무관"]},
    {"query": "현대자동차"}, {"query": "  Kafka "},
    {"query": "백엔드", "regions": ["서울"], "closed": "show"},
    {"query": "100%"}, {"query": "a_b"},
]

# 뷰어 TS 는 확장자 없이 import 한다('./region'). node 의 ESM 은 그걸 못 찾으므로
# '.ts' 를 붙여 보는 resolve 훅을 건다.
_HOOKS = r"""
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
export async function resolve(spec, ctx, next) {
  if ((spec.startsWith('./') || spec.startsWith('../')) && !/\.[a-z]+$/.test(spec)) {
    const u = new URL(spec + '.ts', ctx.parentURL)
    if (existsSync(fileURLToPath(u))) return next(u.href, ctx)
  }
  return next(spec, ctx)
}
"""

_RUNNER = r"""
import { readFileSync, writeFileSync } from 'node:fs'
import { applyFilter, computeFacets, emptyFilter } from '%(viewer)s/src/lib/filter.ts'
const [jobsPath, sizesPath, casesPath, outPath] = process.argv.slice(2)
const jobs = JSON.parse(readFileSync(jobsPath, 'utf8'))
const sizes = JSON.parse(readFileSync(sizesPath, 'utf8'))
for (const j of jobs) j.company_size = sizes[j.company]
const cases = JSON.parse(readFileSync(casesPath, 'utf8'))
writeFileSync(outPath, JSON.stringify(cases.map((c) => {
  const f = emptyFilter()
  for (const k of ['sites','careers','stacks','roles','regions','districts','sizes']) f[k] = new Set(c[k] || [])
  f.query = c.query || ''; f.closed = c.closed || 'hide'; f.unverified = c.unverified || 'show'
  const rows = applyFilter(jobs, f)
  const fc = computeFacets(jobs, f)
  return { total: rows.length, first: rows.slice(0, 50).map((j) => j.site + '-' + j.pid),
    facets: { siteCount: Object.fromEntries(fc.siteCount), careerCount: Object.fromEntries(fc.careerCount),
      regions: fc.regions, sizes: fc.sizes,
      districts: Object.fromEntries(fc.districts.map((x) => [x.name, x.count])),
      roles: Object.fromEntries(fc.roles.map((x) => [x.name, x.count])),
      stacks: Object.fromEntries(fc.stacks.map((x) => [x.name, x.count])) } }
})))
"""

_PARAM = {"sites": "site", "careers": "career", "stacks": "stack", "roles": "role",
          "regions": "region", "districts": "district", "sizes": "size"}


def main() -> int:
    from fastapi.testclient import TestClient
    from store.api import app
    from store.export import fetch_jobs
    from store.facets import company_sizes, refresh_dup

    refresh_dup()
    jobs = fetch_jobs()
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "hooks.mjs").write_text(_HOOKS, encoding="utf-8")
        (t / "reg.mjs").write_text(
            f"import {{ register }} from 'node:module'\nregister('{(t / 'hooks.mjs').as_uri()}')\n",
            encoding="utf-8")
        (t / "run.mjs").write_text(_RUNNER % {"viewer": VIEWER.as_posix()}, encoding="utf-8")
        (t / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        # 화면은 규모를 company_meta.json 에서 붙인다 — 같은 판정 함수로 만든 표를 준다.
        (t / "sizes.json").write_text(json.dumps(company_sizes(jobs), ensure_ascii=False),
                                      encoding="utf-8")
        (t / "cases.json").write_text(json.dumps(CASES, ensure_ascii=False), encoding="utf-8")
        subprocess.run(["node", "--no-warnings", "--import", str(t / "reg.mjs"), str(t / "run.mjs"),
                        str(t / "jobs.json"), str(t / "sizes.json"), str(t / "cases.json"),
                        str(t / "out.json")], check=True)
        ts = json.loads((t / "out.json").read_text(encoding="utf-8"))

    client = TestClient(app)
    bad = 0
    for case, want in zip(CASES, ts):
        params = [(_PARAM[k], v) for k, vs in case.items() if k in _PARAM for v in vs]
        if "query" in case:
            params.append(("q", case["query"]))
        params += [(k, case[k]) for k in ("closed", "unverified") if k in case]
        got = client.get("/api/jobs", params=params).json()
        f = got["facets"]
        diffs = []
        if got["total"] != want["total"]:
            diffs.append(f"건수 api={got['total']} 화면={want['total']}")
        if [f"{j['site']}-{j['pid']}" for j in got["items"]] != want["first"]:
            diffs.append("첫 페이지 순서")
        for name in ("siteCount", "careerCount", "regions", "sizes"):
            if f[name] != want["facets"][name]:
                diffs.append(name)
        # 건수가 같은 칩끼리의 순서는 화면이 정한다(여기선 이름순, 화면은 등장순) — 값만 본다.
        for name in ("districts", "roles", "stacks"):
            if {x["name"]: x["count"] for x in f[name]} != want["facets"][name]:
                diffs.append(name)
        bad += bool(diffs)
        mark = "OK" if not diffs else "✗ "
        print(f"  {mark} {json.dumps(case, ensure_ascii=False)} → {got['total']:,}건 {'; '.join(diffs)}")
    print(f"[api_parity] {len(CASES)}개 조합 · 공고 {len(jobs):,}건 — 불일치 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
