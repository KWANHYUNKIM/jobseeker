# 강의 노트 엔진 — 한 사이클 절차

역설계(`engine/`)가 "그 회사가 어떻게 만들어졌나"라면 여기는 **"요즘 무엇을 어떻게 공부하나"**다.
Stanford·MIT 같은 공개 강의와 국내외 개발 강의 영상을 읽고, 우리 말로 다시 쓴 노트를
`jd-viewer/public/lectures/` 에 쌓는다. 뷰어 `기업정보 > 강의 노트`(`/lectures`)가 읽는다.

Claude 는 영상을 직접 보지도 듣지도 못한다. 그래서 **말은 자막으로, 그림은 장면으로** 읽는다.

## 한 사이클 = 영상 한 편

1. 다음 일감: `python lecture-engine/validate.py --gaps` 맨 위 id.
   대기열(`state/QUEUE.md`)이 비면 새 영상을 찾아 덧붙인다 — 우선순위:
   Stanford Online(CS229·CS224N·CS231N·CS336·CS25·CS329 계열) → MIT·Berkeley·CMU 공개 강의 →
   국내 개발 채널. 최근 1년 안 학기를 앞에 둔다(트렌드가 목적이다).
2. 재료 받기: `python lecture-engine/fetch.py <id>` → `catch_capture/var/lectures/<id>/`
   - `meta.json`(제목·길이·챕터·자막 종류) · `transcript.txt`(1분 단위 대본) · `sheets/sNNN.jpg`
     (30초마다 장면 16칸을 한 장에 — 한 장 = 8분, 칸 왼쪽 위 노란 글씨가 영상 속 시각)
3. 읽기: 대본을 처음부터 끝까지 읽고, 인화를 **전부** 본다. 슬라이드·판서에 뜬 그래프·표·수식은
   대본에 없으니 장면에서 읽어 `chapters[].on_screen` 에 적는다.
4. 쓰기: `jd-viewer/public/lectures/items/<id>.json` — 형식은 `schema.json`.
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
