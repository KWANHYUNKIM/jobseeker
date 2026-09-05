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



| 복제 (레플리케이션) | `replication` | **`causal-consistency` 가 "다른 저장소에서 자기 쓰기 읽기를 어떻게 만드나"를 확인 못 해 남긴 자리**이고, `consistency-model`·`consensus`·`sharding` 이 전부 **복제본이 있다는 것을 전제**하고 쓰였다 — 그 전제 자체를 다룬 문서가 없다. **48건(모집중 33)**: 사카드코리아(`Solid understanding of distributed systems - partitioning, replication, consistency trade-offs, failure modes`), 예스폼(`Replication 구성 및 운영 경험`, `이관 도구(AWS DMS, mysqldump/mydumper, replication 등)`), 메디인테크(`마스터-슬레이브 시스템 개발 경험`). 축: ①**왜 복제하나 — 목적이 셋이고 서로 다르다**(가용성 · 읽기 확장 · 지역 분산) ②**동기냐 비동기냐**(쓰기가 기다리나 — `consensus` 의 과반이 이 축의 한 점) ③**복제 지연이 곧 앞 문서들의 증상**(`consistency-model`·`causal-consistency` 가 다룬 것의 원인) ④**장애 조치(failover)와 데이터 손실**(비동기면 못 따라온 만큼 잃는다 → RPO) ⑤**읽기를 복제본으로 보내면 자기 쓰기 읽기가 깨진다**(→ `causal-consistency` 로 되돌아온다) | ⭐ **1차 자료가 확실하다** — **PostgreSQL 의 복제 문서**(동기 복제의 `synchronous_commit` 수준)나 **MySQL 의 복제 문서**가 **설정으로 노출된 자리**다. `mdm`·`consistency-model`·`data-governance`·`causal-consistency` 에서 **네 번 통한 방법** 그대로. ⚠️ **`sharding` 과 겹치지 않게 — 나누는 것은 그쪽, 베끼는 것은 여기** |
| 정책 엔진 (OPA) | `policy-engine` | **`abac` 이 "규칙을 어디에 두느냐가 진짜 주제"라 하고 범위 밖으로 둔 자리**다. 42dot 공고가 **`RBAC, ABAC, ReBAC, policy engine, permission model 중 하나 이상`** 이라 적어 **모델 이름들과 나란히** 요구한다 — 즉 **모델을 고르는 것과 그것을 어디서 평가하느냐는 다른 결정**이다. ⚠️ **건수를 먼저 센다**(`OPA|Open Policy Agent|policy engine|Rego|정책 엔진|Cedar`). 축: ①**권한 규칙이 코드 안 `if` 문에 흩어지는 문제**에서 시작한다 ②**결정과 실행의 분리**(PDP/PEP — 물어보는 쪽과 판단하는 쪽) ③**정책을 데이터처럼 배포한다**(버전 관리·리뷰·테스트 → `iac`) ④**어디서 평가하나**(사이드카·라이브러리·중앙 서비스 — 지연과 가용성이 갈린다) ⑤**정책도 테스트가 필요하다**(규칙이 늘면 왜 막혔는지 모른다 → `abac` 의 그 대가) | ⭐ **1차 자료가 확실하다** — **OPA 공식 문서**(Rego, PDP/PEP 구분, `opa test`)가 공개 HTML 이고 **AWS Cedar** 도 후보다. `mdm`·`consistency-model`·`data-governance`·`causal-consistency`·`abac` 에서 **다섯 번 통한 방법** 그대로. ⚠️ **`rbac`·`abac` 과 겹치지 않게 — 모델은 그쪽, 여기는 "규칙을 어디서 평가하나"** |
## 미룸

| 낱말 | 왜 미뤘나 | 언제 다시 볼까 |
|---|---|---|
| (없음) | 2026-09-04 후보 조사에서 Kubernetes·BigDecimal 을 **대기로 올렸다** | |

## 재시도 안 함

| 낱말 | 왜 | 다시 꺼낼 조건 |
|---|---|---|
| (없음) | | |
