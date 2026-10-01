# jobseeker

채용 사이트를 크롤링해 정본 DB(PostgreSQL)에 쌓고, 뷰어·대시보드로 보여 주는 시스템.
작업 규칙과 설계 근거는 [`CLAUDE.md`](CLAUDE.md)에 있다.

```
크롤러·파이프라인(catch_capture) ──쓰기──▶ PostgreSQL(db/) ◀──읽기── 뷰어 API(backend, 8771) ◀── 뷰어(jd-viewer)
                                   └─ 대시보드·운영 서버(catch_capture/servers)
```

## 폴더

| 폴더 | 무엇 |
|---|---|
| `catch_capture/` | 쓰는 쪽 — 크롤·통합·마감 재확인·DB 적재·임베딩, 그리고 사람이 보는 서버들 |
| `backend/` | 읽는 쪽 — 뷰어 API(FastAPI). DB 를 읽기만 한다 |
| `jd-viewer/` | 뷰어(React/Vite). API 먼저, 안 되면 정적 파일 |
| `db/` | 스키마(`schema.sql`)와 번호순 마이그레이션 — 파이프라인과 backend 가 같이 쓴다 |
| `deploy/` | 운영 맥 설치·launchd 등록 스크립트 |
| `engine/` `guide-engine/` `hw-engine/` `study-engine/` | Claude `/loop` 조사 엔진(역설계·취업 브리핑·하드웨어·백과사전) |
| `design-lab/` | 공고 포스터·소셜 발행 실험실(8780) |
| `ai-job-search/` | 구직 워크플로(git subtree, 원본 MIT) |
| `archive/` | 지금 시스템과 무관한 옛 코드(첫 커밋의 뉴스 크롤링 프로젝트 등) |

### catch_capture

```
catch_capture/
├─ core/         공통 기반 — paths(경로·데이터 위치) · sites(사이트 등록부) · normalize · classifier
├─ crawlers/     사이트별 크롤러(crawl_*.py) + 공통(jobs_common)
├─ pipeline/     통합(aggregate) · 마감(job_status·close_check) · 트렌드 · 헬스 · 행동 점수 …
├─ store/        정본 DB 접근 — db/ · ingest/ · jobs/ · vectors/ · market/
├─ automation/   크롤 회차 오케스트레이션(auto_crawl·crawl_all·orchestration) · 반복 작업 등록부(loops)
├─ servers/      사람·에이전트가 붙는 서버 — ops(8770) · stats(8765) · collect(8772) · admin(8910) · agent_mcp(8790)
├─ tests/
└─ var/          런타임 데이터(git 밖) — admin 개인 데이터·방문 기록
```

규칙: 모듈은 `catch_capture` 를 루트로 import 한다(`python -m servers.ops.server`). 데이터는
코드 폴더 안에 두지 않는다 — `core/paths.py` 가 위치의 단일 소스다.

## 실행

```bash
# 파이프라인(catch_capture 에서)
python -m automation.auto_crawl once "개발자" 50
python -m pytest

# 뷰어 API(backend 에서)
python -m app.main            # http://127.0.0.1:8771/api/docs
python -m pytest

# 뷰어(jd-viewer 에서)
npm install && npm run dev    # http://localhost:5173
npm test && npm run build
```

운영(맥) 설치는 `deploy/README.md`.
