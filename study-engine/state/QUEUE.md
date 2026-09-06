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



| GitHub Actions | `github-actions` | ⭐ **`redis` 가 끊긴 링크를 안 남겼다(`kafka` 는 이미 있었다) — 또 사슬이 끊겨 층을 바꾼 자리**(데이터 → CI/배포). ⭐⭐⭐ **셈(2026-09-06): `CI/CD` 2795건(모집중 1168)** — 이 백과사전이 만난 낱말 중 손꼽히게 크다. `GitHub Actions` **727건(모집중 322)** · `Jenkins` 669 · `공급망|supply chain|SBOM` **227** · `시크릿|Vault` 123 · `셀프호스트 러너` **38**. ⚠️⚠️ **낱말을 `CI/CD` 로 잡으면 요약본이 된다** — 그리고 `secrets` 문서가 이미 `시크릿` alias 를 갖고 있다. ⭐ **그러니 `GitHub Actions` 를 낱말로 하고 축을 좁힌다: "우리 비밀을 들고 남의 코드를 실행하는 자리."** **웹은 우리 서버, 앱은 남의 스토어**(`android`·`ios`)였다면 — **CI 는 우리 비밀이 남의 기계에서 남의 코드와 함께 도는 곳**이다. ⚠️ **먼저 할 일: `secrets` 문서를 열어 무엇을 안 다뤘나 센다**(`redis` 사이클에서 `caching`·`distributed-lock` 에 한 것처럼 — `pull_request_target`·`서드파티 액션`·`러너`·`SHA 고정` 같은 낱말을 세어 본다). ⚠️ **축이 겹치면 미룬다.** 축 넷: ①⭐⭐**포크에서 온 PR 이 우리 비밀에 닿는 자리**(`pull_request_target`) ②⭐⭐**서드파티 액션은 남의 코드가 우리 CI 안에서 도는 것**(태그는 옮겨 달 수 있으니 커밋 SHA 로 고정) ③**셀프호스트 러너와 public 레포**(⭐ GitHub 이 직접 권하지 않는다고 적는 자리) ④**권한의 기본값**(토큰이 기본으로 무엇을 할 수 있나). **이웃**: `secrets`(정면 이웃 — 축 확인 필수) · `feature-flag` · `observability` · `android`/`ios`(배포의 다른 끝). | ⭐⭐⭐ **1차 자료: GitHub Docs `Security hardening for GitHub Actions`** — **플랫폼이 자기 기능의 위험을 스스로 경고하는 자리**다. ⭐ 그 문서에는 **Warning 블록이 여럿** 있고(특히 `pull_request_target`), ⭐⭐ **"셀프호스트 러너를 public 레포에 쓰지 말라"** 부류의 **권하지 않는다는 문장**이 있다 — `kotlin`("impractical")·`redis`("we discourage it")에서 모은 그 형태. **부정어 먼저 검색**: Warning·Danger·do not·should not·recommend that you do not·can be dangerous·untrusted. ⚠️ 그리고 **`redis` 에서 배운 대로, 인용한 경고가 "무엇을 못 하게 하나"가 아니라 "무엇이 일어날 수 있나"를 적는지** 본다 |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| 시맨틱 버저닝 (`semantic-versioning`) | **셈에서 3건(모집중 1)** — `시맨틱 버저닝\|semantic version\|semver\|MAJOR.MINOR` 로 이름을 대는 공고가 사실상 없다. `changeset\|Conventional Commits\|semantic-release` 까지 넓혀도 10건(모집중 2). `api-versioning` 이 끊긴 링크로 남겼으나 **근거가 이 백과사전 최저 수준**이라 지금 쓰면 '규격 요약본'이 된다. | **`monorepo` 를 쓴 뒤** — 그 문서가 `fixed vs independent` 버저닝을 다루면서 이 낱말을 다시 가리킬 것이다. 또는 공고에서 `semver` 를 이름으로 대는 곳이 10건을 넘으면. |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
