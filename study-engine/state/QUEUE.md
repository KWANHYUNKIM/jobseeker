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



| TypeScript | `typescript` | ⭐ **`github-actions` 가 끊긴 링크를 안 남겼다 — 세 번째로 층을 바꾼 자리**(CI → 언어/프론트엔드). ⭐⭐⭐ **셈(2026-09-06): `TypeScript|타입스크립트` 2678건(모집중 1034)** — `CI/CD` 2795 에 버금간다. ⚠️⚠️ **그런데 `타입 안전|타입 안정성` 26건 · `any 타입|strict` 3건 · `제네릭` 19건** — ⭐ **2678 대 26, 열째 형태다.** ⚠️ **`aliases` 확인 완료**: `TypeScript`·`타입`·`any`·`정적 타입`·`zod` 어느 것도 없다. ⚠️⚠️ **그대로 쓰면 문법 요약본이 된다.** ⭐⭐⭐ **축을 좁힌다: "타입이 맞다는 건 증명됐다는 뜻이 아니다."** ⭐⭐ **1차 자료가 그 축을 직접 준다** — TypeScript 의 **Design Goals** 문서에 **Non-goals** 목록이 있고 거기 이렇게 적혀 있다: **"Apply a sound or 'provably correct' type system. Instead, strike a balance between correctness and productivity."** **건전성(soundness)이 설계 목표가 아니라고 스스로 못 박는다** — `kotlin`("impractical")·`redis`("we discourage it")·`github-actions`("almost never")에 이은 **"제품이 스스로 그은 선"의 가장 순수한 형태**: **자기 비목표를 목록으로 적어 둔다.** ⚠️ **`kotlin` 과 겹치지 않게 조심한다** — 저쪽은 "**다른 언어와 만나는 자리**에서 보장이 내려간다"이고, 여기는 ⭐ **"컴파일이 끝나면 타입이 아예 없어진다"**(런타임 경계 — API 응답·`JSON.parse`·외부 입력). 축 넷: ①⭐⭐**비목표 목록**(왜 건전하지 않게 만들었나 — 생산성과의 맞바꿈) ②⭐⭐⭐**타입은 지워진다**(런타임에 아무것도 안 남는다 → `런타임 검증|zod` **53건**이 그 빈자리를 메우는 도구) ③**`any` 와 단언이 뚫는 구멍**(⚠️ `strict` 를 이름으로 대는 공고 **3건**) ④**경계에서만 검증한다**(→ `rest`·`graphql` 의 응답, `authz` 의 입력). **이웃**: `kotlin`(축 다름 — 확인 필수) · `javascript`(**2397건, 문서 없음** — 다음 후보) · `rest`/`graphql`(응답이 들어오는 경계) · `authz`. | ⭐⭐⭐ **1차 자료: TypeScript 공식 위키의 `TypeScript Design Goals`**(Non-goals 목록이 축의 심장) + **핸드북의 타입 소거·`any`·타입 단언** 관련 절. ⭐ **부정어 먼저**: not sound · Non-goals · does not · no guarantee · erased · at runtime · escape hatch. ⚠️ **`market` 은 `TypeScript`(1006건 · 14.0% · 층 "언어" · React 67.8% 동반)를 그대로 옮기고, 본문 셈 2678 과 함께 적는다** |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| 시맨틱 버저닝 (`semantic-versioning`) | **셈에서 3건(모집중 1)** — `시맨틱 버저닝\|semantic version\|semver\|MAJOR.MINOR` 로 이름을 대는 공고가 사실상 없다. `changeset\|Conventional Commits\|semantic-release` 까지 넓혀도 10건(모집중 2). `api-versioning` 이 끊긴 링크로 남겼으나 **근거가 이 백과사전 최저 수준**이라 지금 쓰면 '규격 요약본'이 된다. | **`monorepo` 를 쓴 뒤** — 그 문서가 `fixed vs independent` 버저닝을 다루면서 이 낱말을 다시 가리킬 것이다. 또는 공고에서 `semver` 를 이름으로 대는 곳이 10건을 넘으면. |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
