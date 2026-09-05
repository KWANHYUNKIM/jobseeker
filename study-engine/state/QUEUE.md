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



| SIEM (보안 로그 분석·위협 탐지) | `siem` | **`audit-log` 이 끊긴 링크로 남긴 자리**다 — 그 문서의 경계 2번(**남기기만 하고 안 본다**)이 곧 이 낱말이다. 공고가 '남기는 능력'이 아니라 **분석하는 능력**을 요구한다: 마이리얼트립 `보안 로그, 클라우드 감사 로그 등을 분석하여 위협을 탐지한 경험`, 유모스원 `로그 분석·모니터링(CloudTrail, SIEM) 체계 구축`, 서치독 `Detective Controls (탐지 통제) — GuardDuty, Security Hub, AWS Config, CloudTrail, Security Lake의 조직 단위 통합 운영`, 미리디 `OpenSearch SIEM`, 와탭랩스 `Siem 보안 로그 모니터링 사용 경험`. ⚠️⚠️ **`관제`로 세면 안 된다** — 1002건이 나오는데 **물류 관제·영상 관제·로봇 관제**가 대부분이다(`audit-log`의 '감사' 87% 오탐과 같은 종류, 이번엔 더 심하다). 좁혀도 640건(모집중 214)이라 **`SIEM|Splunk|Security Hub|GuardDuty|Wazuh|SOAR|OpenSearch SIEM` 처럼 제품 이름 위주로 세고 문장을 읽는다.** 축: ①**로그를 모으는 것과 보는 것은 다른 시스템이다**(→ `observability` 의 짝 — 그쪽은 우리가 고장 났나, 여기는 누가 공격하나) ②**상관분석**(한 줄로는 아무 뜻도 없고 여러 줄을 이어야 사건이 된다) ③**오탐이 본질이다**(경보가 많으면 아무도 안 본다 → `oncall` 의 그 대가) ④**정규화**(제품마다 다른 로그 형식을 하나로 — → `data-contract` 와 같은 문제) ⑤**보관 비용과 검색 가능성의 거래**(뜨거운/차가운 저장) | ⭐ **1차 자료 후보** — **AWS Security Hub 문서**(findings 형식 **ASFF: AWS Security Finding Format** — **정규화의 실물이 스키마로 노출된 자리**)와 **GuardDuty finding types 문서**(탐지 유형의 분류 = **분류가 곧 결정인 표**), 그리고 **OpenSearch Security Analytics 문서**(탐지 규칙·Sigma). ⚠️ **`observability` 와 겹치지 않게 — 로그 수집·지표는 그쪽, 여기는 '적대적 행위를 찾는 것'** |
| 계약 테스트 | `contract-testing` | **`data-contract` 이 끊긴 링크로 남긴 자리**다 — 데이터가 아니라 **API 호출**에 대해 같은 일(깨는 변경을 배포 전에 잡기)을 하는 쪽. 두 문서가 짝이 되면 서로의 경계가 분명해진다(`olap`↔`db-index`, `sse`↔`grpc` 와 같은 형태). ⚠️ **근거가 얇다 — 6건(모집중 4)이고 그중 1건은 오탐이다.** 진짜는 코그넥스 `CI/CD, contract test, integration test, load test, rollback strategy에 대한 경험`, Bill.com `Experience with contract testing (Pact or similar) and visual regression testing`, Coursera `API testing frameworks (Postman, REST-assured, Pact)`, 와이즈플러스(마감) `API Contract Test 또는 Simulator 개발 경험`. ⚠️⚠️ **`PACT` 는 학회 이름이기도 하다** — 피플뱅크 공고의 `ASPLOS, HPDC, ISCA, Micro, **PACT**, PLDI, PPoPP, SC` 가 그것이다(제품명 충돌의 새 사례). **얇은 근거는 `rebac` 처럼 왜 얇은지를 숫자로 적고 쓴다.** 축: ①**통합 테스트로는 왜 안 되나**(둘 다 띄워야 하고 느리고 남의 배포에 깨진다) ②**소비자가 계약을 쓴다**(consumer-driven — 생산자가 아니라 쓰는 쪽이 무엇을 기대하는지 적는다) ③**계약을 어디에 두나**(브로커 — 양쪽 CI 가 같은 것을 본다) ④⭐**`can-i-deploy`**(배포 전에 '지금 나가도 되나'를 기계에 물어본다 — 이 낱말의 가장 또렷한 실물) ⑤**계약 테스트가 대체하지 못하는 것**(성능·인증·실제 데이터 → `load-test`) | ⭐ **1차 자료** — **Pact 공식 문서(docs.pact.io)** 가 공개 HTML 이고 **"contract testing is not..."** 처럼 **스스로 경계를 그은 페이지**를 갖고 있다(`policy-engine`·`data-migration`·`rebac` 에서 세 번 통한 '제품이 스스로 그은 선'). **Pact Broker 와 `can-i-deploy` 문서**도 같은 사이트. ⚠️ **`data-contract` 와 겹치지 않게 — 데이터 스키마는 그쪽, 여기는 API 호출** |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| (없음) | 2026-09-04 후보 조사에서 Kubernetes·BigDecimal 을 **대기로 올렸다** | |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
