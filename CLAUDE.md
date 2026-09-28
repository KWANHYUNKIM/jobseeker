# 프로젝트 가이드

채용 사이트(wanted/jumpit/jobkorea/saramin/devocean) 크롤링 → 통합/분류 → 대시보드/뷰어 시각화 시스템.

- `catch_capture/` : 채용 크롤 파이프라인 (기능별 패키지)
  - `crawlers/` : 사이트별 크롤러(crawl_*.py) + 공통(jobs_common)
    `crawl_freelance` 는 채용 공고가 아니라 **외주·프리랜서 프로젝트**(SI/SM 상주·도급·부업)를
    모은다 — 원티드 긱스(API)·프리모아(목록 JSON, 의뢰인 이메일 필드는 버린다)·이랜서(사이트맵 →
    상세 JSON-LD)·잡코리아(jobtype=6)·사람인(job_type=9)·아임잡·SISM(약관상 목록 요약과 링크만).
    all_jobs 와 섞지 않고 `public/freelance.json` 에 누적하며, 사이클 끝의 별도 단계로 돈다
    (crawl_all `--no-freelance` 로 끈다). 뷰어 `/freelance` 탭이 읽는다. DB 는 `project` 계열
    (`db/migrations/005`, `store/freelance.py` 로 이중 쓰기) — job 과 따로 두되 tech 사전은 공유한다.
    **사람을 구하면 닫힌다** — 목록에서 빠진 모집중 프로젝트를 회차당 60건씩 원본에 다시 묻는다
    (긱스 상세 API·이랜서 JSON-LD·잡코리아/사람인은 close_check 판정기·아임잡 상세 상태·SISM 은
    이틀 안 보이면 게재 종료). **단가 이력**: 단가·상태·기간이 바뀐 순간만 프로젝트의 `history`
    와 DB `project_version`(006)에 쌓고, 주별 월 단가 중앙값·기술별 단가·단가를 바꾼 프로젝트를
    `trend` 로 미리 세어 둔다. 추이는 '올라올 때 단가'로 센다.
    **단가 분석은 따로 뺀 페이지다**(`/freelance/rates`, 목록 위에 얹지 않는다). 몸값은 중간값
    하나가 아니라 등급(초·중·고·특급 — 표기 우선, 없으면 경력으로 추정)과 SI/SM·분야·직무로
    갈린다 — `pipeline/freelance_rates.py` 가 분류(classify)·분석(analyze)·요약 문장(insights)을
    만들어 `analysis` 에 싣고, DB 는 007(`project_pay_by_grade`)이 같은 값을 낸다.
    분석 페이지의 첫 화면은 **현재 단가표**(최근 90일에 본 개발 프로젝트, 등급 × 전체·SI·SM)이고
    칸을 누르면 그 숫자를 만든 프로젝트(원문·등급 근거)와 CSV 가 나온다 — 칸의 id 목록을 분석
    모듈이 같이 실어서 표와 근거가 어긋날 수 없다. **기록은 매일, 보기는 월별**: 크롤마다 그날의
    단가표를 `rate_history`(JSON)·`project_rate_snapshot`(DB 008)에 쌓고, 추이는 그 기간에
    올라온 자리로 다시 센다. **추이는 늘 등급별로 긋는다** — 전체 중앙값 하나로는 등급 구성이
    바뀐 것과 단가가 바뀐 것을 가를 수 없다. 주별·월별 코호트를 '분야|유형' 조합마다 미리 세어
    (`analysis.cohorts`) 화면이 분야·유형을 골라 본다(표본 3건 미만인 점은 선에 올리지 않는다).
    위시켓(약관 금지)·OKKY(robots 전면 차단)·크몽(스크래핑 금지)은 일부러 뺐다.
  - `pipeline/` : 통합/중복제거/마감분류(aggregate, job_status), 수동보정(overrides)
    마감 판정은 두 겹이다 — 공고가 들고 온 텍스트(`job_status`)와, 원본 사이트에
    다시 물어보는 재확인(`close_check` → `job_closures.json` 원장). 원장이 우선한다.
    크롤은 "지금 올라온 공고"만 알려주므로 재확인이 없으면 마감이 영영 안 닫힌다
    (특히 목록에 마감일 표기가 없는 wanted). auto_crawl 이 사이클마다 400건, 그와 별개로
    launchd `com.jobseeker.closecheck` 가 10분마다 100건씩 돌린다(`setup-crawler.sh` 가
    깐다 — 운영 크롤은 `once` 라 auto_crawl 의 대기 중 루프는 안 돈다). 둘이 겹치면
    원장 잠금(`job_closures.lock`)을 못 잡은 쪽이 그 회차를 건너뛴다.
    뷰어도 `deadline_date` 가 지난 공고는 받은 status 와 무관하게 닫는다(`useJobs`) —
    파이프라인이 멈춰 데이터가 낡아도 날짜 지난 공고는 모집중에 안 남는다.
    다시 묻는 주기는 공고마다 다르다 — 처음 보는 것·목록에서 사라진 것은 즉시,
    마감일 모름 1일, 마감일 있음 3일(조기 마감), 지난번 답 못 얻음 7일.
    재확인은 **등록일도 같이 받아 온다** — 어느 크롤러도 수집하지 않던 값인데
    원본이 이미 주고 있었다(JSON-LD `datePosted`, jumpit `publishedAt`).
    wanted 는 chaos API 가 아니라 **공고 페이지 JSON-LD** 에 `datePosted`·
    `validThrough` 가 둘 다 있다 — "wanted 는 마감일이 없다"는 API 얘기였다.
    등록일이 없는 곳은 saramin 하나뿐이고 그 자리는 `first_seen_at` 이 대신한다
    (추정값이라 화면이 구분해 보여준다). 출처표는 `db/README.md` 의 "3-1".
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
    사이트 간 중복도 지우지 않고 `job_dup` 뷰가 대표를 가리킨다(모집중 → 사이트 순서).
    `store.export` 가 사본을 걸러 뷰어·빌더에는 한 건만 간다.
    `posted_on`(등록일)은 close_check 만 쓴다 — `JOB_COLUMNS` 에 없어서 크롤이
    NULL 로 덮지 못한다. 스키마를 고칠 때는 `db/migrations/` 에 번호순 ALTER 를
    남긴다(돌고 있는 DB 는 `schema.sql` 을 다시 못 돌린다).
    이중 쓰기는 실패해도 사이클을 죽이지 않는다(`DB_DUAL_WRITE=0` 으로 끈다).
    크롤러 폴더의 `jobs.json` 은 **누적본**이라 "지금 올라와 있나"를 모른다. 그래서
    크롤러가 회차마다 목록에서 본 pid 를 `listed.json` 에 따로 남기고, DB 는 거기
    있던 공고만 `last_seen_at` 을 갱신한다. 사라짐(`gone_at`)은 **목록을 끝까지 본
    범위** — ats 의 받아 온 보드 — 에서만 찍는다. 검색 앞 몇 쪽만 보는 사이트는
    안 보였다고 내려간 게 아니라서 close_check 가 원본에 물어 닫는다. 받아 온
    보드들에서 절반 넘게 안 보이면(`DB_GONE_MIN_RATIO`) 사이트째 보류한다 —
    파서가 깨진 것과 공고가 내려간 것은 다르다. 지우지는 않는다.
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
  ⑦ 「스프링 부트와 JPA 활용 1편」(10장 64절, 완결) — 그 결정이 만든 것.
     DDL·SQL·HTTP·쿼리 개수 순으로 바뀐다
  ⑧ 「스프링 부트와 JPA 활용 2편」(7장 48절, 완결) — 나간 JSON 과 그것을
     만든 쿼리 개수. 같은 응답을 여섯 번 만들어 31 을 3 으로 줄인다
  ⑨ 「Practical Testing — 실용적인 테스트 가이드」(10장 72절, 완결) —
     실제로 돌린 테스트 결과. 절반이 빨간 막대다
  ⑩ 「스프링 시큐리티 완전 정복」(12장 90절, 완결) — 오간 HTTP 와
     그 요청이 지나간 필터 목록. 막힌 자리가 곧 고칠 자리다
  ⑪ 「개발자를 위한 도커」(11장 69절, 완결) — 실제로 친 명령과 그 출력.
     막힌 출력도 같이 싣는다
  ⑫ 「쿠버네티스 입문」(11장 67절, 완결) — kubectl 이 돌려준 것.
     Pending 과 CrashLoopBackOff 를 읽는 것이 절반이다
  ⑬ 「모든 개발자를 위한 HTTP 웹 기본 지식」(9장 64절, 완결) —
     와이어에 실제로 오간 요청·응답 원문
  ⑭ 「실전! 스프링 데이터 JPA」(8장 56절, 완결) — 구현을 한 줄도
     안 쓰고 받아 낸 SQL. 인터페이스만 적었는데 문장이 나온다
  ⑮ 「실전! Querydsl」(8장 61절, 완결) — 조립한 코드가 만든 JPQL 과,
     그 JPQL 이 만든 SQL. 이 책만 두 겹이다
  ⑯ 「스프링 부트 — 핵심 원리와 활용」(10장 80절, 완결) — 기동 로그와
     엔드포인트 응답. 부트가 대신한 일은 로그에 남는다
  ⑰ 「스프링 핵심 원리 — 고급편」(12장 85절, 완결) — 찍힌 로그와
     그 빈의 진짜 클래스 이름. 이름 끝에 붙은 글자가 주제다
  ⑱ 「아파치 카프카 애플리케이션 프로그래밍」(11장 72절, 완결) —
     실제로 친 명령과 오간 레코드. 보냈다는 것과 처리됐다는 것 사이가 주제다
  ⑲ 「실전 자바 — 멀티스레드와 동시성」(12장 74절, 완결) — 찍힌 스레드
     이름과 실행 순서. 같은 코드를 여러 번 돌린 결과를 같이 싣는다
  ⑳ 「자바 성능 튜닝 — JVM 과 GC」(12장 79절, 완결) — 찍힌 GC 로그와
     그 순간의 힙 스냅숏. 옵션을 바꿨으면 바꾸기 전 로그도 같이 싣는다
  ㉑ 「실전 자바 — I/O, 네트워크, 리플렉션」(11장 67절, 완결) —
     od 로 찍은 실제 바이트나 소켓에 오간 원문. 같은 일을 여러 방법으로
     하고 느린 쪽도 같이 싣는다
  **서가는 갈래(track)로 묶인다** — 기반 지식 · 스프링 · 데이터 접근 ·
  실전 프로젝트 · 품질과 보안 · 인프라와 배포. `index.json` 의 `tracks` 가
  원본이고 화면 왼쪽 차례가 이걸로 그린다. 새 책에 `track` 을 안 적으면
  '그 밖의' 로 모인다(사라지지는 않는다).
  **혼자 읽는 책이라 색인하지 않는다** — noindex + sitemap/prerender 제외 + robots
  Disallow. 형식과 집필 규칙(특히 ASCII 그림에서 한글을 테두리 왼쪽에 두지 않는 규칙)은
  `jd-viewer/public/book/README.md`.
