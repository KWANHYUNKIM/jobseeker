# 프로젝트 가이드

채용 사이트(wanted/jumpit/jobkorea/saramin/devocean) 크롤링 → 통합/분류 → 대시보드/뷰어 시각화 시스템.

- `catch_capture/` : 채용 크롤 파이프라인 (기능별 패키지)
  - `crawlers/` : 사이트별 크롤러(crawl_*.py) + 공통(jobs_common)
  - `pipeline/` : 통합/중복제거/마감분류(aggregate, job_status), 수동보정(overrides)
  - `monitoring/` : 헬스 기록·이상탐지(health)
  - `automation/` : 크롤 오케스트레이션(crawl_all) + 자동화 데몬(auto_crawl)
  - `dashboard/` : 통계 대시보드(serve.py, 8765)
  - `paths.py` : 공통 경로(데이터/venv 위치) 단일 소스
- `jd-viewer/` : React/Vite 기반 JD 뷰어 (5173, public 데이터 소비)

실행 예: `python -m automation.auto_crawl start 개발자 100 1800`,
`python -m pipeline.aggregate 개발자`, `python -m monitoring.health report`

## Git 워크플로
- 커밋 메시지는 Conventional Commits 형식을 따른다: `type(scope): subject`
- type은 다음 중 하나: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- subject는 명령형, 50자 이내, 끝에 마침표 없음
- 한 커밋은 하나의 논리적 변경만 담는다. 관련 없는 변경은 나눠서 커밋한다
- 커밋 전 반드시 테스트와 타입체크를 통과시킨다
- **IMPORTANT: `git push`는 절대 자동으로 하지 말 것. 사용자가 명시적으로 "푸시해"라고 할 때만 푸시한다**
