"""엔진 산출물 색인 → 정본 DB.

`engine/`(기술 역설계) · `guide-engine/`(취업 브리핑) · `study-engine/`(기술 백과사전)이
쓴 JSON 은 **파일로 둔다.** 사람이 쓴 글이고 git 리뷰 대상이라 DB 로 옮길 이유가 없다.
DB 에는 "무엇이 무엇에 붙어 있나"만 넣는다. 그러면 각 엔진의 `validate.py --gaps` 가
파일을 다 열어보는 대신 SQL 질의 한 줄이 된다.

  guide_gap  모집중 공고는 많은데 브리핑이 없는 회사
  study_gap  수요는 큰데 문서가 없는 기술

회사 이어붙이기는 alias 로 한다. 브리핑 index 의 `aliases` 는 이미 정규화된 형태라
`company.norm` 과 바로 맞는다. 못 맞으면 그 회사는 건너뛴다 — 공고가 없는 회사에
빈 행을 만들면 gap 질의가 그만큼 거짓말을 한다.

사용:
    python -m store.ingest_engines
    python -m store.ingest_engines --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys as _sys
from datetime import datetime
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from normalize import company as norm_company  # noqa: E402
from store import conn as store_conn  # noqa: E402
from store.slug import tech_slug  # noqa: E402

PUBLIC = _Path(__file__).resolve().parent.parent.parent / "jd-viewer" / "public"


def _load(path: _Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [경고] {path.name} 파싱 실패 — 건너뜀: {e}")
        return None


def _ts(v) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


def _company_by_alias(cur) -> dict[str, int]:
    """정규화된 회사명 → id. norm 과 alias 양쪽으로 찾을 수 있게 한다."""
    cur.execute("SELECT norm, id FROM company")
    out = {r["norm"]: r["id"] for r in cur.fetchall()}
    cur.execute("SELECT raw, company_id FROM company_alias")
    for r in cur.fetchall():
        out.setdefault(norm_company(r["raw"]), r["company_id"])
    return out


def ingest(dry_run: bool = False) -> dict:
    stats = {k: 0 for k in
             ("guide", "guide_miss", "reveng", "reveng_miss", "study", "links")}

    guide = _load(PUBLIC / "guide" / "index.json") or {}
    reveng = _load(PUBLIC / "reveng" / "index.json") or {}
    study = _load(PUBLIC / "study" / "index.json") or {}
    g_rows = guide.get("companies") or []
    r_rows = reveng.get("companies") or []
    s_rows = study.get("articles") or []
    print(f"입력: 브리핑 {len(g_rows)}곳 · 역설계 {len(r_rows)}곳 · 백과사전 {len(s_rows)}편")
    if dry_run:
        return stats

    with store_conn.connect() as db:
        with db.cursor() as cur:
            by_norm = _company_by_alias(cur)

            def find(row) -> int | None:
                """index 의 이름·별칭 중 아무거나 회사와 맞으면 그 id."""
                names = [row.get("name"), row.get("name_en"), row.get("slug")]
                names += list(row.get("aliases") or [])
                for n in names:
                    cid = by_norm.get(norm_company(n or ""))
                    if cid:
                        return cid
                return None

            # ── 취업 브리핑 ────────────────────────────────────────
            for row in g_rows:
                cid = find(row)
                if not cid:
                    stats["guide_miss"] += 1
                    continue
                cur.execute(
                    """INSERT INTO company_guide
                           (company_id, slug, updated_at, n_postings, n_items)
                       VALUES (%s,%s,COALESCE(%s, now()),%s,%s)
                       ON CONFLICT (company_id) DO UPDATE SET
                           slug = EXCLUDED.slug,
                           updated_at = EXCLUDED.updated_at,
                           n_postings = EXCLUDED.n_postings,
                           n_items = EXCLUDED.n_items""",
                    (cid, row["slug"], _ts(row.get("updated_at")),
                     int(row.get("postings") or 0), int(row.get("study_items") or 0)),
                )
                stats["guide"] += 1

            # ── 기술 역설계 ────────────────────────────────────────
            for row in r_rows:
                cid = find(row)
                if not cid:
                    stats["reveng_miss"] += 1
                    continue
                cur.execute(
                    """INSERT INTO reveng_doc (company_id, slug, updated_at)
                       VALUES (%s,%s,COALESCE(%s, now()))
                       ON CONFLICT (company_id) DO UPDATE SET
                           slug = EXCLUDED.slug, updated_at = EXCLUDED.updated_at""",
                    (cid, row["slug"], _ts(row.get("updated_at"))),
                )
                stats["reveng"] += 1

            # ── 기술 백과사전 ──────────────────────────────────────
            # 문서를 기술에 잇는다. slug 가 곧 기술 슬러그인 경우가 대부분이고,
            # 아니면 별칭으로 찾는다. 못 이어도 문서는 넣는다 — 문서가 먼저 있고
            # 그 기술의 공고가 나중에 들어오는 순서도 있다.
            cur.execute("SELECT slug, id FROM tech")
            tech_by_slug = {r["slug"]: r["id"] for r in cur.fetchall()}
            cur.execute("SELECT alias, tech_id FROM tech_alias")
            tech_by_alias = {str(r["alias"]).lower(): r["tech_id"] for r in cur.fetchall()}

            for row in s_rows:
                slug = row["slug"]
                tid = tech_by_slug.get(tech_slug(slug))
                if not tid:
                    for a in [row.get("title"), row.get("title_en")] + list(row.get("aliases") or []):
                        tid = tech_by_alias.get(str(a or "").lower()) or tech_by_slug.get(tech_slug(a or ""))
                        if tid:
                            break
                cur.execute(
                    """INSERT INTO study_article
                           (slug, tech_id, title, complete, n_sections, n_drills, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,COALESCE(%s, now()))
                       ON CONFLICT (slug) DO UPDATE SET
                           tech_id = EXCLUDED.tech_id, title = EXCLUDED.title,
                           complete = EXCLUDED.complete, n_sections = EXCLUDED.n_sections,
                           n_drills = EXCLUDED.n_drills, updated_at = EXCLUDED.updated_at""",
                    (slug, tid, row.get("title") or slug,
                     (row.get("status") == "done"),
                     int(row.get("sections") or 0), int(row.get("drills") or 0),
                     _ts(row.get("updated_at"))),
                )
                stats["study"] += 1

            # related 링크. 아직 없는 문서를 가리킬 수 있어 FK 를 안 걸었다 —
            # 그 끊긴 링크가 곧 다음 집필 대기열이다.
            for row in s_rows:
                doc = _load(PUBLIC / "study" / "articles" / f"{row['slug']}.json")
                if not doc:
                    continue
                for rel in doc.get("related") or []:
                    to = rel.get("slug") if isinstance(rel, dict) else rel
                    if not to:
                        continue
                    cur.execute(
                        "INSERT INTO study_link (from_slug, to_slug) VALUES (%s,%s) "
                        "ON CONFLICT DO NOTHING",
                        (row["slug"], to),
                    )
                    stats["links"] += 1
        db.commit()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="엔진 산출물 색인 → 정본 DB")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = ingest(args.dry_run)
    if args.dry_run:
        return 0
    print(f"브리핑 {s['guide']}곳 (공고 없는 회사 {s['guide_miss']}) · "
          f"역설계 {s['reveng']}곳 (공고 없는 회사 {s['reveng_miss']}) · "
          f"백과사전 {s['study']}편 · 링크 {s['links']}개")
    if s["reveng_miss"] or s["guide_miss"]:
        print("  ※ '공고 없는 회사'는 실패가 아니다 — 역설계는 넷플릭스·유튜브처럼 우리 공고에\n"
              "     없는 해외 회사도 다룬다. 뷰어는 그 문서를 파일에서 바로 읽으므로 화면은 멀쩡하고,\n"
              "     여기 색인은 공고와 이어지는 회사만 담는다(안 그러면 gap 질의가 거짓말을 한다).")

    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("SELECT count(*) n FROM guide_gap")
        print(f"\n브리핑 대기열(guide_gap): {cur.fetchone()['n']:,}곳")
        cur.execute("SELECT display_name, n_active FROM guide_gap LIMIT 5")
        for r in cur.fetchall():
            print(f"    {r['display_name']:<24} 모집중 {r['n_active']}건")
        cur.execute("SELECT count(*) n FROM study_gap")
        print(f"백과사전 대기열(study_gap): {cur.fetchone()['n']:,}종")
        cur.execute("SELECT name, n_jobs FROM study_gap LIMIT 5")
        for r in cur.fetchall():
            print(f"    {r['name']:<24} 공고 {r['n_jobs']}건")
        # 끊긴 링크 = 아직 안 쓴 문서
        cur.execute("""SELECT count(DISTINCT l.to_slug) n FROM study_link l
                        LEFT JOIN study_article a ON a.slug = l.to_slug
                        WHERE a.slug IS NULL""")
        print(f"끊긴 related 링크(= 다음 집필감): {cur.fetchone()['n']:,}종")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
