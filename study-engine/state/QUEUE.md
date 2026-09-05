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



| 계약 테스트 | `contract-testing` | **`data-contract` 이 끊긴 링크로 남긴 자리**다 — 데이터가 아니라 **API 호출**에 대해 같은 일(깨는 변경을 배포 전에 잡기)을 하는 쪽. 두 문서가 짝이 되면 서로의 경계가 분명해진다(`olap`↔`db-index`, `sse`↔`grpc` 와 같은 형태). ⚠️ **근거가 얇다 — 6건(모집중 4)이고 그중 1건은 오탐이다.** 진짜는 코그넥스 `CI/CD, contract test, integration test, load test, rollback strategy에 대한 경험`, Bill.com `Experience with contract testing (Pact or similar) and visual regression testing`, Coursera `API testing frameworks (Postman, REST-assured, Pact)`, 와이즈플러스(마감) `API Contract Test 또는 Simulator 개발 경험`. ⚠️⚠️ **`PACT` 는 학회 이름이기도 하다** — 피플뱅크 공고의 `ASPLOS, HPDC, ISCA, Micro, **PACT**, PLDI, PPoPP, SC` 가 그것이다(제품명 충돌의 새 사례). **얇은 근거는 `rebac` 처럼 왜 얇은지를 숫자로 적고 쓴다.** 축: ①**통합 테스트로는 왜 안 되나**(둘 다 띄워야 하고 느리고 남의 배포에 깨진다) ②**소비자가 계약을 쓴다**(consumer-driven — 생산자가 아니라 쓰는 쪽이 무엇을 기대하는지 적는다) ③**계약을 어디에 두나**(브로커 — 양쪽 CI 가 같은 것을 본다) ④⭐**`can-i-deploy`**(배포 전에 '지금 나가도 되나'를 기계에 물어본다 — 이 낱말의 가장 또렷한 실물) ⑤**계약 테스트가 대체하지 못하는 것**(성능·인증·실제 데이터 → `load-test`) | ⭐ **1차 자료** — **Pact 공식 문서(docs.pact.io)** 가 공개 HTML 이고 **"contract testing is not..."** 처럼 **스스로 경계를 그은 페이지**를 갖고 있다(`policy-engine`·`data-migration`·`rebac` 에서 세 번 통한 '제품이 스스로 그은 선'). **Pact Broker 와 `can-i-deploy` 문서**도 같은 사이트. ⚠️ **`data-contract` 와 겹치지 않게 — 데이터 스키마는 그쪽, 여기는 API 호출** |
| 데이터 유출 방지 (DLP) | `dlp` | **`siem` 이 남긴 자리** — 그 문서가 `EDR·WAF·SIEM·DLP` 묶음을 인용하면서 네 칸 중 셋만 백과사전에 있다고 짚었다(소스·차단·모아보기는 있고 **유출 방지만 없다**). 그리고 `audit-log` 의 '응답 본문까지 남기면 감사 로그가 개인정보 DB 사본이 된다', `abac` 의 'PII 마스킹', `network-separation` 의 '망분리'가 전부 **데이터가 밖으로 나가는 문제**를 언급만 하고 지나갔다. 근거: 바로팜 `EDR, WAF, SIEM, DLP 등 주요 보안 솔루션 운영 경험`, 버킷플레이스 `Endpoint 보안을 고도화하여 EDR, DLP 기반 단말 위협 탐지·차단 체계 구축`, 프라이빗테크놀로지 `제로트러스트, ZTNA, SASE, SWG, NAC, VPN, PAM, DLP, SIEM/SOAR`, 브레인크루 `PII 가명화`. ⚠️ **`DLP` 는 세 글자다** — `OPA`(이웃이 좁아 안전) vs `DMS`(넓어 오탐)의 판별을 먼저 한다. 그리고 ⚠️ **`유출` 은 한국어에서 넓다**(정보 유출 사고 기사·개인정보 유출 대응이 섞인다 — `감사`·`관제` 규칙). 축: ①**나가는 길이 몇 개인지 세어 보면 막을 수 없다는 걸 안다**(메일·USB·클립보드·API·스크린샷·사진) ②**분류가 먼저다**(무엇이 민감한지 모르면 아무것도 못 막는다 → `data-governance`) ③**탐지 대 차단** (오탐이 곧 업무 중단 → `siem` 의 그 거래) ④**가명화·마스킹은 유출 자체를 막는 게 아니라 피해를 줄인다** (→ `abac` 의 열 마스크) ⑤**내부자가 전제다**(권한이 있는 사람이 가져간다 → `rebac`·`audit-log`) | ⭐ **1차 자료 후보** — **Google Cloud Sensitive Data Protection(구 DLP API) 문서**의 **infoType 탐지기 목록과 de-identification 기법(마스킹·토큰화·버킷팅·날짜 시프팅)** 이 **분류와 처리가 전부 스키마로 노출된 자리**이고, **AWS Macie** 도 후보. ⚠️ 국내 개인정보보호법 조문은 **`network-separation` 의 규정 처리 규칙**(확인한 것/못 한 것을 나눠 적기)을 따를 것 |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| (없음) | 2026-09-04 후보 조사에서 Kubernetes·BigDecimal 을 **대기로 올렸다** | |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