- `design-lab/` : 공고 한 건을 한 장의 이미지로 접어 소셜에 올리는 실험실(8780).
  인스타에서 모은 상세페이지·채용포스터 캡처(`refs.json` — 읽은 것/훔칠 것/버릴 것)를
  템플릿으로 옮겨 놨다. `poster/`(공고 색인 → 원고 → HTML → Playwright 렌더) →
  `publish/`(인스타·페북·링크드인 어댑터 + 발행 큐 원장). 발행은 언제나 dry-run 이
  기본이고 `--live` 를 줘야 실제로 나간다. 자세한 건 랩 README.
  **소셜 자동 발행**(인스타·페이스북): 사람은 `publish.cli approve`(윈도우) → `push` 까지만, 맥의
  `publish.daemon tick`(launchd 5분, `deploy/setup-publisher.sh`)이 12:30·19:30 슬롯에 한 건씩
  올린다. 올리는 단위는 공고 한 건(`approve`)과 **카테고리 묶음**(`approve-collection` —
  이번 주·마감임박·직군·회사규모·기술·신입, 키워드 표지 + 차례 표지 + 공고 판 8장까지를 한 게시물로;
  `poster/collection.py`)이다. 묶음은 **캐러셀이거나 릴스거나 하나**다 —
  `--as reel` 을 주면 같은 판을 9:16 으로 다시 찍어 장당 1.8초씩 이어 붙인 영상 한 편으로
  나간다(`poster/video.py`, ffmpeg). 둘 다 올리면 중복 게시로 보인다.
  영상은 무음이다 — API 로는 음원을 못 붙인다. 원장은 맥에만 있고, 결과는 8770 '인스타 발행' 칸(읽기 전용 — 8770 은 무인증 공개라
  버튼·토큰을 두지 않는다). `autopublish.live` 가 꺼져 있으면 연습 발행만 한다. 한 판이 인스타와 페이스북 페이지
  양쪽에 나가고(캡션은 플랫폼별로 따로), 한쪽만 실패하면 실패한 쪽만 다시 시도한다. `design-lab/SOCIAL.md`.

