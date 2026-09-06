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



| 리팩터링 | `refactoring` | ⭐⭐⭐ **층을 바꾼다** — 설계/아키텍처를 세 사이클 연속 했다(`microservices`→`bounded-context`→`hexagonal-architecture`). ⭐⭐⭐ **그리고 사슬을 닫는다**: `testing`("rarely hesitant to change some code") → `technical-debt`(이자 = 바꿀 때 드는 추가 노력) → `code-review` → **`refactoring`**. 넷 다 **"움직일 수 있는가"** 를 묻는데, **실제로 움직이는 행위가 여기**다. ⭐ 직전 문서가 **"의존성 방향은 매 커밋마다 지켜야 한다"** 로 끝난 것과도 이어진다. ⭐⭐ **셈(2026-09-06): `리팩[터토]링|refactor` 753건(모집중 256)** — ⚠️ **모집중 34%로 정상.** 관련: `레거시` 766 · `부채` 227 · `코드 품질`·`유지보수` **(⚠️ 미확인 — 세라)**. ⭐⭐⭐ **축 후보: "원저자가 이 낱말이 오용되는 것에 이름을 붙여 항의했다."** Fowler 는 별도 bliki **`RefactoringMalapropism`** 에서 **사람들이 코드를 망가뜨려 놓고 "리팩터링했다"고 말하는 것**을 지적한다 — ⭐ **이 백과사전의 "스스로 그은 선" 계보에 새 형태**다: 제품도 주창자도 아니라 **낱말의 뜻 자체를 지키려는 선**. ⭐⭐ **정의가 축을 준다** — "a **disciplined technique** for restructuring an existing body of code, **altering its internal structure without changing its external behavior**". ⚠️ **"외부 동작을 바꾸지 않는다"가 전부**이고, 그러려면 **테스트가 전제**다(→ `testing` 과 직접 이어진다). 축 넷: ①⭐⭐⭐**오용**(`RefactoringMalapropism` — 무엇이 리팩터링이 아닌가) ②⭐⭐**전제는 테스트**(외부 동작이 안 바뀌었음을 무엇으로 아나) ③⭐⭐**언제 하나**(Fowler 의 "세 번의 법칙"·"기능 추가 전에 준비" — ⚠️ 원문 확인) ④⚠️**`레거시` 766건과의 관계**. ⚠️ **겹침 확인 필수**: `technical-debt`(이자 개념) · `testing` · `code-review` · `migration`(대규모 재작성과 다른 점) · `hexagonal-architecture`. ⚠️ **aliases 확인 필요**. ⭐⭐⭐ **1차 자료를 여는 그 호출에 실패 사례 검색을 함께 넣는다** — 직전 사이클에서 처음 지켰다(결과는 2차 자료뿐이었고 그 사실을 기록했다). | ⭐⭐⭐ **1차 자료: martinfowler.com/bliki/RefactoringMalapropism.html** + **refactoring.com** 의 정의 페이지(What is Refactoring / When should we refactor). ⭐ martinfowler.com 은 **세 사이클 연속 잘 열렸다**. ⭐ **부정어 먼저**: not refactoring · shouldn't · don't · broke · without changing · malapropism. ⚠️ **못 열면 축을 바꾼다** — 대안: `문서화` **2037건** 또는 `성능 최적화` **2725건**(둘 다 층이 통째로 비어 있다) |
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
