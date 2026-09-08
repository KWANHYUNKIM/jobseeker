# 보관 — 기술 백과사전 화면 (2026-09-08)

`/wiki` 가 낱말 단위 백과사전에서 **책장**(`src/components/BookView.tsx`)으로 바뀌면서
화면에서 떼어 낸 파일들이다. 라우트에 걸려 있지 않고 컴파일 대상도 아니다.

- `WikiView.tsx` — 낱말 문서 목록·상세 화면
- `useStudy.ts` — `public/study/*.json` 타입과 로더

데이터(`jd-viewer/public/study/`)와 생성 엔진(`study-engine/`)은 **그대로 살아 있다.**
되살리려면 두 파일을 `src/` 로 되돌리고 `paths.wikiArticle()` 을 다시 만든 뒤
(지금은 `paths.book`/`paths.bookPage` 가 그 자리를 쓴다) 라우트를 붙이면 된다.
