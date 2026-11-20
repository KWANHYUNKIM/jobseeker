# 강의 노트 엔진 — 한 사이클 절차

역설계(`engine/`)가 "그 회사가 어떻게 만들어졌나"라면 여기는 **"요즘 무엇을 어떻게 공부하나"**다.
Stanford·MIT 같은 공개 강의와 국내외 개발 강의 영상을 읽고, 우리 말로 다시 쓴 노트를
`jd-viewer/public/lectures/` 에 쌓는다. 뷰어 `기업정보 > 강의 노트`(`/lectures`)가 읽는다.

Claude 는 영상을 직접 보지도 듣지도 못한다. 그래서 **말은 자막으로, 그림은 장면으로** 읽는다.

## 한 사이클 = 영상 한 편

1. 다음 일감: `python lecture-engine/validate.py --gaps` 맨 위 id. 순서는 `state/QUEUE.md` 에 손으로 올린 것 →
   `series.json` 의 과목 순서대로 앞 강의부터(사용자가 1강부터 N강까지 이어 볼 수 있게).
   과목 추가: `python lecture-engine/series.py add <재생목록 id> <키> --code CS229 --term "Spring 2026" --title "..."`,
   새 강의가 올라왔는지는 `series.py refresh`.
   대기열(`state/QUEUE.md`)이 비면 새 영상을 찾아 덧붙인다 — 우선순위:
   Stanford Online(CS229·CS224N·CS231N·CS336·CS25·CS329 계열) → MIT·Berkeley·CMU 공개 강의 →
   국내 개발 채널. 최근 1년 안 학기를 앞에 둔다(트렌드가 목적이다).
2. 재료 받기: `python lecture-engine/fetch.py <id>` → `catch_capture/var/lectures/<id>/`
   - `meta.json`(제목·길이·챕터·자막 종류) · `transcript.txt`(1분 단위 대본) · `sheets/sNNN.jpg`
     (30초마다 장면 16칸을 한 장에 — 한 장 = 8분, 칸 왼쪽 위 노란 글씨가 영상 속 시각)
3. 읽기: 대본을 처음부터 끝까지 읽고, 인화를 **전부** 본다. 슬라이드·판서에 뜬 그래프·표·수식은
   대본에 없으니 장면에서 읽어 `chapters[].on_screen` 에 적는다.
4. 쓰기: `jd-viewer/public/lectures/items/<id>.json` — 형식은 `schema.json`.
   **깊이 기준(2026-11-20, 사용자 요청 "너무 축약해서 공부가 안 된다")** — 노트는 요약이 아니라
   **영상을 안 본 사람이 이것만 읽고 공부할 수 있는 교재**다. 참고: Princeton COS511 스크라이브 지침
   (빠진 학생도 이해하는 완결된 문장, 받아 적은 메모가 아님), MIT 스크라이브 팁(강의보다 더 잘 설명하라),
   CS231n 공식 노트(강의 하나에 6천 단어 안팎, 개념마다 직관 → 식 → 작은 숫자 예 → 코드 → 주의점).
   - 챕터마다 `explain` 문단 3개 이상·600자 이상: 직관(비유) → 정의 → 왜 그런가 → 강의가 든 예.
     강의가 빠르게 넘어간 곳은 더 풀어 쓴다. 노트 전체 본문은 강의 1분당 200자 이상(validate 가 센다).
   - 식이 나오면 `formulas` 에 기호 하나하나의 뜻까지. 식이 있는 챕터는 `example` 로 작은 숫자를 직접 넣어 본다.
   - 코드로 확인할 수 있는 개념은 `code`(직접 쓴 30줄 안쪽 — 슬라이드 코드를 옮기지 않는다).
   - 구조·흐름은 `diagram`(mermaid). 헷갈리는 곳은 `pitfalls`. 챕터마다 `check` 문제 1~3개(답 포함).
   - 국내 강의·비기술 강의(포트폴리오·커리어)도 같다 — 식·코드 대신 사례·체크리스트로 채운다.
   - 요약은 **우리 말로 다시 쓴다.** 대본 문장을 옮기지 않는다(validate 가 긴 영어 덩어리를 막는다).
     용어·수식·짧은 고유명사만 원문 그대로.
   - 챕터는 8~15개, `start` 는 그 이야기가 시작되는 초(원본 영상의 그 자리로 링크된다).
   - `trends` 는 강의가 말한 업계 흐름이다. 강사의 의견이면 "강사 의견" 이라고 적는다.
   - `study` 는 "이 강의를 듣고 무엇을 어떤 순서로 공부하나" — 선수 지식·단계·손으로 할 과제·
     공식 자료(과목 홈페이지·논문·공식 문서) 링크.
   - `tags`·`jobs.skills` 는 공고 `tech_stack` 표기(PyTorch, Python, CUDA, Kubernetes …)에 맞춘다.
5. 검증: `python lecture-engine/validate.py` — 통과하면 `index.json` 이 다시 구워진다.
6. 기록: `state/LOG.md` 에 한 줄(날짜 · id · 제목 · 챕터 수). 커밋:
   `git add jd-viewer/public/lectures lecture-engine/state` → `feat(lectures): <과목> <제목> 노트`.
   푸시는 하지 않는다. 재료 폴더(`var/lectures/<id>`)는 커밋하지 않는다.

## 하지 않는 것
- 원본 영상·장면 이미지·대본을 공개 폴더에 두지 않는다 — 공개되는 건 노트뿐이고 원본은 링크한다.
- 유료 강의(인프런 유료 등)의 본문을 받지 않는다. 공개된 소개·커리큘럼 페이지만 쓴다.
- 봇 차단·로그인을 우회하지 않는다.
