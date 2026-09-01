# 프로젝트 가이드

채용 사이트(wanted/jumpit/jobkorea/saramin/devocean) 크롤링 → 통합/분류 → 대시보드/뷰어 시각화 시스템.

- `catch_capture/` : 채용 크롤 파이프라인 (기능별 패키지)
  - `crawlers/` : 사이트별 크롤러(crawl_*.py) + 공통(jobs_common)
  - `pipeline/` : 통합/중복제거/마감분류(aggregate, job_status), 수동보정(overrides)
  - `monitoring/` : 헬스 기록·이상탐지(health)
  - `automation/` : 크롤 오케스트레이션(crawl_all) + 자동화 데몬(auto_crawl)
  - `dashboard/` : 통계 대시보드(serve.py, 8765)
  - `semantic/` : 임베딩 기반 추천·검색 (SQLite+sqlite-vec 저장, Ollama bge-m3 증분 임베딩,
    코사인 top-K → `public/similar_*.json`). 크롤 사이클 끝에 auto_crawl 이 자동 실행.
    `search.py`(FTS5+벡터 RRF 하이브리드) / `server.py`(검색 API, 8771)
    마감 공고는 색인에 남기되(지난 공고 통계·유사도의 재료) `meta.status` 로 표시해
    검색·추천에서 뺀다. 검색은 `--include-closed` 로 열 수 있다.
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
  회사를 모집중 공고 수로 줄 세워 준다. 스킬은 `/hireguide`, 루프는 `/loop 30m /hireguide`.

실행 예: `python -m automation.auto_crawl start 개발자 100 1800`,
`python -m pipeline.aggregate 개발자`, `python -m monitoring.health report`,
`python -m semantic.ingest && python -m semantic.embed && python -m semantic.similar`,
`python -m semantic.search "재택 되는 백엔드"`, `python -m semantic.server`

## 로컬 서버 포트
8765 stats(통계) / 8770 ops(크롤 운영) / 8771 search(검색 API) / 8910 admin(개인 이력, LAN 전용).
검색 API 는 뷰어 nginx 가 `/api/` 로 프록시하므로 별도 터널이 필요 없다.

## 운영 주의
- 이 머신은 8GB M1 이다. Playwright 크롤과 Ollama 임베딩이 동시에 뜨면 컨텍스트
  할당에 실패한다. 전량 임베딩이 필요하면 `auto_crawl stop` 후 돌린다.
- `screenshots/` 는 타임스탬프 스냅샷이 사이클마다 쌓인다(개당 ~250MB).
  `auto_crawl` 이 매 사이클 계열별 8개만 남기고 정리한다(`auto_crawl prune`으로 수동 실행).
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
