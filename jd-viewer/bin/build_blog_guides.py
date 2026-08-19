#!/usr/bin/env python3
"""자격조건·우대사항 → 읽을 기술 블로그 글 연결기.

입력: catch_capture/semantic.db          (job/post 임베딩, bge-m3 1024d)
      jd-viewer/public/all_jobs_enriched.json  (qualifications / preferences 원문)
출력: jd-viewer/public/blog_guides.json

**무엇을 푸는가.** 공고의 우대사항에는 "대용량 트래픽 처리 경험", "쿠버네티스 운영
경험" 같은 문장이 반복해서 나오는데, 정작 그걸 어디서 배우는지는 아무도 안 알려준다.
한편 tech_blogs 에는 그 주제를 실무에서 겪은 회사들이 쓴 글이 1,000편 넘게 있다.
둘을 이어 "이 요구사항을 채우려면 이 글을 읽어라"를 만든다.

**왜 키워드 검색이 아니라 임베딩인가.** 블로그 제목에 '대용량'이라는 단어가 없어도
그 글이 대용량 트래픽 이야기일 수 있다. 반대로 제목에 '쿠버네티스'가 있다고 그 글이
쿠버네티스 운영을 가르치는 것도 아니다(도입 후기일 수도, 사내 발표 요약일 수도 있다).
키워드는 표기를 맞추고 임베딩은 내용을 맞춘다.

**방법: 중심 차이(centroid difference).**
개념 C 를 요구하는 공고들의 임베딩 평균에서 전체 공고의 평균을 뺀다.

    v(C) = normalize( mean(공고 with C) - mean(전체 공고) )

전체 평균을 빼는 게 핵심이다. 빼지 않으면 v(C) 는 대부분 '한국어 채용공고'라는 공통
방향이고, 어떤 개념으로 검색하든 같은 글이 상위에 온다. 차이를 취하면 그 공통 성분이
사라지고 C 를 C 답게 만드는 방향만 남는다.

이 방식은 새로 임베딩을 만들지 않는다 — 이미 저장된 벡터의 산술만 쓴다. 8GB M1 에서
Ollama 를 다시 띄우지 않아도 되고, 크롤 사이클 끝에 붙여 돌리기 싸다.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import sqlite_vec

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "catch_capture" / "semantic.db"
JOBS = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
TRENDS = ROOT / "jd-viewer" / "public" / "trends.json"
OUT = ROOT / "jd-viewer" / "public" / "blog_guides.json"

TOP_POSTS = 8        # 개념/기술당 추천 글 수
MIN_JOBS = 30        # 이만큼도 안 요구하는 개념은 방향이 잡히지 않는다
MIN_SCORE = 0.05     # 이보다 낮으면 '가까운 글'이 아니라 그냥 목록 맨 위다

# pipeline/trends.py 의 CONCEPT_KEYWORDS 와 같은 축을 쓴다. 트렌드 탭에서 "이 개념이
# 공고의 몇 %" 를 보고 여기서 "그럼 뭘 읽지" 로 이어지려면 축이 같아야 한다.
sys.path.insert(0, str(ROOT / "catch_capture"))
from pipeline.trends import CONCEPT_KEYWORDS  # noqa: E402


def load_vectors() -> tuple[np.ndarray, list[dict], np.ndarray, list[dict]]:
    con = sqlite3.connect(DB)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    rows = con.execute(
        """
        SELECT d.kind, d.url, d.title, d.company, d.meta, v.embedding
        FROM documents d JOIN vec_documents v ON v.rowid = d.rowid
        WHERE d.kind IN ('job', 'post')
        """
    ).fetchall()
    con.close()

    jv, jd, pv, pd = [], [], [], []
    for kind, url, title, company, meta, emb in rows:
        vec = np.frombuffer(emb, dtype=np.float32)
        rec = {"url": url or "", "title": title or "", "company": company or "", "meta": meta}
        if kind == "job":
            jv.append(vec); jd.append(rec)
        else:
            pv.append(vec); pd.append(rec)
    j = np.asarray(jv, dtype=np.float32)
    p = np.asarray(pv, dtype=np.float32)
    for m in (j, p):
        m /= np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)
    return j, jd, p, pd


def direction(vecs: np.ndarray, idx: np.ndarray, base: np.ndarray) -> np.ndarray | None:
    """부분집합 중심에서 전체 중심을 뺀 방향(단위벡터)."""
    if len(idx) == 0:
        return None
    d = vecs[idx].mean(axis=0) - base
    n = float(np.linalg.norm(d))
    return d / n if n > 1e-6 else None


def _norm_title(t: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", (t or "").lower())[:60]


def top_posts(posts: list[dict], sims: np.ndarray, generic: np.ndarray,
              meta_by_url: dict) -> list[dict]:
    """한 방향에 대한 상위 글.

    순위는 raw 코사인이 아니라 `sim - generic` 으로 매긴다. generic 은 그 글이 **모든**
    개념 방향에 대해 갖는 평균 유사도다. 링크 모음/뉴스레터("FE News 26년 3월 소식")는
    온갖 주제를 조금씩 담고 있어 어떤 방향에서도 상위에 오는데, 정작 그 주제를 가르쳐
    주지는 않는다. 평균을 빼면 '모두에게 가까운 글'은 내려가고 '이 주제에 유독 가까운
    글'만 남는다 — 공고 쪽에서 전체 중심을 뺀 것과 같은 발상이다.

    제목이 사실상 같은 글(재게시·다국어 판)도 걸러낸다. 8칸 중 2칸을 같은 글이 먹으면
    추천의 폭이 그만큼 줄어든다.
    """
    adjusted = sims - generic
    out: list[dict] = []
    seen: set[str] = set()
    for i in np.argsort(-adjusted)[: TOP_POSTS * 8]:
        raw = float(sims[i])
        if raw < MIN_SCORE:
            break
        p = posts[i]
        key = _norm_title(p["title"])
        if key in seen:
            continue
        seen.add(key)
        extra = meta_by_url.get(p["url"], {})
        out.append({
            "title": p["title"],
            "company": p["company"] or extra.get("company", ""),
            "url": p["url"],
            "published": extra.get("published", ""),
            "score": round(raw, 3),
            "edge": round(float(adjusted[i]), 3),
            "tech": (extra.get("tech_stack") or [])[:5],
        })
        if len(out) >= TOP_POSTS:
            break
    return out


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"[blog-guides] semantic.db 가 없습니다: {DB}")
    jvec, jdocs, pvec, pdocs = load_vectors()
    print(f"[blog-guides] 공고 {len(jdocs):,} · 글 {len(pdocs):,}", flush=True)

    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    req_by_url = {
        j.get("url"): " ".join([j.get("qualifications") or "", j.get("preferences") or ""]).lower()
        for j in jobs if j.get("url")
    }
    stack_by_url = {j.get("url"): (j.get("tech_stack") or []) for j in jobs if j.get("url")}

    blogs = json.loads((ROOT / "jd-viewer" / "public" / "tech_blogs.json").read_text(encoding="utf-8"))
    blist = blogs if isinstance(blogs, list) else next(v for v in blogs.values() if isinstance(v, list))
    meta_by_url = {b["url"]: b for b in blist if b.get("url")}

    base = jvec.mean(axis=0)

    # ── 개념 축: 자격/우대 원문에 정규식이 걸린 공고들 ────────────────
    # 1단계: 모든 개념의 방향을 먼저 구한다. generic 을 계산하려면 전부 필요하다.
    prepared: list[tuple[str, np.ndarray, np.ndarray]] = []
    for label, pat in CONCEPT_KEYWORDS.items():
        rx = re.compile(pat, re.I)
        idx = np.array([i for i, d in enumerate(jdocs) if rx.search(req_by_url.get(d["url"], ""))],
                       dtype=np.int64)
        if len(idx) < MIN_JOBS:
            print(f"  - {label}: 공고 {len(idx)}건 — 표본 부족, 건너뜀")
            continue
        v = direction(jvec, idx, base)
        if v is not None:
            prepared.append((label, idx, v))

    dirs = np.stack([v for _, _, v in prepared])          # (개념, 1024)
    sim_matrix = pvec @ dirs.T                            # (글, 개념)
    generic = sim_matrix.mean(axis=1)                     # 글마다 '두루 가까운 정도'

    concepts = []
    for ci, (label, idx, _v) in enumerate(prepared):
        tc = Counter()
        for i in idx:
            for t in set(stack_by_url.get(jdocs[i]["url"], [])):
                tc[t] += 1
        posts = top_posts(pdocs, sim_matrix[:, ci], generic, meta_by_url)
        # 방향이 얼마나 또렷한가. 흔한 요구일수록(협업·오너십) 공고 중심이 전체 중심과
        # 거의 같아 방향이 약하고, 추천도 그만큼 일반적이 된다. 숨기지 말고 같이 낸다.
        sharpness = round(float(sim_matrix[:, ci].std()), 3)
        concepts.append({
            "name": label,
            "jobs": int(len(idx)),
            "job_pct": round(100 * len(idx) / len(jdocs), 1),
            "sharpness": sharpness,
            "tech": [{"name": t, "n": n} for t, n in tc.most_common(8)],
            "posts": posts,
        })
        print(f"  - {label}: 공고 {len(idx):,}건 → 글 {len(posts)}편 · 선명도 {sharpness}")

    # ── 기술 축: 수요 상위 기술별로 같은 계산 ─────────────────────────
    techs = []
    tracked = json.loads(TRENDS.read_text(encoding="utf-8")).get("tracked", []) if TRENDS.exists() else []
    tprep: list[tuple[str, int, np.ndarray]] = []
    for t in tracked:
        idx = np.array([i for i, d in enumerate(jdocs) if t in stack_by_url.get(d["url"], [])],
                       dtype=np.int64)
        if len(idx) < MIN_JOBS:
            continue
        v = direction(jvec, idx, base)
        if v is not None:
            tprep.append((t, int(len(idx)), v))
    if tprep:
        tdirs = np.stack([v for _, _, v in tprep])
        tsim = pvec @ tdirs.T
        tgen = tsim.mean(axis=1)
        for ti, (t, n, _v) in enumerate(tprep):
            posts = top_posts(pdocs, tsim[:, ti], tgen, meta_by_url)
            if posts:
                techs.append({"name": t, "jobs": n, "posts": posts})

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "method": "중심 차이(개념 요구 공고 평균 − 전체 공고 평균) 방향으로 글 코사인 랭킹",
        "jobs": len(jdocs),
        "posts": len(pdocs),
        "concepts": sorted(concepts, key=lambda c: -c["jobs"]),
        "techs": techs,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[blog-guides] 개념 {len(concepts)} · 기술 {len(techs)} → {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
