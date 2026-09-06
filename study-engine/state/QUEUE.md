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



| 테스트 | `testing` | ⭐⭐ **`technical-debt` 가 남긴 끊긴 링크**(`related` 의 `testing`) — 그 문서가 **"부채를 갚으려면 안전망이 필요한데 1차 자료로 확인하지 않아 쓰지 않았다"** 고 적었다. **사슬이 이어졌다.** ⭐ **셈(2026-09-06)**: `테스트 코드|단위 테스트` **570(185)** · `테스트 자동화` 473(172) · `통합 테스트|E2E` 419(169) · `Jest|pytest|JUnit|Playwright|Cypress` 400(150) · ⚠️ `TDD|테스트 주도` **109(35)**. ⚠️⚠️ **못 쓰는 것 둘**: `테스트` 만으로는 **3964건**(면접 테스트·QA 등 — 너무 넓다). 그리고 ⭐⭐⭐ **`커버리지|coverage` 461건인데 모집중 381건 = 83%** — **`go`·`git` 에서 세운 진단법대로 오염 신호다.** ⚠️ **반드시 경계를 넣어 다시 세고**(`(?<![A-Za-z])coverage`), **`git` 사이클처럼 반대쪽(영문 안내문 등)을 세어 차이가 떨어지는지 확인한다.** ⚠️ **`aliases` 확인 완료**: `테스트`·`testing`·`단위 테스트`·`커버리지`·`TDD`·`E2E` 어느 것도 없다. ⚠️⚠️ **3964건짜리 낱말이라 그대로 쓰면 요약본이 된다.** ⭐⭐⭐ **축을 좁힌다: "커버리지는 테스트가 좋은지의 척도가 아니다."** ⭐⭐ **1차 자료가 그 축을 직접 준다** — Martin Fowler 의 **`TestCoverage`** 에 **"Test coverage is a useful tool for finding untested parts of a codebase. Test coverage is of little use as a numeric statement of how good your tests are."** 부류의 문장이 있다고 알려져 있다(⚠️ **확인 필요**). ⭐ `technical-debt` 사이클에서 배운 대로 — **확인 못 하면 축을 바꾼다.** 대안 1차 자료: Fowler 의 **`TestPyramid`**(비유의 한계를 스스로 적는다), Google 의 **`Test Sizes`**(small/medium/large — ⭐ **피라미드 대신 크기로 나눈 이유**를 적는 자리). 축 넷: ①⭐⭐**커버리지가 무엇을 말해 주고 무엇을 못 말해 주나**(빈 곳은 찾아 주지만 좋은지는 모른다) ②⭐⭐⭐**셈의 대비**(`커버리지` 461 vs `TDD` 109 — **숫자는 재는데 방법은 안 부른다**) ③**크기·속도의 맞바꿈**(`통합 테스트|E2E` 419 — ⚠️ `playwright` 문서가 있는지 확인) ④**부채를 갚는 안전망**(→ `technical-debt` 가 지목한 자리). **이웃**: `technical-debt`(정면 — 안전망) · `code-review`(사전 장치의 짝) · `github-actions`(어디서 도나) · `typescript`(타입 검사가 잡는 것은 테스트가 안 봐도 된다). | ⭐⭐⭐ **1차 자료: martinfowler.com 의 `TestCoverage` · `TestPyramid`** + 보조로 Google Testing Blog 의 `Test Sizes`. ⭐ **부정어 먼저**: of little use · not · doesn't tell you · never · shouldn't. ⚠️ **martinfowler.com 은 잘 열렸다**(`technical-debt` 사이클에서 확인) |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| ⭐ `go` 의 동시성 절 (보강) | **`go` 문서가 스스로 "가장 큰 구멍"이라고 적었다** — 고루틴·채널·`select`·CSP 를 한 줄도 못 썼다. ⚠️ **셈이 없어서**다(`고루틴` 1건, `채널` 은 채널톡 오염으로 사용 불가). ⭐ `asyncio` 와 겹치지도 않는다(그쪽에 `Go` 0회). | **1차 자료를 찾으면 바로** — `Effective Go` 의 동시성 절, 또는 `Go Blog` 의 "Share Memory By Communicating". ⭐ **셈 없이 쓰는 것이 허용되는 드문 경우**다(언어의 핵심 기능이고 1차 자료가 확실하다). 보강 사이클(사다리 4순위)로 처리한다. |
| 시맨틱 버저닝 (`semantic-versioning`) | **셈에서 3건(모집중 1)** — `시맨틱 버저닝\|semantic version\|semver\|MAJOR.MINOR` 로 이름을 대는 공고가 사실상 없다. `changeset\|Conventional Commits\|semantic-release` 까지 넓혀도 10건(모집중 2). `api-versioning` 이 끊긴 링크로 남겼으나 **근거가 이 백과사전 최저 수준**이라 지금 쓰면 '규격 요약본'이 된다. | **`monorepo` 를 쓴 뒤** — 그 문서가 `fixed vs independent` 버저닝을 다루면서 이 낱말을 다시 가리킬 것이다. 또는 공고에서 `semver` 를 이름으로 대는 곳이 10건을 넘으면. |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
