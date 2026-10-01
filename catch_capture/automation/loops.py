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
    owns: list[str] = field(default_factory=list)      # 이 레인이 고치고 커밋하는 경로(ROOT 기준) — 밖은 안 건드린다
    backlog: str | None = None   # 남은 일감을 세는 함수 이름(BACKLOG) — 대시보드에 뜬다


def _engine_prompt(dir_: str, what: str, extra: str = "") -> str:
    return (f"{what} 한 사이클: {dir_}/PROMPT.md 절차를 그대로 따른다. 상태는 {dir_}/state/ 에서 읽고, "
            f"다음 일감은 validate.py 출력(사다리 순서)이 정한다. 공식·공개 자료만 쓰고 봇 차단은 우회하지 않으며, "
            f"모르는 값은 비워 둔다. validate.py 가 통과하면 state/LOG.md·STATE.md 를 갱신하고 Conventional Commits "
            f"로 커밋한다. 푸시는 하지 않는다. 무엇을 했는지 한두 줄로 보고한다.{extra}")


def _lane(owns: list[str], request: str) -> str:
    """같은 엔진을 여러 세션이 동시에 돌리면 같은 파일을 고쳐 서로의 변경을 커밋에 섞는다(2026-09-29 하드웨어).
    그래서 레인마다 제 파일만 고치고 제 파일만 스테이징한다."""
    return (f" 이 레인이 고치는 파일은 {' · '.join(owns)} 뿐이다 — 커밋할 때도 git add 는 이 경로만 준다"
            f"(git add -A·commit -a 금지, 다른 세션의 변경이 섞인다). 형식(schema.json·validate.py·PROMPT.md·뷰어 코드)을 "
            f"바꿔야 하면 고치지 말고 {request} 에 한 줄 적고 다음 일감으로 넘어간다.")


HW_PARTS_OWNS = ["jd-viewer/public/hardware/parts.json", "jd-viewer/public/hardware/bench.json",
                 "jd-viewer/public/hardware/index.json", "jd-viewer/public/hardware/guide.json",
                 "hw-engine/state/LOG.md", "hw-engine/state/STATE.md", "hw-engine/state/QUEUE.md"]
