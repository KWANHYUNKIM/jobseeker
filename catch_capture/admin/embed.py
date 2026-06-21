"""의미 기반 적합도(임베딩) — 프로필 ↔ JD 의미 유사도(무료·로컬).

키워드 매칭(match.py)은 사전에 등록된 기술 단어가 '정확히' 나와야만 잡는다.
긴 자연어 서술·동의어·개념(예: "고성능 거래 시스템 운영" ↔ "대용량 트래픽 백엔드")은
표현이 다르면 전부 놓친다. 여기서는 텍스트를 벡터로 변환해 코사인 유사도로
'의미가 비슷한지'를 본다 — 이게 RAG의 검색(R) 부분이다.

설계 노트(청킹 검토 후 기각): 긴 JD에서 핵심 요건이 묻히는 걸 막으려 문단/요건 단위
청킹(late-interaction MaxSim)을 구현해 실측 비교했으나, 이 정적 임베딩 모델에서는
짧은 조각이 무엇과도 적당히 매칭돼 노이즈가 되어 랭킹이 오히려 나빠졌다(백엔드
프로필이 프론트 공고를 상위로 올림). mean-pooling한 문서 단위 벡터가 주제 매칭을
가장 안정적으로 잡아, 단순한 doc-level 코사인을 채택했다.

model2vec 정적 임베딩: torch 불필요, CPU에서 즉시, 완전 로컬·무료.
서버 부팅을 막지 않도록 모델은 첫 사용 시 지연 로드한다. 모델이 없거나(미설치/오프라인)
로드에 실패하면 available()=False가 되고, 호출부는 키워드 점수만으로 폴백한다.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from typing import Any

import numpy as np

from . import store

# 다국어 정적 임베딩(한국어 포함). 최초 사용 시 HuggingFace에서 1회 다운로드.
MODEL_NAME = "minishlab/potion-multilingual-128M"
_CACHE_FILE = store.DATA_DIR / "embed_cache.npz"

# 코사인 유사도(0~1)를 0~100 점수로 보정하는 휴리스틱.
# 실측 기준: 무관 JD ~0.34, 의미일치 ~0.63, 키워드일치 ~0.70~0.76.
# 데이터를 보고 조정 가능 — LOW 이하는 0점, HIGH 이상은 100점.
_COS_LOW = 0.30
_COS_HIGH = 0.75

# 블렌드 가중치: 강한 신호가 점수를 주도하고 약한 신호가 보정.
# 키워드 0이어도 의미점수가 높으면 적합으로 인정되도록 max에 큰 가중을 둔다.
_HI_W = 0.7
_LO_W = 0.3

# JD 섹션 배점(지원자격 > 주요업무 > 우대). 잡 벡터를 섹션별로 만들어 가중 평균한다.
# required = 지원자격+기술스택+제목(필수), tasks = 주요업무, preferred = 우대(가산점).
SECTION_WEIGHTS = {"required": 0.5, "tasks": 0.3, "preferred": 0.2}

_model = None
_load_failed = False
# 잡 임베딩 디스크 캐시: job_key -> (content_hash, vector)
_cache: dict[str, tuple[str, np.ndarray]] | None = None
_dirty = False
# 프로필 임베딩 메모리 캐시: (content_hash, vector)
_profile_cache: tuple[str, np.ndarray] | None = None


# ── 모델 (지연 로드) ────────────────────────────────────────
def _get_model():
    global _model, _load_failed
    if _model is None and not _load_failed:
        try:
            from model2vec import StaticModel
            _model = StaticModel.from_pretrained(MODEL_NAME)
        except Exception:  # noqa: BLE001 (미설치/오프라인/다운로드 실패 → 키워드 폴백)
            _load_failed = True
    return _model


def available() -> bool:
    """임베딩 사용 가능 여부. False면 호출부는 키워드 점수만 쓴다."""
    return _get_model() is not None


def _encode(texts: list[str]) -> np.ndarray:
    """텍스트 → 정규화된 벡터(내적 = 코사인 유사도)."""
    m = _get_model()
    v = np.asarray(m.encode(texts), dtype=np.float32)
    if v.ndim == 1:
        v = v[None, :]
    norm = np.linalg.norm(v, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return v / norm


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ── 텍스트 직렬화 ───────────────────────────────────────────
def _flat(v: Any) -> str:
    if isinstance(v, list):
        return " ".join(_flat(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_flat(x) for x in v.values())
    return str(v or "")


def _job_weighted(job: dict[str, Any]) -> tuple[str | None, list[float], list[str]]:
    """JD 섹션 → (캐시해시, 가중치들, 텍스트들). 빈 섹션 제외 후 가중치 재정규화."""
    from . import jd_sections
    secs = jd_sections.sections(job)
    pairs = [(SECTION_WEIGHTS[k], secs[k]) for k in ("required", "tasks", "preferred")
             if secs[k].strip()]
    if not pairs:
        return None, [], []
    tot = sum(w for w, _ in pairs)
    weights = [w / tot for w, _ in pairs]
    texts = [t for _, t in pairs]
    h = _hash("||".join(f"{w:.3f}:{t}" for w, t in zip(weights, texts)))
    return h, weights, texts


def _combine(vecs: np.ndarray, weights: list[float]) -> np.ndarray:
    """섹션 벡터들의 가중 평균 → 정규화(코사인용)."""
    v = np.average(vecs, axis=0, weights=weights).astype(np.float32)
    n = float(np.linalg.norm(v)) or 1.0
    return v / n


def _profile_text(profile: dict[str, Any]) -> str:
    parts = [_flat(profile.get("headline")), _flat(profile.get("summary")),
             _flat(profile.get("skills"))]
    for exp in profile.get("experiences", []) or []:
        parts.append(_flat(exp.get("role")))
        parts.append(_flat(exp.get("bullets")))
    for pr in profile.get("projects", []) or []:
        parts.append(_flat(pr.get("stack")))
        parts.append(_flat(pr.get("bullets")))
    return "\n".join(p for p in parts if p.strip()).strip()


# ── 디스크 캐시 ─────────────────────────────────────────────
def _load_cache() -> dict[str, tuple[str, np.ndarray]]:
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    if _CACHE_FILE.is_file():
        try:
            d = np.load(_CACHE_FILE, allow_pickle=True)
            for k, h, row in zip(d["keys"], d["hashes"], d["vecs"]):
                _cache[str(k)] = (str(h), row.astype(np.float32))
        except Exception:  # noqa: BLE001 (손상 캐시 → 무시하고 재생성)
            _cache = {}
    return _cache


def save_cache() -> None:
    """변경분이 있으면 캐시를 원자적으로 저장(잡 임베딩 재계산 방지)."""
    global _dirty
    if not _dirty or not _cache:
        return
    keys = np.array(list(_cache.keys()), dtype=object)
    hashes = np.array([h for h, _ in _cache.values()], dtype=object)
    vecs = np.stack([v for _, v in _cache.values()])
    store._ensure_dirs()
    fd, tmp = tempfile.mkstemp(dir=str(_CACHE_FILE.parent), suffix=".npz")
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez(f, keys=keys, hashes=hashes, vecs=vecs)
        os.replace(tmp, _CACHE_FILE)
        _dirty = False
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ── 공개 API ────────────────────────────────────────────────
def profile_vector(profile: dict[str, Any]) -> np.ndarray | None:
    """프로필 의미 벡터(없으면 None). 같은 프로필은 메모리 캐시."""
    global _profile_cache
    if not available():
        return None
    text = _profile_text(profile)
    if not text:
        return None
    h = _hash(text)
    if _profile_cache and _profile_cache[0] == h:
        return _profile_cache[1]
    vec = _encode([text])[0]
    _profile_cache = (h, vec)
    return vec


def ensure_jobs(jobs: list[dict[str, Any]]) -> None:
    """후보 잡들의 임베딩을 캐시에 채운다 — 미스만 한 번에 배치 인코딩(빠름)."""
    global _dirty
    if not available():
        return
    from .jobs import job_key
    cache = _load_cache()
    pending: list[tuple[str, str, list[float], int]] = []  # (key, hash, weights, n_sections)
    flat: list[str] = []
    for j in jobs:
        h, weights, texts = _job_weighted(j)
        if not texts:
            continue
        key = job_key(j)
        cur = cache.get(key)
        if cur and cur[0] == h:
            continue
        pending.append((key, h, weights, len(texts)))
        flat.extend(texts)
    if not pending:
        return
    vecs = _encode(flat)  # 전 섹션 한 번에 인코딩 → 잡별로 가중 결합
    off = 0
    for key, h, weights, n in pending:
        cache[key] = (h, _combine(vecs[off:off + n], weights))
        off += n
    _dirty = True


def semantic_score(profile_vec: np.ndarray | None, job: dict[str, Any]) -> int:
    """프로필↔JD 의미 적합도 0~100. 모델/벡터/텍스트 없으면 0."""
    if profile_vec is None or not available():
        return 0
    from .jobs import job_key
    cur = _load_cache().get(job_key(job))
    if cur is not None:
        vec = cur[1]
    else:  # ensure_jobs 미경유 — 단건 인코딩(캐시는 안 함)
        h, weights, texts = _job_weighted(job)
        if not texts:
            return 0
        vec = _combine(_encode(texts), weights)
    cos = float(np.dot(profile_vec, vec))
    pct = (cos - _COS_LOW) / (_COS_HIGH - _COS_LOW)
    return max(0, min(100, round(pct * 100)))


def blend(kw_score: int, sem_score: int) -> int:
    """키워드(정밀) + 의미(긴 텍스트 인식) 종합. 강한 신호 주도 + 약한 신호 보정."""
    hi, lo = (kw_score, sem_score) if kw_score >= sem_score else (sem_score, kw_score)
    return round(hi * _HI_W + lo * _LO_W)
