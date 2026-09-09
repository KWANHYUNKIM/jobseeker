# 프로젝트 가이드

채용 사이트(wanted/jumpit/jobkorea/saramin/devocean) 크롤링 → 통합/분류 → 대시보드/뷰어 시각화 시스템.

- `catch_capture/` : 채용 크롤 파이프라인 (기능별 패키지)
  - `crawlers/` : 사이트별 크롤러(crawl_*.py) + 공통(jobs_common)
  - `pipeline/` : 통합/중복제거/마감분류(aggregate, job_status), 수동보정(overrides)
    마감 판정은 두 겹이다 — 공고가 들고 온 텍스트(`job_status`)와, 원본 사이트에
    다시 물어보는 재확인(`close_check` → `job_closures.json` 원장). 원장이 우선한다.
    크롤은 "지금 올라온 공고"만 알려주므로 재확인이 없으면 마감이 영영 안 닫힌다
    (특히 마감일 표기가 아예 없는 wanted). auto_crawl 이 사이클마다 400건씩 돌린다.
  - `monitoring/` : 헬스 기록·이상탐지(health)
  - `automation/` : 크롤 오케스트레이션(crawl_all) + 자동화 데몬(auto_crawl)
  - `dashboard/` : 통계 대시보드(serve.py, 8765)
  - `semantic/` : 임베딩 기반 추천·검색 (SQLite+sqlite-vec 저장, Ollama bge-m3 증분 임베딩,
    코사인 top-K → `public/similar_*.json`). 크롤 사이클 끝에 auto_crawl 이 자동 실행.
    `search.py`(FTS5+벡터 RRF 하이브리드) / `server.py`(검색 API, 8771)
    마감 공고는 색인에 남기되(지난 공고 통계·유사도의 재료) `meta.status` 로 표시해
    검색·추천에서 뺀다. 검색은 `--include-closed` 로 열 수 있다.
  - `store/` : 정본 DB(PostgreSQL) 접근 계층 — **이관 중이다.** 지금까지 원본은
    `all_jobs_enriched.json` 한 덩어리였고 키도 제약도 없어서 회사 표기가 갈리고
    (`(주)클로봇` ≠ `클로봇`) `status` 가 계산 시점에 박제됐다. 스키마와 설계 근거는
    `db/schema.sql` · `db/README.md`. `conn`(DSN) / `slug`(주소 슬러그 — 규칙 원본은
    `jd-viewer/src/lib/companySlug.js` 이고 여기서 읽어 쓴다) / `upsert`(쓰기 경로 —
    백필과 크롤이 같은 함수를 쓴다) / `backfill`(JSON→DB — 이관·복구용 일회성. 사이클에서는 뺐다) /
    `ingest_crawl`(크롤 사이클→DB, aggregate 가 매번 부른다 — 회사 표기 재선정과
    `mv_company_stack` 갱신도 여기서 한다) / `export`(DB→뷰어 JSON) /
    `embed`·`similar`·`search`(pgvector 판 semantic) / `migrate_vectors`(sqlite-vec→pgvector) /
    `ledgers`(파일로 쌓이던 원장 — `trends_history.jsonl`→`trend_day`/`trend_metric`,
    `job_history.jsonl`→`job_version`, `engagement/events.jsonl`→`engagement_event`.
    지난 일은 다시 계산할 수 없는데 머신마다 따로 놀거나(트렌드가 로컬 54일/운영 23일)
    조용히 회전돼 버려지고 있었다. `build_trends`·`build_reposts`·`engagement.score`
    가 여기서 읽고, 씨앗 뿌리기는 `python -m store.ledgers seed`).
    **status 는 컬럼이 아니라 `job_state` 뷰다** — 저장하지 않으면 낡을 수 없다.
    이중 쓰기는 실패해도 사이클을 죽이지 않는다(`DB_DUAL_WRITE=0` 으로 끈다).
    목록에서 사라진 공고는 지우지 않고 `gone_at` 만 찍되, 그 사이트의 수집량이
    절반 아래로 떨어지면(`DB_GONE_MIN_RATIO`) 그 처리를 통째로 보류한다 —
    크롤이 차단당한 것과 공고가 내려간 것은 다르다.
  - `paths.py` : 공통 경로(데이터/venv 위치) 단일 소스
- `jd-viewer/` : React/Vite 기반 JD 뷰어 (5173, public 데이터 소비).
  화면마다 진짜 경로를 쓴다(`/jobs/<사이트>-<번호>`, `/companies/<회사>` 등) —
  `src/lib/router.ts`(pushState) + `src/lib/seo.ts`(라우트별 head) +
  `scripts/prerender.mjs`(빌드 때 주소별 정적 HTML·sitemap·robots). 자세한 건 뷰어 README.
- `engine/` : 기업 기술 역설계 엔진 (크롤이 아니라 공개 자료 재구성).
  `PROMPT.md`(사이클 절차) / `schema.json`(형식) / `state/`(대기열·진행) /
  `validate.py`(커밋 전 검증). 산출물은 `jd-viewer/public/reveng/` 에 쌓이고
  뷰어의 `기술 역설계` 탭이 읽는다. 한 회사를 완주할 때까지 다음 회사로 안 넘어간다.
- `guide-engine/` : 취업 브리핑 엔진. 역설계가 "이 회사가 어떻게 만들어졌나"라면
  여기는 "내가 저기 들어가려면 뭘 하나"다. 공고의 자격요건·우대사항 문장에서 학습
  항목을 뽑고 회사의 연봉 밴드·공개 인물·사업 도메인을 조사한다. 구조는 `engine/` 과
  같고(PROMPT/schema/state/validate) 큐·상태·산출물은 완전히 따로다. 산출물은
  `jd-viewer/public/guide/` 에 쌓여 공고 상세 화면 오른쪽 패널이 읽는다.
  대기열은 `all_jobs_enriched.json` 에서 나온다 — `validate.py --gaps` 가 브리핑 없는
  회사를 모집중 공고 수로 줄 세워 준다.
