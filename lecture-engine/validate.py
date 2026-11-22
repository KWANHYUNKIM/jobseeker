"""강의 노트 검증 + 목록(index.json) 다시 굽기.

    python lecture-engine/validate.py            # 모든 노트 검사 → 통과하면 index.json 갱신
    python lecture-engine/validate.py --gaps     # 대기열에서 아직 노트가 없는 영상(다음 일감)

검사: 스키마 필수 항목·형식, 챕터 시각이 영상 길이 안·오름차순, 원문 대본을 길게 옮기지 않았나
(영어 문장이 노트에 통째로 들어가면 요약이 아니라 전재다).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "jd-viewer" / "public" / "lectures"
ITEMS = OUT / "items"
SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text(encoding="utf-8"))
QUEUE = Path(__file__).parent / "state" / "QUEUE.md"
# 깊이 기준(2026-11-20): CS231n 공식 노트가 강의 하나에 6천 단어 안팎이다. 한글로 강의 1분당 200자,
# 챕터 하나 600자 아래면 요약이지 노트가 아니다.
PER_MIN = 200
MIN_CHAPTER = 600

TOPIC_LABEL = {
    "llm": "LLM", "agents": "AI 에이전트", "ml-basics": "머신러닝 기초", "deep-learning": "딥러닝",
    "vision": "컴퓨터 비전", "nlp": "자연어 처리", "multimodal": "멀티모달", "systems": "AI 시스템·인프라",
    "rl": "강화학습", "data": "데이터", "career": "커리어·공부법", "other": "그 밖의",
    "coding-test": "코딩테스트", "backend": "백엔드", "frontend": "프론트엔드", "design": "디자인(UI·UX)",
    "detail-page": "상세페이지·포토샵", "toeic": "토익",
}
PATHS = Path(__file__).parent / "paths.json"
# 과목이 없는 노트(한 편짜리)를 트랙에 넣는 규칙 — topic 이 트랙 이름이면 그 트랙, 나머지는 AI.
TRACK_OF_TOPIC = {"coding-test": "coding-test", "backend": "backend", "frontend": "frontend", "design": "design",
                  "detail-page": "detail-page", "toeic": "toeic"}
IN_PROGRESS_SEC = 3 * 3600   # 재료를 받은 지 3시간 안인데 노트가 없으면 다른 회차가 쓰는 중으로 본다


def check(doc: dict, name: str) -> list[str]:
    errs: list[str] = []
    props = SCHEMA["properties"]
    for k in SCHEMA["required"]:
        if k not in doc or doc[k] in ("", [], None):
            errs.append(f"{name}: '{k}' 없음")
    if doc.get("topic") not in props["topic"]["enum"]:
        errs.append(f"{name}: topic '{doc.get('topic')}' 은 목록에 없다")
    if doc.get("level") not in props["level"]["enum"]:
        errs.append(f"{name}: level '{doc.get('level')}'")
    if name != f"{doc.get('id')}.json":
        errs.append(f"{name}: 파일 이름과 id 가 다르다")
    dur = (doc.get("source") or {}).get("duration_sec") or 10**9
    last = -1
    for i, c in enumerate(doc.get("chapters") or []):
        s = c.get("start")
        if not isinstance(s, int) or s < 0 or s > dur:
            errs.append(f"{name}: chapters[{i}].start {s} 가 영상 밖")
        elif s < last:
            errs.append(f"{name}: chapters[{i}] 시각이 거꾸로 간다")
        else:
            last = s
        if not c.get("points"):
            errs.append(f"{name}: chapters[{i}] points 없음")
        body = sum(len(x) for x in c.get("explain") or [])
        if body < MIN_CHAPTER:
            errs.append(f"{name}: chapters[{i}] '{c.get('title')}' 본문 {body}자 — {MIN_CHAPTER}자 이상")
        for k in ("formulas", "check"):
            for j, f in enumerate(c.get(k) or []):
                if not isinstance(f, dict) or not all(f.get(x) for x in (("expr", "meaning") if k == "formulas" else ("q", "a"))):
                    errs.append(f"{name}: chapters[{i}].{k}[{j}] 형식")
    # 깊이 — 노트만 읽고 공부할 수 있어야 한다. 강의 1분당 본문 PER_MIN 자.
    total = sum(len(x) for c in doc.get("chapters") or [] for x in c.get("explain") or [])
    need = int((dur if dur < 10**9 else 3600) / 60 * PER_MIN)
    if total < need:
        errs.append(f"{name}: 챕터 본문 합 {total}자 — 영상 {dur // 60}분이면 {need}자 이상")
    checks = sum(len(c.get("check") or []) for c in doc.get("chapters") or [])
    if checks < 5:
        errs.append(f"{name}: 확인 문제(check) {checks}개 — 5개 이상")
    for k in ("concepts",):
        for i, c in enumerate(doc.get(k) or []):
            if not c.get("term") or not c.get("explain"):
                errs.append(f"{name}: {k}[{i}] term/explain 없음")
    steps = (doc.get("study") or {}).get("steps") or []
    if len(steps) < 2:
        errs.append(f"{name}: study.steps 2개 이상")
    # 전재 검사 — 영어 단어 25개 넘게 이어지는 덩어리는 대본을 옮긴 것으로 본다.
    blob = json.dumps({k: doc.get(k) for k in ("summary", "concepts", "trends", "why_now")}, ensure_ascii=False) + json.dumps(
        [{k: v for k, v in c.items() if k not in ("code", "formulas", "diagram")} for c in doc.get("chapters") or []], ensure_ascii=False)
    for m in re.finditer(r"(?:[A-Za-z][A-Za-z'’-]*[ ,.]+){25,}", blob):
        errs.append(f"{name}: 영어 원문이 길게 들어 있다 — '{m.group(0)[:60]}…'")
        break
    errs += copied_from_transcript(doc, name)
    return errs


COPY_RUN = 40  # 공백을 뺀 글자 기준. 짧은 인용(질문 한 줄)은 두고, 문장째 옮긴 것은 막는다.
WORK = ROOT / "catch_capture" / "var" / "lectures"


def copied_from_transcript(doc: dict, name: str) -> list[str]:
    """한국어 영상은 영어 덩어리 검사로 전재를 못 잡는다 — 재료가 이 머신에 있으면 대본과 직접 맞대 본다."""
    t = WORK / str(doc.get("id")) / "transcript.txt"
    if not t.exists():
        return []
    src = re.sub(r"\[[\d:]+\]|\s+", "", t.read_text(encoding="utf-8"))
    parts = [doc.get("summary"), doc.get("why_now"), doc.get("concepts"), doc.get("trends"),
             [{k: v for k, v in c.items() if k not in ("code", "formulas", "diagram", "on_screen")} for c in doc.get("chapters") or []]]
    note = re.sub(r"\s+", "", json.dumps(parts, ensure_ascii=False))
    grams = {src[i:i + COPY_RUN] for i in range(len(src) - COPY_RUN + 1)}
    for i in range(len(note) - COPY_RUN + 1):
        if note[i:i + COPY_RUN] in grams:
            return [f"{name}: 대본을 {COPY_RUN}자 넘게 그대로 옮겼다 — '{note[i:i + COPY_RUN]}…'"]
    return []


def card(doc: dict) -> dict:
    s, c = doc["source"], doc["course"]
    return {
        "id": doc["id"], "title": doc["title"], "title_ko": doc["title_ko"],
        "school": c.get("school"), "code": c.get("code"), "term": c.get("term"), "speaker": c.get("speaker"),
        "topic": doc["topic"], "tags": doc.get("tags", [])[:8], "level": doc["level"],
        "one_line": doc["one_line"], "duration_sec": s.get("duration_sec"), "published": s.get("published"),
        "views": s.get("views"), "url": s["url"], "platform": s["platform"],
        "thumbnail": f"https://i.ytimg.com/vi/{doc['id']}/mqdefault.jpg" if s["platform"] == "youtube" else None,
        "chapters": len(doc.get("chapters") or []), "written_at": doc["written_at"],
    }


def queue_ids() -> list[str]:
    if not QUEUE.exists():
        return []
    return re.findall(r"^- \[ \] ([\w-]{11})", QUEUE.read_text(encoding="utf-8"), re.M)


SERIES = Path(__file__).parent / "series.json"


def load_series() -> list[dict]:
    return json.loads(SERIES.read_text(encoding="utf-8")) if SERIES.exists() else []


def load_paths() -> list[dict]:
    return json.loads(PATHS.read_text(encoding="utf-8")).get("tracks", []) if PATHS.exists() else []


def track_of_series(s: dict) -> str:
    return s.get("track") or "ai"


def tracks_index(paths: list[dict], series: list[dict]) -> list[dict]:
    """로드맵에 진행률을 붙인다 — 단계마다 과목의 끝낸 편수/전체."""
    by = {s["key"]: s for s in series}
    out = []
    for t in paths:
        steps = []
        for st in t["steps"]:
            ss = [{"key": k, "title": by[k]["title"], "school": by[k].get("school"), "done": by[k]["done"], "total": by[k]["total"]}
                  for k in st["series"] if k in by]
            steps.append({**st, "series": ss, "done": sum(x["done"] for x in ss), "total": sum(x["total"] for x in ss)})
        out.append({k: t[k] for k in ("key", "label", "for", "goal", "how")} |
                   {"steps": steps, "done": sum(x["done"] for x in steps), "total": sum(x["total"] for x in steps)})
    return out


def series_index(series: list[dict], have: set[str]) -> list[dict]:
    """과목마다 1강부터 N강까지 — 노트가 없는 강의도 '준비 중'으로 싣는다(무엇이 남았는지 보이게)."""
    out = []
    for s in series:
        lec = [{"no": l["no"], "id": l["id"], "title": l["title"], "duration_sec": l.get("duration"), "done": l["id"] in have}
               for l in s["lectures"]]
        out.append({"key": s["key"], "title": s["title"], "school": s.get("school"), "code": s.get("code"),
                    "term": s.get("term"), "track": track_of_series(s), "playlist": f"https://www.youtube.com/playlist?list={s['playlist']}",
                    "total": len(lec), "done": sum(l["done"] for l in lec), "lectures": lec})
    return out


def busy(vid: str) -> bool:
    """다른 회차가 지금 쓰는 강의 — fetch.py 가 재료 폴더를 만든 지 얼마 안 됐는데 노트가 아직 없다."""
    import time
    d = WORK / vid
    return d.exists() and time.time() - d.stat().st_mtime < IN_PROGRESS_SEC


def gaps(have: set[str]) -> list[str]:
    """다음 일감 — QUEUE.md 에 손으로 올린 것 먼저, 그다음 paths.json 의 로드맵 순서.

    트랙(AI·코딩테스트·백엔드·프론트·디자인·상세페이지·토익)을 한 편씩 번갈아 꺼내고, 트랙 안에서는
    앞 단계(입문)의 과목부터 1강 → N강. 한 분야만 쌓이지 않고 모든 트랙의 입문이 먼저 채워진다.
    로드맵에 없는 과목은 맨 뒤. 다른 회차가 쓰는 중(busy)인 강의는 건너뛴다.
    """
    todo = [v for v in queue_ids() if v not in have]
    series = {s["key"]: s for s in load_series()}
    lanes: list[list[str]] = []
    placed: set[str] = set()
    for t in load_paths():
        lane = []
        for st in t["steps"]:
            for k in st["series"]:
                if k in series:
                    placed.add(k)
                    lane += [l["id"] for l in series[k]["lectures"]]
        lanes.append(lane)
    rest = [l["id"] for k, s in series.items() if k not in placed for l in s["lectures"]]
    seen = set(todo)
    lanes = [[v for v in lane if v not in have] for lane in lanes]
    while any(lanes):
        for lane in lanes:
            while lane:
                v = lane.pop(0)
                if v not in seen:
                    seen.add(v)
                    todo.append(v)
                    break
    todo += [v for v in rest if v not in have and v not in seen]
    return [v for v in todo if not busy(v)]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # 윈도 cp949 콘솔에서 한글 결과 줄이 터지지 않게
    ITEMS.mkdir(parents=True, exist_ok=True)
    docs, errs = [], []
    for p in sorted(ITEMS.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errs.append(f"{p.name}: JSON 깨짐 {e}")
            continue
        errs += check(d, p.name)
        docs.append(d)
    have = {d["id"] for d in docs}
    if "--gaps" in sys.argv:
        todo = gaps(have)
        print(f"남은 강의 {len(todo)}편 — 위에서부터")
        for v in todo[:20]:
            print(" ", v)
        return
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    docs.sort(key=lambda d: (d["written_at"], d["source"].get("published") or ""), reverse=True)
    topics = {}
    for d in docs:
        topics[d["topic"]] = topics.get(d["topic"], 0) + 1
    series = series_index(load_series(), have)
    where = {l["id"]: (s["key"], l["no"], s["track"]) for s in series for l in s["lectures"]}
    items = []
    for d in docs:
        c = card(d)
        if d["id"] in where:
            c["series"], c["no"], c["track"] = where[d["id"]]
        else:
            c["track"] = TRACK_OF_TOPIC.get(d["topic"], "ai")
        items.append(c)
    index = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(docs),
        "topics": [{"key": k, "label": TOPIC_LABEL[k], "count": n} for k, n in sorted(topics.items(), key=lambda x: -x[1])],
        "tracks": tracks_index(load_paths(), series),
        "series": series,
        "items": items,
    }
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"통과 — 노트 {len(docs)}편, 과목 {len(series)}개, index.json 갱신")


if __name__ == "__main__":
    main()