HW_REQUESTS = "hw-engine/state/REQUESTS.md"  # 두 레인이 형식 변경 요청을 한 줄씩 덧붙인다
HW_PARTS_OWNS.append(HW_REQUESTS)
HW_MODELS_OWNS = ["jd-viewer/public/hardware/models/", "hw-engine/state/models/", HW_REQUESTS]
HW_DC_OWNS = ["jd-viewer/public/hardware/datacenter.json", "jd-viewer/public/hardware/notes.json", "hw-engine/state/datacenter/", HW_REQUESTS]

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
    Loop("ops", "운영 대시보드 8770", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.ops → servers.ops.server"),
    Loop("stats", "통계 대시보드 8765", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.stats → servers.stats.server"),
    Loop("search", "뷰어 API 8771", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.search → backend: python -m app.main"),
    Loop("collect", "방문 수집 8772", "launchd", "mac", "상주(KeepAlive)", 0, "com.jobseeker.collect → servers.collect.server"),

    # ── 크롤 한 회차 안의 단계(차례대로) ──────────────────────────────
    Loop("cycle-jobs", "채용 공고 수집·통합", "cycle", "mac", "회차마다", 3,
         "automation.crawl_all run_foreground → pipeline.aggregate", ["jd-viewer/public/all_jobs_enriched.json"]),
    Loop("cycle-blog", "기술 블로그", "cycle", "mac", "회차마다(마지막 키워드)", 6,
         "crawlers.crawl_techblog_graph", ["jd-viewer/public/tech_blogs.json"], note="--no-blog 로 끈다."),
    Loop("cycle-freelance", "외주·프리 프로젝트", "cycle", "mac", "회차마다(마지막 키워드)", 6,
         "crawlers.crawl_freelance", ["jd-viewer/public/freelance.json"], note="--no-freelance 로 끈다."),
    Loop("cycle-hardware", "PC 부품 가격", "cycle", "mac", "하루 한 번(크롤러가 날짜로 막는다)", 30,
         "crawlers.crawl_hardware", ["jd-viewer/public/hardware/prices.json"],
         check="python -m crawlers.crawl_hardware --selftest", note="다나와 통합검색, Crawl-delay 10초. --no-hardware 로 끈다."),
    Loop("cycle-prebuilt", "완제품 조립PC", "cycle", "mac", "하루 한 번(부품 가격 다음)", 30,
         "crawlers.crawl_prebuilt", ["jd-viewer/public/hardware/prebuilt.json"],
         check="python -m crawlers.crawl_prebuilt --selftest",
         note="구성은 회차당 상품 페이지 80개까지. 네이버는 NAVER_CLIENT_ID/SECRET 이 있을 때만."),
    Loop("cycle-closecheck", "마감 재확인(회차 안)", "cycle", "mac", "회차마다 400건", 3,
         "auto_crawl.refresh_closures → pipeline.close_check", ["catch_capture/job_closures.json"],
         note="launchd closecheck 와 원장 잠금을 나눠 쓴다."),
    Loop("cycle-data", "뷰어 데이터 굽기", "cycle", "mac", "회차마다", 3,
         "jd-viewer/bin/refresh-data.sh → store.jobs.export → build_*",
         ["jd-viewer/public/all_jobs_enriched.json", "jd-viewer/public/company_stacks.json",
          "jd-viewer/public/trends.json", "jd-viewer/public/job_calendar.json"]),
    Loop("cycle-vectors", "임베딩·유사 공고", "cycle", "mac", "회차 끝", 6,
         "auto_crawl.refresh_vectors → store.vectors.embed → store.vectors.similar --dump",
         ["jd-viewer/public/similar_jobs.json"], note="Ollama 가 꺼져 있으면 임베딩만 건너뛴다."),
    Loop("cycle-docs", "문서 → DB(/api/docs)", "cycle", "mac", "회차 끝 + git 동기화 때", 6,
         "auto_crawl.refresh_docs → store.ingest.docs", [],
         note="역설계·브리핑·도서·하드웨어·빌더 산출물. 바뀐 것만 쓴다."),
    Loop("cycle-extras", "부가 빌더", "cycle", "mac", "회차마다(크롤 성패와 무관)", 6,
         "auto_crawl.enrich_extras → learning·radar·reposts·career_map·blog_guides·inflearn·engagement",
         ["jd-viewer/public/reposts.json", "jd-viewer/public/engagement.json"]),

    # ── Claude Code /loop 로 도는 조사 엔진 ───────────────────────────
    Loop("reveng-engine", "기업 기술 역설계", "claude-loop", "any", "2시간마다(짝수 시 :17, 세션 cron)", 72,
         "/loop <prompt>", ["engine/state/LOG.md", "jd-viewer/public/reveng/index.json"],
         check="python engine/validate.py --gaps", prompt=_engine_prompt("engine", "기업 기술 역설계 엔진")),
    Loop("guide-engine", "취업 브리핑", "claude-loop", "any", "2시간마다(홀수 시 :47, 세션 cron)", 72,
         "/loop <prompt>", ["guide-engine/state", "jd-viewer/public/guide"],
         check="python guide-engine/validate.py --gaps", prompt=_engine_prompt("guide-engine", "취업 브리핑 엔진")),
    Loop("study-engine", "기술 백과사전", "claude-loop", "any", "자율(화면에서는 빠져 있다)", 24 * 30,
         "/loop <prompt>", ["study-engine/state", "jd-viewer/public/study"],
         check="python study-engine/validate.py", prompt=_engine_prompt("study-engine", "기술 백과사전 엔진"),
         note="2026-09-08 부터 뷰어 화면에서 빠졌다 — 데이터·엔진만 산다."),
    # 하드웨어는 레인 둘 + 형식. 부품·벤치(hw-engine)와 제품 스펙(hw-models)은 따로 돌고 서로의 파일을
    # 안 건드린다. 형식(schema·validate·PROMPT·뷰어 코드)은 루프가 아니라 사람이 지시한 세션이 바꾸고,
    # 루프는 필요한 변경을 REQUESTS.md 에 적기만 한다. 가격·완제품은 크롤 단계(cycle-hardware·prebuilt)가 받는다.
    Loop("hw-engine", "PC 하드웨어 — 부품·벤치", "claude-loop", "any", "자율(약 20분 간격)", 24,
         "/loop <prompt>", ["hw-engine/state/LOG.md", "jd-viewer/public/hardware/parts.json"],
         check="python -X utf8 hw-engine/validate.py --gaps", owns=HW_PARTS_OWNS,
         prompt=_engine_prompt(
             "hw-engine", "하드웨어 엔진(부품·벤치 레인)",
             " 일감은 --gaps 의 1~5·7·8번이다(6·9번 제품 스펙은 hw-models 레인 몫). 오늘 가격·완제품을 아직 안 받았으면 "
             "catch_capture 에서 python -m crawlers.crawl_hardware 와 python -m crawlers.crawl_prebuilt 를 먼저 돌린다"
             "(하루 한 번 규칙은 크롤러가 지킨다). 다나와 스펙 문구·리뷰 글은 쓰지 않는다."
             + _lane(HW_PARTS_OWNS, HW_REQUESTS))),
    Loop("hw-models", "PC 하드웨어 — 제품 스펙", "claude-loop", "any", "자율(약 20분 간격)", 48,
         "/loop <prompt>", ["jd-viewer/public/hardware/models"],
         check="python -X utf8 hw-engine/validate.py --gaps", owns=HW_MODELS_OWNS, backlog="hw_models",
         prompt=(
             "하드웨어 제품 스펙 레인 한 사이클: hw-engine/PROMPT.md 의 규칙 6·7 과 '케이스 제품' 형식을 따른다. "
             "상태는 hw-engine/state/models/STATE.md 에서 읽는다. 일감은 validate.py --gaps 의 6번(스펙 조사 전 매물)과 "
             "9번(메모리 슬롯 모르는 보드 제품)이다 — 매물이 많이 남은 부품부터, 그 부품의 다나와 인기순(prices.json 의 rank) "
             "위 제품부터 models/<부품 id>.json 에 한 사이클 5~8개를 더한다. 순서는 그래픽카드 → 케이스 → 메인보드 → 파워 → 쿨러. "
             "스펙은 제조사 공식 페이지만(봇 차단은 우회하지 않고 국내 공식 유통사 → medium), 모르는 값은 null, "
             "상품명의 말('세븐팬' 등)로 스펙을 짐작하지 않는다. 한 매물이 두 제품에 걸리면 안 된다. "
             "validate.py 가 통과하면 hw-engine/state/models/LOG.md 에 한 단락, STATE.md 를 갱신하고 "
             "docs(hardware) 로 커밋한다. 푸시는 하지 않는다. 무엇을 했는지 한두 줄로 보고한다."
             + _lane(HW_MODELS_OWNS, HW_REQUESTS))),
    # AI 데이터센터 — 회사별 칩 수·금액·시장 조사. 매출·설비투자는 분기마다 바뀌어 90일이면 다시 본다.
    Loop("hw-datacenter", "AI 데이터센터·실무자 이야기", "claude-loop", "any", "분기 실적 뒤(주 1회면 충분)", 24 * 90,
         "/loop <prompt>", ["jd-viewer/public/hardware/datacenter.json", "jd-viewer/public/hardware/notes.json"],
         check="python -X utf8 hw-engine/validate.py --gaps", owns=HW_DC_OWNS, backlog="hw_datacenter",
         prompt=(
             "AI 데이터센터 레인 한 사이클: hw-engine/PROMPT.md 의 'AI 데이터센터 레인' 규칙 1~6 을 따른다. "
             "상태는 hw-engine/state/datacenter/STATE.md 에서 읽는다. 일감은 validate.py --gaps 의 10번이다 — "
             "확인 90일 넘은 섹션 → 1년 넘은 가동 데이터센터 → H100 환산이 빠진 회사 순으로 한 사이클 3~5개를 새 공시·보도로 바꾼다. 10번이 비면 11번(실무자 이야기 notes.json — 이야기가 없는 고성능 카드, 반년 넘은 이야기)을 한다: GitHub 토론·Puget·Hugging Face·제조사 문서처럼 읽고 링크할 수 있는 곳만, Reddit 은 robots.txt 가 막아 쓰지 않는다, 원문은 옮기지 말고 요약하며 핵심 숫자는 원문과 대조한다. "
             "숫자마다 출처 URL 과 공식·추정·계획 구분, 원문을 못 연 숫자는 넣지 않는다, 겹치는 행은 in_total:false, "
             "공식 사양이 없는 칩은 ratios 에 넣지 않는다. 고친 섹션의 checked 날짜를 오늘로. validate.py 가 통과하면 "
             "state/datacenter/LOG.md 에 한 단락, STATE.md 를 갱신하고 docs(hardware) 로 커밋한다. 푸시는 하지 않는다. "
             "무엇을 했는지 한두 줄로 보고한다."
             + _lane(HW_DC_OWNS, HW_REQUESTS))),
    # 인스타 키우기 — 알고리즘·경쟁 계정을 주마다 다시 보고 design-lab/GROWTH.md 를 고친다. 발행은 하지 않는다.
    Loop("insta-growth", "인스타 키우기 조사", "claude-loop", "any", "주 1회", 24 * 8,
         "/loop <prompt>", ["design-lab/GROWTH.md", "design-lab/planning/01-research/README.md"],
         owns=["design-lab/GROWTH.md", "design-lab/planning/01-research/"],
         prompt=(
             "인스타 키우기 조사 한 사이클: design-lab/GROWTH.md 를 읽고, 지난 조사 뒤에 나온 인스타그램 공식 발표"
             "(about.instagram.com·creators.instagram.com·Adam Mosseri)와 데이터 리포트(Buffer·Later·Hootsuite·Sprout)를 "
             "웹에서 찾는다. 경쟁 계정(@catch.job·@wantedjobs.kr·@codeit_kr 등) 프로필에서 새 시리즈·하이라이트·형식을 본다. "
             "모든 주장에 출처 URL, 추측 금지. 규칙이 바뀌었으면 본문을 고치고 '바뀐 것' 맨 위에 날짜와 한 단락을 더한다. "
             "다음 주에 만들 콘텐츠 후보 3개(데이터 출처와 사진 사용권까지)를 같은 단락에 적는다. "
             "그리고 실제로 터진 릴스를 한 회차 조사한다: design-lab/planning/01-research/method.md 대로 키워드 검색으로 "
             "릴스의 조회·길이·음원·캡션을 모아 data/ 에 CSV 로 남기고, README 의 '조사 회차' 에 한 회차를 더한 뒤 "
             "규칙 표(R…)·가설(H…)을 근거와 함께 고친다(규칙을 바꾸면 근거 회차를 적는다). 게시·댓글·팔로우 같은 "
             "계정 행동은 하지 않는다. docs(design-lab) 로 커밋하고 푸시는 하지 않는다. 무엇을 했는지 한두 줄로 보고한다."
             " 이 레인이 고치는 파일은 design-lab/GROWTH.md 와 design-lab/planning/01-research/ 뿐이다 — git add 도 이 경로만 준다.")),
    # 경쟁 계정·마케팅 전략 학습 — 채용·취업·직장인 큰 계정을 회차마다 2~3곳씩 보고, 전략을 점수로 견준다.
    Loop("insta-benchmark", "인스타 계정·전략 학습", "claude-loop", "any", "하루 1~2회(세션이 열려 있을 때)", 48,
         "/loop <prompt>", ["design-lab/planning/01-research/accounts.md", "design-lab/planning/01-research/strategies.md"],
         owns=["design-lab/planning/01-research/accounts.md", "design-lab/planning/01-research/strategies.md"],
         prompt=(
             "인스타 계정·전략 학습 한 회차: design-lab/planning/01-research/accounts.md 와 strategies.md 를 읽는다. "
             "① 계정: 채용·취업·직장인·개발자 쪽에서 팔로워가 많은 계정 2~3곳을 고른다(비교표에 없는 곳 먼저, 있던 곳은 30일 넘게 안 본 곳). "
             "로그인한 인스타 웹 탭에서 프로필(팔로워·게시물 수)과 최근 릴스·게시물의 조회·길이·형식·올리는 속도·시리즈 이름을 본다"
             "(검색 API 는 planning/01-research/method.md 대로; 429 가 나면 그 회차는 웹 검색 자료로 대신한다). "
             "비교표에 같은 칸으로 한 줄씩 채우고(본 날짜), '회차 기록' 에 한 단락을 더한다. "
             "② 전략: 웹에서 채용·교육·커리어 브랜드의 인스타 마케팅 사례와 인스타 공식 크리에이터 자료를 찾아, 새 전략이면 S 번호로 카드를 더하고 "
             "있던 전략이면 근거를 덧붙여 효과·맞음·비용 점수를 고친다 — 점수를 바꾸면 '바뀐 것' 에 날짜와 이유. "
             "모든 주장에 출처(계정 주소·URL·숫자), 추측은 '?' 로 표시. 글·그림·영상은 옮기지 않고 형식만 적는다. "
             "합계 상위 전략이 03-content.md 일감과 어긋나면 strategies.md '바뀐 것' 에 '03 반영 필요' 라고만 적는다(03 은 고치지 않는다). "
             "팔로우·좋아요·댓글·게시 같은 계정 행동은 하지 않는다. docs(design-lab) 로 커밋하고 푸시는 하지 않는다. "
             "무엇을 배웠는지 한두 줄로 보고한다. 이 레인이 고치는 파일은 위 두 파일뿐이다 — git add 도 이 경로만 준다.")),
    # 인스타 콘텐츠 개발 — planning/03 일감을 위에서부터 하나씩 규격(02)대로 만들고 점검(04)한다. 게시는 사람이 한다.
    Loop("insta-content", "인스타 콘텐츠 개발", "claude-loop", "any", "45분마다(세션이 열려 있을 때)", 24,
         "/loop 45m <prompt>", ["design-lab/planning/03-content.md"],
         owns=["design-lab/poster/", "design-lab/planning/03-content.md", "design-lab/planning/06-review.md",
               "design-lab/assets/", "design-lab/content/"],
         prompt=(
             "인스타 콘텐츠 개발 한 회차: design-lab/planning/README.md · 02-format.md · 03-content.md · 04-production.md 와 "
             "01-research/strategies.md(상위 전략과 '03 반영 필요' 줄)를 읽는다. strategies.md 에 '03 반영 필요' 가 있으면 먼저 03 의 "
             "기준·일감을 고친다(01-research 파일은 고치지 않는다 — 반영했다는 기록은 03 에 날짜로). 03 일감 표에서 '할 일' 중 맨 위 하나를 "
             "골라 02 규격(길이·첫 프레임·안전 여백·디자인)대로 만든다 — design-lab/poster/ 의 판·빌더를 쓰고, 없는 판 종류(예: 티어표)는 더한다. "
             "숫자는 만들 때 우리 데이터에서 다시 세고, 정규식으로 센 숫자는 원문 5건을 확인하며, 04 점검표를 모두 통과시킨다. "
             "결과는 out/series/<id>/ 에 영상·caption.txt 로 두고 찍은 장면을 직접 열어 본다. 03 일감 상태를 '제작(날짜·경로)' 로, "
             "06 성적표에 올리기 전 줄(길이·형식)을 더한다. '할 일' 이 2개 이하로 줄면 01-research 규칙과 우리 데이터로 새 일감 3개를 "
             "출처와 함께 더한다. 인스타 게시·팔로우·댓글 같은 계정 행동은 하지 않는다 — 다 만든 것은 보고에 '올릴 준비' 로 적는다. "
             "design-lab 테스트(python -m pytest tests)를 통과시키고 feat/docs(design-lab) 로 커밋, 푸시는 하지 않는다. "
             "무엇을 만들었는지 한두 줄로 보고한다. 고치는 곳은 design-lab/poster/ · assets/ · content/ · planning/03-content.md · "
             "planning/06-review.md 뿐이다 — git add 도 이 경로만 준다.")),
    # 터진 릴스 공부 — 회차마다 처음 보는 100만+ 릴스를 영상 장면·댓글까지 보고 기록, '이럴 땐 이렇게' 를 고친다.
    Loop("insta-reels", "터진 릴스 공부", "claude-loop", "any", "30분마다(세션이 열려 있을 때)", 24,
         "/loop 30m <prompt>", ["design-lab/planning/01-research/reels-study.md", "design-lab/planning/01-research/playbook.md"],
         owns=["design-lab/planning/01-research/reels-study.md", "design-lab/planning/01-research/playbook.md",
               "design-lab/planning/01-research/data/reels-study.jsonl"],
         prompt=(
             "터진 릴스 공부 한 회차: design-lab/planning/01-research/reels-study.md · playbook.md · method.md('영상·댓글 받기')를 읽는다. "
             "reels-study.md·teardown.md 에 없는 100만+ 릴스 4~6편을 고른다 — data/reels-1m-2026-10-02-links.csv 의 남은 것과 새 키워드 검색에서, "
             "갈래가 겹치지 않게(돈 표·콩트·브이로그·인터뷰·실촬영·공식 계정·개발자). method.md 절차대로 수신기(research.reelstudy serve)를 띄우고, "
             "인스타 탭에서 숫자·캡션·음원·댓글 40여 개를 모아 수신기로 넘긴 뒤 frames --clean 으로 장면표를 만든다(영상은 지운다). "
             "편마다 장면표를 직접 열어 보고 댓글을 좋아요 순으로 읽어, reels-study.md 에 회차를 더한다: 링크·숫자(좋아요율)·길이·소리·"
             "장면 순서(0~1.5초 훅/첫 변화/가운데/끝)·공감 장면·댓글은 왜 쓰나(분류 C…, 새 이유면 기호를 더한다)·우리에게 주는 것. "
             "data/reels-study.jsonl 에 편마다 한 줄. 두 편 이상 같은 결과면 playbook.md 의 줄을 더하거나 '?' 를 떼고, 반대 사례면 고친다(근거 편을 단다). "
             "댓글 원문은 짧게 요약하고 길게 옮기지 않는다. 팔로우·좋아요·댓글 같은 계정 행동은 하지 않는다. 끝나면 탭을 인스타 프로필로 되돌리고 수신기를 끈다. "
             "docs(design-lab) 로 커밋, 푸시는 하지 않는다. 무엇을 배웠는지 한두 줄로 보고한다. "
             "고치는 파일은 reels-study.md · playbook.md · data/reels-study.jsonl 뿐이다 — git add 도 이 경로만 준다.")),
]

BY_KEY = {l.key: l for l in REGISTRY}


# ── 남은 일감 ────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _hit(name: str, rule: dict) -> bool:
    """hw-engine/validate.py·뷰어 offerMatches 와 같은 규칙 — 'A|B' 는 둘 중 하나"""
    has = lambda t: any(_norm(x) in name for x in t.split("|"))
    return all(has(t) for t in rule.get("must", [])) and not any(has(t) for t in rule.get("not", []))


def _hw_models_backlog() -> str | None:
    """분류별 '스펙 조사 전 매물' 수 — 그날 다나와 매물 중 어느 제품(models/)에도 안 걸린 것"""
    hw = PUBLIC / "hardware"
    try:
        parts = json.loads((hw / "parts.json").read_text(encoding="utf-8")).get("parts", [])
        book = json.loads((hw / "prices.json").read_text(encoding="utf-8")).get("parts", {})
    except (OSError, ValueError):
        return None
    left: dict[str, int] = {}
    for p in parts:
        if p.get("category") == "cpu":  # CPU 는 제품이 없다 — 판매 형태로 갈린다
            continue
        offers = (book.get(p["id"]) or {}).get("offers") or []
        try:
            models = json.loads((hw / "models" / f"{p['id']}.json").read_text(encoding="utf-8")).get("models", [])
        except (OSError, ValueError):
            models = []
        n = sum(1 for o in offers if not any(_hit(_norm(o["name"]), m.get("match") or {}) for m in models))
        if n:
            left[p["category"]] = left.get(p["category"], 0) + n
    if not left:
        return "스펙 조사 전 매물 없음"
    return "스펙 조사 전 매물 " + " · ".join(f"{c} {n}" for c, n in sorted(left.items(), key=lambda kv: -kv[1]))


def _hw_datacenter_backlog() -> str | None:
    """AI 데이터센터 — 확인 90일 넘은 섹션 수 · 1년 넘은 가동 데이터센터 수 (validate.py --gaps 10번과 같은 기준)"""
    try:
        d = json.loads((PUBLIC / "hardware" / "datacenter.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    now = datetime.now()

    def days(s: str | None) -> int | None:
        if not s:
            return None
        s = s if len(s) >= 10 else (s + "-01" if len(s) == 7 else s + "-01-01")
        try:
            return (now - datetime.strptime(s[:10], "%Y-%m-%d")).days
        except ValueError:
            return None

    checked = d.get("checked") or {}
    old_sec = sum(1 for k in ("clusters", "ratios", "money", "market", "fx") if (a := days(checked.get(k))) is None or a > 90)
    old_dc = sum(1 for c in d.get("clusters", []) if c.get("status") == "operational" and c.get("in_total", True) and (days(c.get("as_of")) or 0) > 365)
    return f"섹션 {old_sec} · 데이터센터 {old_dc}"


BACKLOG = {"hw_models": _hw_models_backlog, "hw_datacenter": _hw_datacenter_backlog}


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
    try:
        backlog = BACKLOG[l.backlog]() if l.backlog else None
    except Exception:
        backlog = None
    return {**asdict(l), "backlog": backlog, "last": last.isoformat(timespec="minutes") if last else None,
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