실행 예: `python -m automation.auto_crawl start 개발자 100 1800`,
`python -m pipeline.aggregate 개발자`, `python -m pipeline.close_check --limit 300`, `python -m monitoring.health report`,
`python -m semantic.ingest && python -m semantic.embed && python -m semantic.similar`,
`python -m semantic.search "재택 되는 백엔드"`, `python -m semantic.server`

## 로컬 서버 포트
8765 stats(통계) / 8770 ops(크롤 운영) / 8771 search(검색 API) / 8910 admin(개인 이력, LAN 전용)
/ 8780 design-lab(레퍼런스·포스터 렌더·소셜 발행, 파이프라인과 분리된 실험용)
/ 8790 agent-mcp(사용자의 에이전트에 채용 데이터·절차를 붙이는 MCP 서버, `catch_capture/agent_mcp/`).
검색 API 는 뷰어 nginx 가 `/api/` 로 프록시하므로 별도 터널이 필요 없다.
agent-mcp 는 검색 API 와 일부러 뗐다 — 외부 에이전트의 호출량이 뷰어 검색을 느리게 하면 안 된다.
**LLM 을 부르지 않는다** — 생각은 연결한 사람의 에이전트가 하고(토큰도 그쪽), 이 서버는 읽기 전용 도구
(공고·회사 브리핑·기술·외주 단가)와 절차 프롬프트(적합도·지원서 작성→검토→ATS·면접·단가 협상)만 준다.
이력서는 이 서버로 오지 않는다(ATS 는 키워드만 내준다). 아직 인증·호출량 제한이 없어 공개하지 않는다.

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
