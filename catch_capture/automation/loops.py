"""반복 작업 등록부 — 이 저장소에서 '계속 도는 것' 전부를 한 곳에.

돌아가는 것이 세 군데에 흩어져 있었다:
  launchd       맥이 주기로 부르는 작업·상주 서버(deploy/setup-*.sh 가 깐다)
  cycle         크롤 한 회차 안에서 차례로 도는 단계(automation/crawl_all.run_foreground)
  claude-loop   Claude Code 의 `/loop` 로 도는 조사 엔진(engine/·guide-engine/·hw-engine/ …)

claude-loop 은 **실행 프롬프트가 어디에도 적혀 있지 않아서** 세션이 닫히면 무엇을 어떻게
돌렸는지가 사라졌다. 그래서 여기 적는다 — 다시 시작할 때는 `prompt` 를 그대로 `/loop` 에 준다.
주기·입력·산출물·검증 명령도 같이 적어, 무엇이 멈췄는지를 산출물의 나이로 판단한다.

    python -m automation.loops list               # 전체 표
    python -m automation.loops show hw-engine      # 한 줄 자세히
    python -m automation.loops prompt hw-engine    # /loop 에 붙일 프롬프트만
    python -m automation.loops status --json       # 상태(ops_server /api/loops 가 같은 것을 낸다)

새 반복 작업을 만들면 **먼저 여기 한 줄을 더한다.** 등록부에 없는 루프는 없는 것으로 본다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

CATCH = Path(__file__).resolve().parent.parent
ROOT = CATCH.parent
PUBLIC = ROOT / "jd-viewer" / "public"


@dataclass
class Loop:
    key: str
    name: str
    kind: str                    # launchd | cycle | claude-loop
    where: str                   # mac | any
    cadence: str                 # 사람이 읽는 주기
    stale_hours: float           # 산출물이 이보다 오래되면 '멈춤' 으로 본다
    run: str                     # 실행 명령 또는 launchd 라벨
    outputs: list[str] = field(default_factory=list)   # ROOT 기준 경로 — 나이로 생존을 본다
    check: str | None = None     # 검증 명령(있으면)
    prompt: str | None = None    # claude-loop 의 /loop 프롬프트
    note: str = ""


def _engine_prompt(dir_: str, what: str, extra: str = "") -> str:
    return (f"{what} 한 사이클: {dir_}/PROMPT.md 절차를 그대로 따른다. 상태는 {dir_}/state/ 에서 읽고, "
            f"다음 일감은 validate.py 출력(사다리 순서)이 정한다. 공식·공개 자료만 쓰고 봇 차단은 우회하지 않으며, "
            f"모르는 값은 비워 둔다. validate.py 가 통과하면 state/LOG.md·STATE.md 를 갱신하고 Conventional Commits "
            f"로 커밋한다. 푸시는 하지 않는다. 무엇을 했는지 한두 줄로 보고한다.{extra}")


REGISTRY: list[Loop] = [
    # ── launchd (맥) ──────────────────────────────────────────────────
    Loop("crawler", "채용 크롤 사이클", "launchd", "mac", "1시간마다(CRAWL_INTERVAL)", 3,
         "com.jobseeker.crawler → python -m automation.auto_crawl once",
         ["jd-viewer/public/all_jobs_enriched.json"],
         note="한 회차 = 아래 cycle 단계 전부. deploy/setup-crawler.sh 가 깐다."),
    Loop("closecheck", "마감 재확인", "launchd", "mac", "10분마다 100건", 1,
         "com.jobseeker.closecheck → python -m pipeline.close_check --limit 100",
         ["catch_capture/job_closures.json"], note="원장 잠금(job_closures.lock)을 못 잡으면 그 회차를 건너뛴다."),
    Loop("publisher", "소셜 자동 발행", "launchd", "mac", "5분마다 tick(12:30·19:30 슬롯)", 24,
         "com.jobseeker.publisher → python -m publish.daemon tick", [],
         note="design-lab/SOCIAL.md. autopublish.live 가 꺼져 있으면 연습 발행만."),
    Loop("ops", "운영 대시보드 8770", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.ops → monitoring.ops_server"),
    Loop("stats", "통계 대시보드 8765", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.stats → dashboard/serve.py"),
    Loop("search", "검색 API 8771", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.search → semantic.server"),
    Loop("collect", "방문 수집 8772", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.collect → engagement.collect"),

    # ── 크롤 한 회차 안의 단계(차례대로) ──────────────────────────────
    Loop("cycle-jobs", "채용 공고 수집·통합", "cycle", "mac", "회차마다", 3,
         "automation.crawl_all run_foreground → pipeline.aggregate", ["jd-viewer/public/all_jobs_enriched.json"]),
    Loop("cycle-blog", "기술 블로그", "cycle", "mac", "회차마다(마지막 키워드)", 6,
         "crawlers.crawl_techblog", ["jd-viewer/public/tech_blogs.json"], note="--no-blog 로 끈다."),
    Loop("cycle-freelance", "외주·프리 프로젝트", "cycle", "mac", "회차마다(마지막 키워드)", 6,
         "crawlers.crawl_freelance", ["jd-viewer/public/freelance.json"], note="--no-freelance 로 끈다."),
    Loop("cycle-hardware", "PC 부품 가격", "cycle", "mac", "하루 한 번(크롤러가 날짜로 막는다)", 30,
         "crawlers.crawl_hardware", ["jd-viewer/public/hardware/prices.json"],
         check="python -m crawlers.crawl_hardware --selftest", note="다나와 통합검색, Crawl-delay 10초. --no-hardware 로 끈다."),
    Loop("cycle-prebuilt", "완제품 조립PC", "cycle", "mac", "하루 한 번(부품 가격 다음)", 30,
         "crawlers.crawl_prebuilt", ["jd-viewer/public/hardware/prebuilt.json"],
         check="python -m crawlers.crawl_prebuilt --selftest",
         note="구성은 회차당 상품 페이지 80개까지. 네이버는 NAVER_CLIENT_ID/SECRET 이 있을 때만."),
    Loop("cycle-semantic", "임베딩·유사 공고", "cycle", "mac", "회차 끝", 6,
         "semantic.ingest → embed → similar", [], note="Ollama 가 꺼져 있으면 조용히 건너뛴다."),

    # ── Claude Code /loop 로 도는 조사 엔진 ───────────────────────────
    Loop("reveng-engine", "기업 기술 역설계", "claude-loop", "any", "자율(사이클 끝에 다음 시각을 스스로 잡는다)", 72,
         "/loop <prompt>", ["engine/state/LOG.md", "jd-viewer/public/reveng/index.json"],
         check="python engine/validate.py --gaps", prompt=_engine_prompt("engine", "기업 기술 역설계 엔진")),
    Loop("guide-engine", "취업 브리핑", "claude-loop", "any", "자율", 72,
         "/loop <prompt>", ["guide-engine/state", "jd-viewer/public/guide"],
         check="python guide-engine/validate.py --gaps", prompt=_engine_prompt("guide-engine", "취업 브리핑 엔진")),
    Loop("study-engine", "기술 백과사전", "claude-loop", "any", "자율(화면에서는 빠져 있다)", 24 * 30,
         "/loop <prompt>", ["study-engine/state", "jd-viewer/public/study"],
         check="python study-engine/validate.py", prompt=_engine_prompt("study-engine", "기술 백과사전 엔진"),
         note="2026-09-08 부터 뷰어 화면에서 빠졌다 — 데이터·엔진만 산다."),
    Loop("hw-engine", "PC 하드웨어 조사", "claude-loop", "any", "자율(약 20분 간격)", 24,
         "/loop <prompt>", ["hw-engine/state/LOG.md", "jd-viewer/public/hardware/parts.json"],
         check="python -X utf8 hw-engine/validate.py --gaps",
         prompt=_engine_prompt(
             "hw-engine", "하드웨어 엔진",
             " 오늘 가격·완제품을 아직 안 받았으면 catch_capture 에서 python -m crawlers.crawl_hardware 와 "
             "python -m crawlers.crawl_prebuilt 를 먼저 돌린다(하루 한 번 규칙은 크롤러가 지킨다). 다나와 스펙 문구·"
             "리뷰 글은 쓰지 않는다. 두 크롤러의 --selftest 와 뷰어 tsc 도 통과해야 커밋한다.")),
]

BY_KEY = {l.key: l for l in REGISTRY}


# ── 상태 ─────────────────────────────────────────────────────────────

def _mtime(rel: str) -> datetime | None:
    p = ROOT / rel
    if not p.exists():
        return None
    if p.is_dir():
        ts = [f.stat().st_mtime for f in p.rglob("*") if f.is_file()]
        return datetime.fromtimestamp(max(ts)) if ts else None
    return datetime.fromtimestamp(p.stat().st_mtime)


def _last_commit(paths: list[str]) -> str | None:
    """git 이 기억하는 마지막 갱신 — 파일 시각은 체크아웃만 해도 바뀌어서 claude-loop 은 이걸 본다."""
    if not paths or not shutil.which("git"):
        return None
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cI", "--", *paths],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out or None
    except Exception:
        return None


def _launchd_alive(label: str) -> bool | None:
    if not shutil.which("launchctl"):
        return None  # 맥이 아니다 — 모른다
    try:
        r = subprocess.run(["launchctl", "list", label], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return None


def status(l: Loop) -> dict:
    last = None
    if l.kind == "claude-loop":
        c = _last_commit(l.outputs)
        last = datetime.fromisoformat(c).replace(tzinfo=None) if c else None
    else:
        ts = [t for t in (_mtime(o) for o in l.outputs) if t]
        last = max(ts) if ts else None
    age_h = (datetime.now() - last).total_seconds() / 3600 if last else None
    alive = _launchd_alive(l.run.split(" ")[0]) if l.kind == "launchd" else None
    if l.kind == "launchd" and alive is False:
        state = "stopped"
    elif l.stale_hours and age_h is not None and age_h > l.stale_hours:
        state = "stale"
    elif age_h is None and l.outputs:
        state = "unknown"
    else:
        state = "ok"
    return {**asdict(l), "last": last.isoformat(timespec="minutes") if last else None,
            "age_hours": round(age_h, 1) if age_h is not None else None, "launchd_alive": alive, "state": state}


def status_all() -> list[dict]:
    return [status(l) for l in REGISTRY]


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        rows = status_all()
        for r in rows:
            age = f"{r['age_hours']}h" if r["age_hours"] is not None else "-"
            print(f"{r['state']:<8} {r['kind']:<12} {r['key']:<16} {r['cadence']:<34} 마지막 {r['last'] or '-':<17} ({age})  {r['name']}")
        return 0
    if cmd in ("show", "prompt"):
        if len(argv) < 2 or argv[1] not in BY_KEY:
            print(f"키: {', '.join(BY_KEY)}")
            return 2
        l = BY_KEY[argv[1]]
        if cmd == "prompt":
            if not l.prompt:
                print(f"{l.key} 는 /loop 로 돌지 않는다({l.kind}) — {l.run}")
                return 1
            print(l.prompt)
            return 0
        print(json.dumps(status(l), ensure_ascii=False, indent=2))
        return 0
    if cmd == "status":
        print(json.dumps(status_all(), ensure_ascii=False, indent=None if "--json" in argv else 2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
