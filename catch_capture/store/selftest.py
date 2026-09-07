"""정본 DB 계층 자체 검사 — `python -m store.selftest`

**별도의 시험용 데이터베이스**(기본 `jobseeker_test`)를 만들어 거기서만 돈다.
운영 DB 는 건드리지 않는다. 매번 스키마를 새로 깔고 끝나면 지운다.

왜 이 파일이 있나. 이관 작업 중에 조용히 틀리는 결함이 다섯 개 나왔는데
(한글 기술명이 지워져 다른 기술과 합쳐짐, 마감일을 나중에 다시 파싱해 끝난 공고가
되살아남, 추천 JSON 키 형식이 뷰어와 어긋나 추천이 통째로 안 뜸 …) 전부 오류를
내지 않고 값만 틀리는 종류였다. 그런 건 사람이 눈으로 못 잡는다.

Ollama 없이 돈다 — 벡터는 유사도를 직접 지정한 결정적 값을 넣는다.

사용:
    python -m store.selftest
    python -m store.selftest --keep     # 끝나고 시험용 DB 를 남긴다(들여다볼 때)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys as _sys
from datetime import date, timedelta
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from store import conn as store_conn  # noqa: E402

ROOT = _Path(__file__).resolve().parent.parent.parent
SCHEMA = ROOT / "db" / "schema.sql"
TEST_DB = os.environ.get("JOBSEEKER_TEST_DB", "jobseeker_test")

# 시험 대상 모듈들(store.similar 등)은 자기 커넥션을 store.conn 으로 연다. 그래서
# 여기서 JOBSEEKER_DSN 을 시험용 DB 로 **바꿔치기해야** 그것들이 운영 DB 가 아니라
# 시험 DB 를 본다. 처음 한 번 원래 값을 붙들어 두고(아래 _BASE_DSN) 그걸 기준으로
# 시험 DB 주소를 만든다 — 안 그러면 바꾼 값을 다시 읽어 자기 자신을 가리킨다.
_BASE_DSN = store_conn.dsn()

TODAY = date.today()
_fails: list[str] = []
_passes = 0


def check(ok: bool, what: str, detail: str = "") -> bool:
    global _passes
    if ok:
        _passes += 1
    else:
        _fails.append(f"{what}{(' — ' + detail) if detail else ''}")
    print(f"  {'OK ' if ok else '!! '}{what}{('  ' + detail) if detail and not ok else ''}")
    return ok


def rejects(cur, sql, args, what: str) -> bool:
    """이 INSERT 는 **거부되어야** 정상이다."""
    cur.execute("SAVEPOINT sp")
    try:
        cur.execute(sql, args)
    except psycopg.Error as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp")
        return check(True, what, type(e).__name__)
    cur.execute("ROLLBACK TO SAVEPOINT sp")
    return check(False, what, "거부되지 않았다")


# ── 시험용 DB 준비 ────────────────────────────────────────────────────
def _admin_dsn() -> str:
    return _BASE_DSN.rsplit("/", 1)[0] + "/postgres"


def _test_dsn() -> str:
    return _BASE_DSN.rsplit("/", 1)[0] + "/" + TEST_DB


def make_db() -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{TEST_DB}"')
    with psycopg.connect(_test_dsn(), autocommit=True) as c:
        c.execute(SCHEMA.read_text(encoding="utf-8"))


def drop_db() -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')


# ── 벡터 ──────────────────────────────────────────────────────────────
def unit(*pairs) -> list[float]:
    """지정한 차원에만 값을 준 1024차원 단위 벡터. 코사인을 손으로 계산할 수 있다."""
    v = [0.0] * 1024
    for i, x in pairs:
        v[i] = x
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def run() -> int:
    from store.upsert import (
        refresh_display_names, set_job_techs, upsert_company, upsert_job,
    )

    with psycopg.connect(_test_dsn(), row_factory=dict_row) as db:
        cur = db.cursor()

        # ── 1. 회사: 표기가 갈려도 한 회사 ─────────────────────────
        print("\n[1] 회사 표기 흡수")
        for raw in ("(주)클로봇", "㈜클로봇", "클로봇", "주식회사 클로봇", "클로봇"):
            upsert_company(cur, raw)
        refresh_display_names(cur)
        cur.execute("SELECT count(*) n FROM company")
        check(cur.fetchone()["n"] == 1, "표기 5개 → 회사 1곳")
        cur.execute("SELECT count(*) n FROM company_alias")
        check(cur.fetchone()["n"] == 4, "alias 4개(같은 표기는 한 번)")
        cur.execute("SELECT display_name, slug FROM company")
        r = cur.fetchone()
        check("㈜" not in r["display_name"],
              "대표 표기에 합자 문자(㈜)가 없다", r["display_name"])
        check(r["slug"] == "keulrobot", "슬러그가 로마자 규칙을 따른다", r["slug"])
        cid = None
        cur.execute("SELECT id FROM company")
        cid = cur.fetchone()["id"]

        # ── 2. 기술 슬러그가 서로 다른 기술을 합치지 않는다 ────────
        print("\n[2] 기술 슬러그")
        ids = {}
        for name in ("Windows", "Windows 서버", "QA", "QA 엔지니어링", "JIRA", "Jira",
                     ".NET", "데이터베이스", "dev"):
            from store.upsert import upsert_tech
            ids[name] = upsert_tech(cur, name)
        check(ids["Windows"] != ids["Windows 서버"], "Windows ≠ Windows 서버")
        check(ids["QA"] != ids["QA 엔지니어링"], "QA ≠ QA 엔지니어링")
        check(ids["JIRA"] == ids["Jira"], "JIRA = Jira (대소문자만 다른 건 같은 기술)")
        cur.execute("SELECT slug FROM tech WHERE id = %s", (ids[".NET"],))
        check(cur.fetchone()["slug"] == "dotnet", ".NET → dotnet (스키마 CHECK 통과)")
        cur.execute("SELECT is_noise FROM tech WHERE id = %s", (ids["dev"],))
        check(cur.fetchone()["is_noise"], "'dev' 는 노이즈로 표시된다")

        # ── 2b. 조건 파싱: 크롤러가 흘린 제목이 DB 까지 못 가게 ──────
        print("\n[2b] 경력·고용형태 파싱")
        from store.upsert import parse_career, parse_employment
        check(parse_employment("정규직") == "정규직"
              and parse_employment("정규직(수습 3개월)") == "정규직"
              and parse_employment("정규직/계약직") == "정규직",
              "정상 고용형태는 받아들인다")
        # 실제 데이터에서 고용형태 칸에 들어앉아 있던 값들이다(242건 중 225건).
        check(all(parse_employment(v) is None for v in (
                  "[아이모비] 웹 풀스택 개발자(정규직/신입)",
                  "SK하이닉스(SK Hynix) React/Java 개발자(정규직/계약직/프리랜서) 채용",
                  "프리랜서 Java 백엔드 개발자 모집",
                  "[국비최대무료/기숙사무료/취업연계]AI/빅데이터/풀스택/KDT단기심화")),
              "제목이 고용형태로 들어오면 버린다")
        # 정규식은 받아들이는데 ENUM 표에는 없던 값. KeyError 가 함수 밖으로 튀어
        # 2026-09-08 크롤 사이클의 이중 쓰기를 통째로 롤백시켰다.
        check(parse_employment("아르바이트") == "기타",
              "ENUM 에 없는 고용형태는 '기타' 로 받는다")
        check(parse_employment("파견직(6개월)") == "파견",
              "  표기가 갈려도 ENUM 값 하나로 모인다")
        check(parse_career("경력3년↑") == (3, False)
              and parse_career("신입·경력") == (0, True)
              and parse_career("") == (None, None),
              "경력 파싱")

        # ── 3. 공고 제약 ───────────────────────────────────────────
        print("\n[3] 공고 제약")
        base = dict(site="wanted", pid="1", url="https://a.test/1", company_id=cid,
                    title="백엔드 개발자", career_text="", career_min=None,
                    accepts_entry=None, location_text="", sido=None, sigungu=None,
                    region=None, overseas=False, employment=None, education=None,
                    source_board=None, main_tasks="", qualifications="", preferences="",
                    benefits="", full_jd="", deadline_text="", deadline_on=None,
                    always_open=False, dday_text_raw="", content_hash="h1")
        job_a, _ = upsert_job(cur, base)
        cols = ", ".join(base)
        holes = ", ".join(["%s"] * len(base))
        ins = f"INSERT INTO job ({cols}) VALUES ({holes})"
        rejects(cur, ins, tuple({**base, "pid": "2"}.values()), "같은 URL 거부")
        rejects(cur, ins, tuple({**base, "url": "https://a.test/2"}.values()),
                "같은 (site,pid) 거부")
        rejects(cur, ins, tuple({**base, "pid": "3", "url": "https://a.test/3",
                                 "title": "   "}.values()), "빈 제목 거부")
        rejects(cur, ins, tuple({**base, "pid": "4", "url": "https://a.test/4",
                                 "company_id": None}.values()), "회사 없음 거부")
        rejects(cur, ins, tuple({**base, "pid": "5", "url": "https://a.test/5",
                                 "deadline_on": date(2999, 1, 1)}.values()),
                "말도 안 되는 마감일 거부")
        rejects(cur, "INSERT INTO job_override (job_id, field, value) VALUES (%s,%s,%s)",
                (job_a, "status", json.dumps("actve")), "status 오타 override 거부")

        # 같은 공고가 다른 주소로 다시 온다 — jobkorea 는 검색 위치를 URL 에 싣는다.
        # upsert 가 URL 만 보면 여기서 INSERT 로 밀다가 job_site_pid_uniq 에 걸리고,
        # 그 예외 하나가 크롤 사이클의 이중 쓰기를 통째로 롤백시킨다(2026-09-08).
        moved, inserted = upsert_job(cur, {**base, "url": "https://a.test/1?listno=7",
                                           "title": "백엔드 개발자(수정)"})
        check(moved == job_a and not inserted, "주소만 바뀐 같은 공고는 제자리 갱신")
        cur.execute("SELECT url, title FROM job WHERE id = %s", (job_a,))
        r = cur.fetchone()
        check(r["url"] == "https://a.test/1?listno=7" and r["title"].endswith("(수정)"),
              "  주소·본문이 최신 표기로 따라간다")

        # ── 4. status 는 계산값이다 ────────────────────────────────
        print("\n[4] job_state 우선순위 (저장이 아니라 계산)")
        past = {**base, "pid": "10", "url": "https://a.test/10",
                "deadline_on": TODAY - timedelta(days=5), "content_hash": "h2"}
        future = {**base, "pid": "11", "url": "https://a.test/11",
                  "deadline_on": TODAY + timedelta(days=7), "content_hash": "h3"}
        always = {**base, "pid": "12", "url": "https://a.test/12",
                  "always_open": True, "content_hash": "h4"}
        job_past, _ = upsert_job(cur, past)
        job_future, _ = upsert_job(cur, future)
        job_always, _ = upsert_job(cur, always)

        def state(jid):
            cur.execute("SELECT status, status_source, dday FROM job_state WHERE job_id=%s", (jid,))
            return cur.fetchone()

        s = state(job_a)
        check(s["status"] == "active" and s["status_source"] == "unknown",
              "마감일 없음 → active/unknown", str(dict(s)))
        s = state(job_past)
        check(s["status"] == "closed" and s["dday"] == -5,
              "지난 마감 → closed, dday=-5", str(dict(s)))
        s = state(job_future)
        check(s["status"] == "active" and s["dday"] == 7,
              "미래 마감 → active, dday=+7 (지금 계산)", str(dict(s)))
        s = state(job_always)
        check(s["status_source"] == "always_open", "상시채용 → always_open")

        # 원장이 마감일을 이긴다
        cur.execute("""INSERT INTO job_closure_check (job_id, closed, evidence)
                       VALUES (%s, true, '마감되었습니다')""", (job_future,))
        s = state(job_future)
        check(s["status"] == "closed" and s["status_source"] == "ledger",
              "원장이 마감일 텍스트를 이긴다")
        # 사람이 원장을 이긴다
        cur.execute("""INSERT INTO job_override (job_id, field, value)
                       VALUES (%s,'status',%s)""", (job_future, json.dumps("active")))
        s = state(job_future)
        check(s["status"] == "active" and s["status_source"] == "override",
              "수동 보정이 원장을 이긴다")

        # ── 5. v_job = 뷰어가 읽는 모양 ────────────────────────────
        print("\n[5] v_job / export 형식")
        set_job_techs(cur, job_a, ["Windows", "dev"])
        db.commit()
        cur.execute("SELECT * FROM v_job WHERE id=%s", (job_a,))
        v = cur.fetchone()
        check("dev" not in (v["tech_stack"] or []), "노이즈 기술은 tech_stack 에서 빠진다",
              str(v["tech_stack"]))
        check(v["job_key"] == "wanted-1", "job_key 가 /jobs/<site>-<pid> 와 같다")
        need = {"site", "pid", "url", "company", "title", "career_text", "location_text",
                "tech_stack", "main_tasks", "qualifications", "preferences", "benefits",
                "full_jd", "status", "deadline_on", "dday", "employment", "education"}
        check(need <= set(v.keys()), "뷰어가 쓰는 필드가 전부 있다",
              str(sorted(need - set(v.keys()))))

        # ── 6. 벡터: 유사도 밴드와 회사 상한 ───────────────────────
        print("\n[6] 유사 공고 (결정적 벡터)")
        cur.execute("SELECT id FROM company")
        c1 = cur.fetchone()["id"]
        c2 = upsert_company(cur, "다른회사")
        # A 를 기준으로: B=0.80(밴드 안) · C=0.999(중복) · D=0.0(너무 멂)
        vecs = {
            "A": unit((0, 1.0)),
            "B": unit((0, 0.8), (1, 0.6)),
            "C": unit((0, 1.0), (1, 0.02)),
            "D": unit((2, 1.0)),
        }
        made = {}
        for i, (name, vec) in enumerate(vecs.items(), start=100):
            jid, _ = upsert_job(cur, {**base, "pid": str(i),
                                      "url": f"https://a.test/{i}",
                                      "company_id": c1 if name in ("A", "B") else c2,
                                      "content_hash": f"v{i}"})
            made[name] = jid
            cur.execute("""INSERT INTO job_embedding (job_id, model, content_hash, embedding)
                           VALUES (%s,'test',%s,%s)""", (jid, f"v{i}", str(vec)))
        db.commit()

        from store import similar as sim_mod
        n = sim_mod.compute("job")
        cur.execute("""SELECT k.pid, round(s.score::numeric,3) score
                         FROM job_similar s JOIN job k ON k.id=s.similar_id
                        WHERE s.job_id=%s ORDER BY s.rank""", (made["A"],))
        rows = cur.fetchall()
        got = {r["pid"] for r in rows}
        check(got == {"101"}, "A 의 추천은 B 하나뿐 (C=중복 제외, D=점수 미달)",
              f"실제 {sorted(got)} · 전체 {n}쌍")

        # ── 7. dump_json 이 뷰어 형식과 맞는가 ─────────────────────
        print("\n[7] similar_jobs.json 형식 (useSimilar.ts 와 대조)")
        import tempfile
        tmp = _Path(tempfile.mkdtemp()) / "similar_jobs.json"
        old_out = sim_mod.SIMILAR_JOBS_JSON
        sim_mod.SIMILAR_JOBS_JSON = tmp
        try:
            sim_mod.dump_json("job")
        finally:
            sim_mod.SIMILAR_JOBS_JSON = old_out
        f = json.loads(tmp.read_text(encoding="utf-8"))
        check(isinstance(f.get("docs"), dict) and isinstance(f.get("similar"), dict),
              "docs·similar 이 둘 다 map 이다")
        import hashlib
        aid = hashlib.sha1(b"https://a.test/100").hexdigest()[:16]
        check(aid in f["docs"], "문서 키가 sha1(url)[:16] 이다")
        check(set(f["docs"][aid]) == {"u", "c", "t"}, "docs 항목이 {u,c,t} 다",
              str(f["docs"].get(aid)))
        pair = (f["similar"].get(aid) or [[None, None]])[0]
        check(isinstance(pair, list) and len(pair) == 2 and isinstance(pair[1], float),
              "similar 항목이 [대상id, 점수] 다", str(pair))

        # ── 8. 검색: FTS + 마감 제외 ───────────────────────────────
        print("\n[8] 검색")
        cur.execute("SELECT count(*) n FROM search_jobs('백엔드', %s, 10, false)",
                    (str(vecs["A"]),))
        n_open = cur.fetchone()["n"]
        cur.execute("SELECT count(*) n FROM search_jobs('백엔드', %s, 10, true)",
                    (str(vecs["A"]),))
        n_all = cur.fetchone()["n"]
        check(n_open >= 1, "하이브리드 검색이 결과를 낸다", f"{n_open}건")
        check(n_all >= n_open, "마감 포함이 더 많거나 같다", f"{n_open} vs {n_all}")
        cur.execute("""SELECT count(*) n FROM search_jobs('백엔드', %s, 50, false) s
                         JOIN v_job v ON v.id=s.job_id WHERE v.status='closed'""",
                    (str(vecs["A"]),))
        check(cur.fetchone()["n"] == 0, "기본 검색에 마감 공고가 없다")

        # CLI 진입점. Ollama 가 없을 때 FTS 로 떨어지는 길이 살아 있어야 한다.
        db.commit()
        from store.search import search as cli_search
        hits = cli_search("백엔드", 5, False, use_vector=False)
        check(bool(hits) and {"company", "title", "status"} <= set(hits[0]),
              "store.search CLI 가 화면에 쓸 필드를 채워 돌려준다",
              str(sorted(hits[0])[:6]) if hits else "결과 없음")

        # ── 9. 임베딩 대기열 ───────────────────────────────────────
        print("\n[9] 증분 임베딩 대기열")
        cur.execute("SELECT count(*) n FROM job_embed_pending")
        before = cur.fetchone()["n"]
        cur.execute("UPDATE job SET content_hash='changed' WHERE id=%s", (made["A"],))
        cur.execute("SELECT count(*) n FROM job_embed_pending")
        check(cur.fetchone()["n"] == before + 1,
              "본문이 바뀌면 재임베딩 대상이 된다")

        db.commit()

        # ── 10. 이중 쓰기: 사라짐 처리와 급감 가드 ─────────────────
        # 여기가 제일 위험한 코드다. 크롤이 차단당해 몇 건만 들어왔을 때 나머지를
        # "사라졌다"고 찍으면 close_check 가 헛돌고 화면에서도 근거 없이 사라진다.
        print("\n[10] 크롤 이중 쓰기 (store.ingest_crawl)")
        from store.ingest_crawl import ingest as crawl_ingest

        feed = [
            {"site": "jumpit", "pid": f"9{i}", "url": f"https://j.test/9{i}",
             "company": "점핏시험사", "title": f"공고 {i}", "tech_stack": ["Java"],
             "deadline": "", "dday": ""}
            for i in range(6)
        ]

        def alive_jumpit():
            cur.execute("SELECT count(*) n FROM job WHERE site='jumpit' AND gone_at IS NULL")
            return cur.fetchone()["n"]

        s1 = crawl_ingest(feed, label="t1", site_counts={"jumpit": 6})
        check(s1["new"] == 6 and alive_jumpit() == 6, "① 첫 투입 → 신규 6건",
              f"신규 {s1['new']} · 살아있음 {alive_jumpit()}")

        s2 = crawl_ingest(feed, label="t2", site_counts={"jumpit": 6})
        check(s2["new"] == 0 and s2["gone"] == 0, "② 같은 것 재투입 → 아무 일 없음(멱등)",
              str({k: s2[k] for k in ("new", "gone", "reopened")}))

        s3 = crawl_ingest(feed[:5], label="t3", site_counts={"jumpit": 5})
        check(s3["gone"] == 1 and alive_jumpit() == 5,
              "③ 1건 누락 → 그 1건만 사라짐 처리",
              f"사라짐 {s3['gone']} · 살아있음 {alive_jumpit()}")

        s4 = crawl_ingest(feed[:2], label="t4", site_counts={"jumpit": 2})
        check(s4["gone"] == 0 and s4["gone_skipped_sites"] and alive_jumpit() == 5,
              "④ 2건만 옴(부분 크롤) → 급감 가드가 막는다",
              f"사라짐 {s4['gone']} · 보류 {s4['gone_skipped_sites']}")

        s5 = crawl_ingest(feed, label="t5", site_counts={"jumpit": 6})
        check(s5["reopened"] == 1 and alive_jumpit() == 6,
              "⑤ 전량 복귀 → 아까 1건이 되살아난다",
              f"재등장 {s5['reopened']}")

        cur.execute("""SELECT kind, count(*) n FROM job_event e JOIN job j ON j.id=e.job_id
                        WHERE j.site='jumpit' GROUP BY kind""")
        ev = {r["kind"]: r["n"] for r in cur.fetchall()}
        check(ev.get("appeared") == 6 and ev.get("disappeared") == 1
              and ev.get("reopened") == 1, "이벤트가 남는다", str(ev))

        # 결측 레코드는 트랜잭션을 깨지 않고 세어서 넘어간다
        s6 = crawl_ingest(
            feed + [{"site": "jumpit", "pid": "bad", "url": "https://j.test/bad",
                     "company": "", "title": "회사 없는 공고"}],
            label="t6", site_counts={"jumpit": 7})
        check(s6["skipped"] == 1 and s6["usable"] == 6,
              "회사명 없는 공고는 세어서 건너뛴다(사이클을 안 죽인다)",
              str({k: s6[k] for k in ("usable", "skipped")}))

        # ── 11. 임베딩 배치 ────────────────────────────────────────
        # Ollama 는 없으니 HTTP 호출만 가짜로 바꾼다. 그 바깥의 SQL·배치·저장
        # 경로는 실제 코드가 그대로 돈다.
        # HTTP 호출(`_post`)만 대역으로 바꾼다. `embed_batch` 자체는 실제 코드가
        # 돌아야 한다 — 정규화와 차원 검사가 거기 들어 있고, 그게 이 모듈에서 가장
        # 중요한 방어선이다. 함수째로 대역하면 그 검사를 시험하지 못한다.
        print("\n[11] 임베딩 배치 (Ollama HTTP 만 대역)")
        from store import embed as embed_mod
        real_post, real_check = embed_mod._post, embed_mod.check_model
        embed_mod.check_model = lambda: None
        dim = [embed_mod.EMBED_DIM]

        def fake_post(path, payload, timeout):
            n = len(payload["input"])
            # 정규화 전 값을 준다 — embed_batch 가 L2 정규화하는지도 함께 본다.
            return {"embeddings": [[3.0 if i == k % dim[0] else 0.0
                                    for i in range(dim[0])] for k in range(n)]}

        embed_mod._post = fake_post
        embed_mod.RETRY_WAIT = 0        # 실패 시험에서 15초를 기다릴 이유가 없다
        try:
            cur.execute("SELECT count(*) n FROM job_embed_pending")
            pending = cur.fetchone()["n"]
            done = embed_mod.run("job", None, False)
            check(done == pending, "대기분을 전부 임베딩한다", f"{done}/{pending}")
            cur.execute("SELECT count(*) n FROM job_embed_pending")
            check(cur.fetchone()["n"] == 0, "임베딩 후 대기열이 빈다")
            cur.execute("SELECT count(*) n FROM job_embedding WHERE model = %s",
                        (embed_mod.EMBED_MODEL,))
            check(cur.fetchone()["n"] > 0, "모델 이름이 함께 기록된다")
            cur.execute("SELECT round((embedding <#> embedding)::numeric, 4) d "
                        "FROM job_embedding LIMIT 1")
            check(abs(float(cur.fetchone()["d"]) + 1.0) < 1e-3,
                  "벡터가 L2 정규화되어 저장된다(자기 내적 = 1)")

            # 모델을 갈아탔는데 눈치 못 채면 차원이 다른 벡터가 섞여 추천이 조용히
            # 망가진다. embed_batch 가 DB 에 닿기 전에 막아야 한다.
            dim[0] = 8
            cur.execute("UPDATE job SET content_hash = content_hash || 'x'")
            db.commit()
            try:
                embed_mod.run("job", 1, False)
                check(False, "차원이 다른 벡터는 DB 에 닿기 전에 거부된다", "그냥 통과했다")
            except embed_mod.EmbedError as e:
                check("차원" in str(e), "차원이 다른 벡터는 DB 에 닿기 전에 거부된다", str(e)[:60])
            except Exception as e:
                check(False, "차원이 다른 벡터는 DB 에 닿기 전에 거부된다",
                      f"DB 까지 갔다: {type(e).__name__}")
        finally:
            embed_mod._post, embed_mod.check_model = real_post, real_check

        # ── 12. sqlite-vec → pgvector 이관 ─────────────────────────
        print("\n[12] 벡터 이관 (store.migrate_vectors)")
        ok_mig = _test_migrate(cur, db)
        check(ok_mig is True, "SQLite 의 벡터가 URL 로 이어져 옮겨진다", str(ok_mig))

    return 0


def _test_migrate(cur, db) -> object:
    """작은 semantic.db 를 만들어 실제 이관 코드를 돌린다."""
    import sqlite3
    import struct
    import tempfile

    import sqlite_vec

    from store import migrate_vectors as mig

    cur.execute("SELECT url FROM job ORDER BY id LIMIT 2")
    urls = [r["url"] for r in cur.fetchall()]
    if len(urls) < 2:
        return "시험할 공고가 모자란다"

    path = _Path(tempfile.mkdtemp()) / "semantic.db"
    lite = sqlite3.connect(path)
    lite.enable_load_extension(True)
    sqlite_vec.load(lite)
    lite.executescript("""
        CREATE TABLE documents (rowid INTEGER PRIMARY KEY, id TEXT, kind TEXT,
            url TEXT UNIQUE, embed_model TEXT, embedded_hash TEXT);
    """)
    lite.execute("CREATE VIRTUAL TABLE vec_documents USING vec0(embedding float[1024])")
    for i, u in enumerate(urls, start=1):
        vec = unit((i, 1.0))
        lite.execute(
            "INSERT INTO documents (rowid,id,kind,url,embed_model,embedded_hash) "
            "VALUES (?,?,'job',?,'bge-m3','done')", (i, f"id{i}", u))
        lite.execute("INSERT INTO vec_documents (rowid, embedding) VALUES (?,?)",
                     (i, struct.pack(f"{len(vec)}f", *vec)))
    lite.commit()
    lite.close()

    cur.execute("DELETE FROM job_embedding")
    db.commit()
    saved = _sys.argv
    _sys.argv = ["migrate_vectors", "--db", str(path), "--kind", "job"]
    try:
        mig.main()
    finally:
        _sys.argv = saved

    cur.execute("SELECT count(*) n FROM job_embedding")
    n = cur.fetchone()["n"]
    if n != len(urls):
        return f"{n}건만 옮겨졌다(기대 {len(urls)})"
    # 이관된 벡터의 content_hash 는 **job 의 현재 값**이어야 한다. SQLite 쪽 값을
    # 그대로 쓰면 다음 embed 배치가 옮겨 온 것까지 전부 재임베딩 대상으로 잡는다
    # — 1만 건이면 M1 에서 한 시간이 넘고, 이관의 의미가 사라진다.
    # (옮기지 않은 공고가 대기로 남는 것은 정상이라 옮긴 것만 확인한다.)
    cur.execute("SELECT count(*) n FROM job_embed_pending p "
                " JOIN job j ON j.id = p.id WHERE j.url = ANY(%s)", (urls,))
    still = cur.fetchone()["n"]
    if still:
        return f"옮긴 {len(urls)}건 중 {still}건이 여전히 재임베딩 대기다"
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="정본 DB 계층 자체 검사")
    ap.add_argument("--keep", action="store_true", help="끝나고 시험용 DB 를 남긴다")
    args = ap.parse_args()

    print(f"시험용 DB: {_test_dsn()}")
    make_db()
    # 이 시점부터 store.* 가 여는 모든 커넥션이 시험 DB 로 간다.
    os.environ["JOBSEEKER_DSN"] = _test_dsn()
    try:
        run()
    finally:
        if not args.keep:
            drop_db()

    total = _passes + len(_fails)
    print(f"\nstore selftest: {_passes}/{total} 통과")
    for f in _fails:
        print(f"  실패: {f}")
    return 1 if _fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
