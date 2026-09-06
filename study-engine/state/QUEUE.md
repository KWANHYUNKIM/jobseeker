# 대기열 — 쓸 낱말

`validate.py --gaps` 의 사다리 3순위가 이 파일의 "대기" 표 **맨 위 한 줄**을 읽는다.
표의 첫 열(낱말)만 기계가 읽는다 — 나머지 열은 사람과 다음 사이클을 위한 근거다.

> ⚠️ 이 문서를 스크립트로 고칠 때 `s.index("## 대기")` 로 자르지 말 것.
> 위 문장에 같은 글자가 있어 인트로 한가운데를 잘라 먹는다. `"\n## 대기"`(줄 시작)로 찾는다.

큐에 올릴 자격은 셋 중 하나다 (PROMPT.md 2⁗단계).
**(a) 수요가 큰데 문서가 없다** / **(b) 이미 쓴 문서가 계속 가리킨다(끊긴 `related`)** /
**(c) 공고·블로그에는 나오는데 어디에도 설명이 없는 말.**

## 대기

| 낱말 | slug | 왜 이 낱말 | 무엇을 읽을 수 있나 |
|---|---|---|---|



| 헥사고날 / 클린 아키텍처 | `hexagonal-architecture` | ⭐⭐⭐ **`bounded-context` 가 방금 `open_questions` 2번에 "이 문서 다음의 가장 큰 빈자리"라고 적은 자리**(사다리 2순위 — 두 사이클 연속 문서가 스스로 가리켰다). ⭐⭐⭐ **셈(2026-09-06): `클린 아키텍처\|clean architecture\|헥사고날\|hexagonal\|포트-어댑터` 174건(모집중 71)** — ⚠️⚠️ **`DDD`(대문자) 88건보다 많다.** 그 밖: `모듈화\|모듈 분리\|모듈 설계` 210(87) · `도메인 모델` 131(54) · `의존성 역전\|DIP` **3(2)** · `SOLID`(⭐ 대문자만) 15 · `바운디드 컨텍스트` 12 · `유비쿼터스 언어` **0**. ⭐⭐⭐ **축 후보: "구조는 174번 불리는데 그 구조가 지키려는 것(의존성 방향)은 3번 불린다."** ⚠️ **`의존성 역전` 3건을 반드시 재확인**한다 — 다른 표현(`인터페이스 분리`·`추상화에 의존`·`결합도`)으로 셌을 때 달라지는지. ⭐⭐ **`bounded-context` 가 이미 관찰 하나를 남겼다** — 공고가 **`Clean Architecture 또는 DDD`(커넥트웨이브)** 처럼 **"또는"으로 묶는다**. **층을 나누는 일과 모델을 나누는 일이 같은 것으로 취급**된다. ⭐ 그 문서는 그 관계를 **단정하지 않았고**(1차 자료를 안 봐서), **여기서 답한다.** ⭐⭐⭐ **1차 자료는 원저자로 간다** — **Alistair Cockburn, `Hexagonal Architecture`**(alistair.cockburn.us/hexagonal-architecture/). ⭐ 유명한 의도 문장이 있다: **"Allow an application to equally be driven by users, programs, automated test or batch scripts, and to be developed and tested in isolation from its eventual run-time devices and databases."** 보조: **Uncle Bob, `The Clean Architecture`**(blog.cleancoder.com) — ⭐ **의존성 규칙**("source code dependencies can only point inwards"). ⚠️ **둘의 관계(같은 것인가 다른 것인가)를 원문으로 확인**한다. 축 넷: ①⭐⭐⭐**무엇으로부터 격리하려는 것인가**(DB·프레임워크·UI — 원문이 이름을 든다) ②⭐⭐**테스트가 목적에 들어 있다**("automated test" 가 의도 문장에 있다 → `testing` 과 잇는다) ③⚠️**`bounded-context` 와의 관계** — 층이냐 경계냐 ④**대가**(포트·어댑터가 늘면 코드가 는다 — ⚠️ 원문이 인정하는지 확인). ⚠️ **겹침 확인 필수**: `bounded-context`(층과 경계의 관계를 미결로 남겼다) · `testing` · `spring`·`java` · `monorepo`. ⚠️ **aliases 확인 필요**(`클린 아키텍처`·`헥사고날`·`포트와 어댑터`). ⭐⭐⭐ **그리고 이번엔 1차 자료를 여는 그 호출에 실패 사례 검색을 함께 넣는다** — `github-actions`·`migration`·`aws`·`microservices`·`bounded-context` 다섯 사이클 연속 못 지킨 규칙이다. | ⭐⭐⭐ **1차 자료: alistair.cockburn.us/hexagonal-architecture/** (+ blog.cleancoder.com 의 `The Clean Architecture`). ⭐ **부정어 먼저**: not · never · shouldn't · avoid · isolation from · independent of. ⚠️ **못 열면 축을 바꾼다** — 대안: `리팩터링` **753건**(Fowler 의 `Refactoring`, ⭐ `technical-debt`·`testing`·`code-review` 사슬의 마지막 조각) |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| ⭐ 테스트 피라미드 (`testing` 보강) | **`testing` 이 "가장 큰 빈자리"라고 적었으나 셈이 없다** — `테스트 피라미드` **2건**. ⚠️⚠️ 그리고 `E2E` 로 세면 **1582건인데 모집중 65%** 로 **오염**이다("End-to-End로 설계" 같은 **업무 범위** 표현이 걸린다 — ⭐ **네 번째 오염 형태: 같은 약자의 다른 뜻**). 쓸 수 있는 값은 `통합 테스트` **176** · `Playwright\|Cypress\|Selenium` **273** 뿐. | **`testing` 의 보강 사이클로 처리한다**(사다리 4순위). 1차 자료는 Fowler 의 `TestPyramid` 로 확실하고, ⭐ **셈 없이 쓸 수 있는 드문 경우**(그 문서가 이미 축을 세워 뒀고 피라미드는 그 안의 배치 문제다). |
| ⭐ `go` 의 동시성 절 (보강) | **`go` 문서가 스스로 "가장 큰 구멍"이라고 적었다** — 고루틴·채널·`select`·CSP 를 한 줄도 못 썼다. ⚠️ **셈이 없어서**다(`고루틴` 1건, `채널` 은 채널톡 오염으로 사용 불가). ⭐ `asyncio` 와 겹치지도 않는다(그쪽에 `Go` 0회). | **1차 자료를 찾으면 바로** — `Effective Go` 의 동시성 절, 또는 `Go Blog` 의 "Share Memory By Communicating". ⭐ **셈 없이 쓰는 것이 허용되는 드문 경우**다(언어의 핵심 기능이고 1차 자료가 확실하다). 보강 사이클(사다리 4순위)로 처리한다. |
| 시맨틱 버저닝 (`semantic-versioning`) | **셈에서 3건(모집중 1)** — `시맨틱 버저닝\|semantic version\|semver\|MAJOR.MINOR` 로 이름을 대는 공고가 사실상 없다. `changeset\|Conventional Commits\|semantic-release` 까지 넓혀도 10건(모집중 2). `api-versioning` 이 끊긴 링크로 남겼으나 **근거가 이 백과사전 최저 수준**이라 지금 쓰면 '규격 요약본'이 된다. | **`monorepo` 를 쓴 뒤** — 그 문서가 `fixed vs independent` 버저닝을 다루면서 이 낱말을 다시 가리킬 것이다. 또는 공고에서 `semver` 를 이름으로 대는 곳이 10건을 넘으면. |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
