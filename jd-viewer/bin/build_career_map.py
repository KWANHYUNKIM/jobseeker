#!/usr/bin/env python3
"""커리어 맵 빌더 — JD 임베딩 군집 + 군집 간 인접도 + 이동 시 기술 격차.

입력: catch_capture/semantic.db  (documents + vec_documents, bge-m3 1024d, 정규화 완료)
출력: jd-viewer/public/career_map.json

**기존 mindmap 과 무엇이 다른가.**
build_mindmap.py 는 도메인 → 기업 → 직군 → 스택 을 문자열 규칙으로 세운다. 좋은
'채용 기업 디렉터리'지만 커리어 맵은 아니다. 직군은 하드코딩된 11개 라벨이고, 어떤
직군에서 어떤 직군으로 갈 수 있는지, 가려면 무엇이 비는지는 답하지 않는다.

여기서는 세 가지를 임베딩에서 끌어낸다. 전부 규칙으로는 못 구하는 것들이다.

1. 군집 = 시장이 실제로 나뉘어 있는 모양. 라벨을 미리 정하지 않는다. '백엔드'가
   커머스 트래픽 / 금융 정산 / 사내 플랫폼으로 갈라지면 갈라진 채로 나온다.
2. 인접도 = 군집 중심 간 코사인. JD 문맥이 가까운 군집이 곧 현실적인 다음 자리다.
   같은 직군 라벨이어도 도메인이 멀면 멀게 나오고, 라벨이 달라도 하는 일이 겹치면
   가깝게 나온다 — 라벨 기반 규칙이 절대 못 하는 부분이다.
3. 격차 = A→B 로 갈 때 B 에는 흔한데 A 에는 드문 기술. 이게 '무엇을 공부할 것인가'다.

라벨링은 빈도가 아니라 '변별력(lift)'으로 뽑는다. 빈도로 뽑으면 모든 군집이
Python·AWS 로 라벨링된다 — 그건 군집의 특징이 아니라 시장 전체의 배경이다.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import sqlite_vec

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "catch_capture" / "semantic.db"
OUT = ROOT / "jd-viewer" / "public" / "career_map.json"

K = int(sys.argv[1]) if len(sys.argv) > 1 else 28
SEED = 20260819           # 고정 시드 — 같은 데이터면 같은 맵이 나와야 비교가 가능하다
ITERS = 40
NEIGHBORS = 4             # 군집당 인접 군집 수
MIN_TECH_JOBS = 5         # 라벨/격차에 쓸 기술의 군집 내 최소 등장 건수
MIN_TECH_SHARE = 0.08     # 군집 내 최소 등장 비율
GAP_MIN_SHARE = 0.15      # '격차'로 부를 최소 목표군집 점유율
SAMPLES = 4               # 군집당 대표 공고 수

# 직군/도메인 라벨에 쓸 제목 토큰에서 걸러낼 잡음
# 라벨에 들어가면 군집을 구분해주지 못하는 토큰들. 고용형태·연차·모집 문구는 어느
# 군집에나 고르게 퍼져 있어서 lift 가 우연히 튀면 라벨을 통째로 잡아먹는다
# ('python · it · 경력직' 같은 라벨이 그렇게 나왔다).
STOP = {
    "개발자", "개발", "엔지니어", "채용", "경력", "신입", "정규직", "및", "담당자",
    "modal", "engineer", "developer", "senior", "junior", "lead", "the", "and",
    "for", "with", "팀원", "모집", "부문", "직무", "포지션", "이상", "년차",
    "인턴", "경력직", "계약직", "체험형", "전환형", "수시", "상시", "공고",
    "서비스", "사업", "관련", "우대", "담당", "직원", "인재", "지원", "모집중",
    "it", "job", "team", "new", "hiring", "recruit", "full", "time", "부서",
    "전문가", "리드", "총괄", "파트", "그룹", "본부", "센터", "회사", "기업",
}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.]{1,}|[가-힣]{2,}")


def load() -> tuple[np.ndarray, list[dict]]:
    """임베딩 행렬과 문서 메타를 같은 순서로 반환."""
    if not DB.exists():
        raise SystemExit(f"[career-map] semantic.db 가 없습니다: {DB}")
    con = sqlite3.connect(DB)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)

    rows = con.execute(
        """
        SELECT d.id, d.company, d.title, d.url, d.site, d.meta, v.embedding
        FROM documents d JOIN vec_documents v ON v.rowid = d.rowid
        WHERE d.kind = 'job'
        """
    ).fetchall()
    con.close()
    if not rows:
        raise SystemExit("[career-map] job 임베딩이 없습니다.")

    vecs = np.empty((len(rows), 1024), dtype=np.float32)
    docs: list[dict] = []
    for i, (id_, company, title, url, site, meta, emb) in enumerate(rows):
        vecs[i] = np.frombuffer(emb, dtype=np.float32)
        m = {}
        if meta:
            try:
                m = json.loads(meta)
            except json.JSONDecodeError:
                m = {}
        docs.append({
            "id": id_, "company": company or "", "title": title or "",
            "url": url or "", "site": site or "",
            "tech": [t for t in (m.get("tech_stack") or []) if t],
            "career": m.get("career") or "",
        })
    # 저장 시점에 정규화돼 있지만(‖v‖=1) 재임베딩·모델 교체 이력이 섞일 수 있어 한 번 더 맞춘다.
    vecs /= np.clip(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9, None)
    return vecs, docs


def kmeans(x: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """구면 k-means. 벡터가 단위길이라 코사인 = 내적이고, 중심도 매번 정규화한다."""
    rng = np.random.default_rng(SEED)
    n = x.shape[0]

    # k-means++ 초기화. 무작위 초기화는 빈 군집과 실행마다 다른 맵을 만든다.
    centers = np.empty((k, x.shape[1]), dtype=np.float32)
    centers[0] = x[rng.integers(n)]
    closest = x @ centers[0]
    for i in range(1, k):
        d = np.clip(1.0 - closest, 0, None) ** 2
        total = float(d.sum())
        idx = int(rng.integers(n)) if total <= 0 else int(rng.choice(n, p=d / total))
        centers[i] = x[idx]
        closest = np.maximum(closest, x @ centers[i])

    labels = np.zeros(n, dtype=np.int32)
    for _ in range(ITERS):
        sim = x @ centers.T                 # (n, k) 코사인
        new = sim.argmax(axis=1).astype(np.int32)
        if np.array_equal(new, labels):
            break
        labels = new
        for i in range(k):
            members = x[labels == i]
            if len(members) == 0:
                # 빈 군집은 가장 외로운 점으로 되살린다. 그냥 두면 k 가 조용히 줄어든다.
                centers[i] = x[int((x @ centers.T).max(axis=1).argmin())]
                continue
            c = members.mean(axis=0)
            centers[i] = c / max(float(np.linalg.norm(c)), 1e-9)
    return labels, centers


def lift_terms(member_counts: Counter, member_n: int,
               corpus_counts: Counter, corpus_n: int,
               min_n: int, min_share: float, top: int) -> list[dict]:
    """군집을 '설명하는' 항목 = 전체 대비 과대표집된 항목.

    빈도 상위를 그냥 쓰면 어느 군집이든 Python·AWS 가 1등이다. 그건 군집의 특징이
    아니라 시장의 배경이라, 군집끼리 구분이 되지 않는다.
    """
    out = []
    for term, n in member_counts.items():
        if n < min_n:
            continue
        share = n / member_n
        if share < min_share:
            continue
        base = corpus_counts.get(term, 0) / corpus_n
        if base <= 0:
            continue
        out.append({
            "name": term,
            "n": n,
            "share": round(100 * share, 1),
            "lift": round(share / base, 2),
        })
    # 변별력 우선, 동률이면 규모
    out.sort(key=lambda t: (-t["lift"], -t["n"]))
    return out[:top]


def main() -> None:
    vecs, docs = load()
    n = len(docs)
    print(f"[career-map] job 임베딩 {n:,}건 · k={K}", flush=True)

    labels, centers = kmeans(vecs, K)

    # 코퍼스 배경 분포
    corpus_tech = Counter()
    corpus_tok = Counter()
    for d in docs:
        for t in set(d["tech"]):
            corpus_tech[t] += 1
        for tok in set(TOKEN_RE.findall(d["title"].lower())):
            if tok not in STOP and len(tok) > 1:
                corpus_tok[tok] += 1

    clusters = []
    for i in range(K):
        idx = np.where(labels == i)[0]
        if len(idx) == 0:
            continue
        members = [docs[j] for j in idx]
        m_n = len(members)

        tech_c, tok_c, comp_c, band_c = Counter(), Counter(), Counter(), Counter()
        for d in members:
            for t in set(d["tech"]):
                tech_c[t] += 1
            for tok in set(TOKEN_RE.findall(d["title"].lower())):
                if tok not in STOP and len(tok) > 1:
                    tok_c[tok] += 1
            if d["company"]:
                comp_c[d["company"]] += 1
            if d["career"]:
                band_c[d["career"]] += 1

        tech = lift_terms(tech_c, m_n, corpus_tech, n, MIN_TECH_JOBS, MIN_TECH_SHARE, 12)
        toks = lift_terms(tok_c, m_n, corpus_tok, n, 4, 0.05, 8)

        # 대표 공고 = 중심에 가장 가까운 것들. '평균적인' 공고라 군집을 눈으로 확인하기 좋다.
        sim = vecs[idx] @ centers[i]
        order = idx[np.argsort(-sim)]
        samples = [{
            "title": docs[j]["title"], "company": docs[j]["company"],
            "url": docs[j]["url"], "site": docs[j]["site"],
        } for j in order[:SAMPLES]]

        # 라벨: 변별력 있는 제목 토큰 우선, 모자라면 그 군집의 대표 기술로 채운다.
        # 제목이 '개발자 채용' 같은 공고가 몰린 군집은 토큰만으로는 이름이 안 나온다.
        parts = [t["name"] for t in toks[:3]]
        if len(parts) < 2:
            parts += [t["name"] for t in tech[:3] if t["name"] not in parts]
        label = " · ".join(parts[:3]) or f"군집 {i}"
        clusters.append({
            "id": i,
            "label": label,
            "size": m_n,
            "share": round(100 * m_n / n, 2),
            "terms": toks,
            "tech": tech,
            "companies": [{"name": c, "n": k} for c, k in comp_c.most_common(8)],
            "bands": [{"name": b, "n": k} for b, k in band_c.most_common(6)],
            "samples": samples,
            "cohesion": round(float(sim.mean()), 3),
        })

    # ── 인접도: 중심 간 코사인 ────────────────────────────────────────
    alive = [c["id"] for c in clusters]
    cmat = centers[alive] @ centers[alive].T
    np.fill_diagonal(cmat, -1.0)
    by_id = {c["id"]: c for c in clusters}
    tech_share = {
        c["id"]: {t["name"]: t["share"] / 100 for t in c["tech"]} for c in clusters
    }
    # 격차 계산에는 lift 로 자르기 전의 원 점유율이 필요하다.
    raw_share: dict[int, dict[str, float]] = {}
    for i in alive:
        idx = np.where(labels == i)[0]
        c = Counter()
        for j in idx:
            for t in set(docs[j]["tech"]):
                c[t] += 1
        raw_share[i] = {t: v / len(idx) for t, v in c.items()}

    for pos, cid in enumerate(alive):
        order = np.argsort(-cmat[pos])[:NEIGHBORS]
        edges = []
        for q in order:
            tid = alive[int(q)]
            src, dst = raw_share[cid], raw_share[tid]
            # B 에는 흔하고 A 에는 드문 기술 = 이동에 드는 학습 비용
            gap = [
                {
                    "name": t,
                    "to_share": round(100 * s, 1),
                    "from_share": round(100 * src.get(t, 0.0), 1),
                    "gap": round(100 * (s - src.get(t, 0.0)), 1),
                }
                for t, s in dst.items()
                if s >= GAP_MIN_SHARE and s - src.get(t, 0.0) >= 0.10
            ]
            gap.sort(key=lambda g: -g["gap"])
            edges.append({
                "to": tid,
                "to_label": by_id[tid]["label"],
                "similarity": round(float(cmat[pos][q]), 3),
                "gap": gap[:8],
                "shared": sorted(
                    (t for t in dst if dst[t] >= 0.2 and src.get(t, 0) >= 0.2),
                    key=lambda t: -dst[t],
                )[:6],
            })
        by_id[cid]["neighbors"] = edges

    clusters.sort(key=lambda c: -c["size"])
    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "semantic.db (bge-m3, 1024d)",
        "jobs": n,
        "k": K,
        "seed": SEED,
        "clusters": clusters,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[career-map] 군집 {len(clusters)}개 → {OUT} ({OUT.stat().st_size:,} bytes)")
    for c in clusters[:12]:
        techs = ", ".join(t["name"] for t in c["tech"][:4])
        print(f"  [{c['size']:>4}건 {c['share']:>5.2f}%] {c['label']:<38} {techs}")


if __name__ == "__main__":
    main()