- `study-engine/` : 기술 백과사전 엔진. 단위는 **낱말 하나**다 — ATmega128 핀맵·풀업
  저항부터 파이썬 자료구조 선택, 멱등성 같은 IT 용어까지. 구조는 `engine/` 과 같고
  산출물은 `jd-viewer/public/study/` 에 쌓인다.
  **2026-09-08 부터 뷰어 화면에서는 빠져 있다** — `/wiki` 를 책장이 가져갔다.
  데이터와 엔진은 그대로 살아 있고, 화면 코드만 `jd-viewer/archive/study-wiki/` 로
  옮겨 뒀다(되살리는 법은 그쪽 README).
- **책(`jd-viewer/public/book/`)** : `/wiki` 가 읽는 것. 낱말 사전이 아니라 **차례가
  있는 한 권**이다 — 위키독스처럼 왼쪽에 차례가 상주하고 이전/다음으로 이어 읽는다.
  차례의 뼈대는 인프런 커리큘럼에서 빌렸고 본문·예제·그림은 직접 쓴다.
  **매 절은 눈으로 확인할 수 있는 것으로 끝난다** — 책마다 그 '것' 이 다르다.
  ① 「자바 ORM 표준 JPA 프로그래밍 — 기본편」(12장 56절, 완결) — 실제로 나가는 SQL
  ② 「스프링 핵심 원리 — 기본편」(9장 61절, 완결) — 실행 결과·컨테이너 로그
  ③ 「스프링 MVC 1편」(9장 71절, 완결) — 실제로 오간 HTTP
  ④ 「스프링 MVC 2편」(13장 99절, 완결) — 오간 HTTP. 절반이 오류 응답이다
  ⑤ 「스프링 DB 1편」(8장 57절, 완결) — 나간 SQL 과 커넥션·트랜잭션 로그
  ⑥ 「스프링 DB 2편」(13장 83절, 완결) — 나간 SQL. 같은 SQL 을 다섯 기술이 만든다
  **혼자 읽는 책이라 색인하지 않는다** — noindex + sitemap/prerender 제외 + robots
  Disallow. 형식과 집필 규칙(특히 ASCII 그림에서 한글을 테두리 왼쪽에 두지 않는 규칙)은
  `jd-viewer/public/book/README.md`.
- `design-lab/` : 공고 한 건을 한 장의 이미지로 접어 소셜에 올리는 실험실(8780).
  인스타에서 모은 상세페이지·채용포스터 캡처(`refs.json` — 읽은 것/훔칠 것/버릴 것)를
  템플릿으로 옮겨 놨다. `poster/`(공고 색인 → 원고 → HTML → Playwright 렌더) →
  `publish/`(인스타·페북·링크드인 어댑터 + 발행 큐 원장). 발행은 언제나 dry-run 이
  기본이고 `--live` 를 줘야 실제로 나간다. 자세한 건 랩 README.

실행 예: `python -m automation.auto_crawl start 개발자 100 1800`,
`python -m pipeline.aggregate 개발자`, `python -m pipeline.close_check --limit 300`, `python -m monitoring.health report`,
`python -m semantic.ingest && python -m semantic.embed && python -m semantic.similar`,
`python -m semantic.search "재택 되는 백엔드"`, `python -m semantic.server`

## 로컬 서버 포트
8765 stats(통계) / 8770 ops(크롤 운영) / 8771 search(검색 API) / 8910 admin(개인 이력, LAN 전용)
/ 8780 design-lab(레퍼런스·포스터 렌더·소셜 발행, 파이프라인과 분리된 실험용).
검색 API 는 뷰어 nginx 가 `/api/` 로 프록시하므로 별도 터널이 필요 없다.

## 운영 주의
- 이 머신은 8GB M1 이다. Playwright 크롤과 Ollama 임베딩이 동시에 뜨면 컨텍스트
  할당에 실패한다. 전량 임베딩이 필요하면 `auto_crawl stop` 후 돌린다.
- `screenshots/` 는 타임스탬프 스냅샷이 사이클마다 쌓인다(개당 ~250MB).
  `auto_crawl` 이 매 사이클 계열별 3개만 남기고 정리한다(`auto_crawl prune`으로 수동 실행).
- 새 공고의 임베딩은 크롤 사이클 끝의 `refresh_semantic()` 이 증분으로 처리한다.
  그러려면 Ollama 가 늘 떠 있어야 한다 — `brew services start ollama`.
  꺼져 있으면 사이클은 그대로 돌고 임베딩만 조용히 건너뛴다(추천·검색이 낡아간다).
- 검색 API(8771)는 `./deploy/setup-dashboards.sh` 가 launchd 로 상시 등록한다.
  이게 없으면 뷰어의 `/api/` 는 SPA 폴백으로 index.html 을 200 으로 돌려준다.

## Git 워크플로
- 커밋 메시지는 Conventional Commits 형식을 따른다: `type(scope): subject`
- type은 다음 중 하나: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- subject는 명령형, 50자 이내, 끝에 마침표 없음
- 한 커밋은 하나의 논리적 변경만 담는다. 관련 없는 변경은 나눠서 커밋한다
- 커밋 전 반드시 테스트와 타입체크를 통과시킨다
- **IMPORTANT: `git push`는 절대 자동으로 하지 말 것. 사용자가 명시적으로 "푸시해"라고 할 때만 푸시한다**
