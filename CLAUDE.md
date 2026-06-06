# 프로젝트 가이드

채용 사이트(wanted/jumpit/jobkorea/saramin/devocean) 크롤링 → 통합/분류 → 대시보드/뷰어 시각화 시스템.

- `catch_capture/` : 크롤러 + 통합(aggregate) + 자동화 데몬(auto_crawl) + 대시보드(dashboard)
- `jd-viewer/` : React/Vite 기반 JD 뷰어 (public 데이터 소비)

## Git 워크플로
- 커밋 메시지는 Conventional Commits 형식을 따른다: `type(scope): subject`
- type은 다음 중 하나: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- subject는 명령형, 50자 이내, 끝에 마침표 없음
- 한 커밋은 하나의 논리적 변경만 담는다. 관련 없는 변경은 나눠서 커밋한다
- 커밋 전 반드시 테스트와 타입체크를 통과시킨다
- **IMPORTANT: `git push`는 절대 자동으로 하지 말 것. 사용자가 명시적으로 "푸시해"라고 할 때만 푸시한다**
