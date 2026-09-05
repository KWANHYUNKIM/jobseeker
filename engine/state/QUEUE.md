# 대기열

한 사이클에 한 회사만 판다. 맨 위 회사가 `done` 이 되기 전에는 아래로 내려가지 않는다.
회사를 끝내면 `## 대기` 표에서 지우고 `## 완료` 로 옮긴다.

> **표 형식을 지킨다.** `validate.py --gaps` 가 이 표의 행 수를 세어 큐 잔량을 판단하고,
> 잔량이 목표(3)보다 적으면 후보 조사 사이클을 띄운다. 산문으로 적으면 세지 못한다.
> **⚠️ 행을 추가할 때는 앞 행 끝의 줄바꿈을 확인한다** — 두 번(Canva·Grafana) 앞 행에 붙어
> 큐 잔량이 잘못 세어졌다. 고친 뒤 `sed -n '/^## 대기/,/^### 확인/p' engine/state/QUEUE.md | grep -c '^| \*\*'` 로 센다.
> `## 진행 중

## 보류` 와 `## 완료` 는 세지 않는다 — 팔 수 있는 것만 큐다.

## 진행 중

| 회사 | 국가·분류 | 상태 |
|---|---|---|
| **Ramp** | US · 핀테크(지출 관리) | 프로파일 완료 · 도메인 3(지출이 되는지를 그래프가 판정한다[tech 4] / 모델 배포를 넉 달에서 5분으로 줄인다[tech 3] / 코딩 에이전트를 사서 쓰지 않고 직접 만든다[tech 4]) · **기능 2**(workflows-as-graphs-not-code / reproducibility-is-a-data-promise) |

## 대기

| 회사 | 국가·분류 | 1차 자료 | 접근 | 왜 이 회사인가 |
|---|---|---|---|---|


### 확인해 둔 후보 (아직 검증 안 됨)

- **2026-09-06 열일곱 번째 후보 조사 — 세 곳을 올렸고 그중 둘은 앞선 판정을 뒤집은 것이다.**
  - **✅ ClickHouse (❌ → ✅)** — 앞 조사에서 `일반론 교육 글` 이라 떨어뜨리며 **`ai-first-data-warehouse` 는 결이 다를 수 있다** 고 주소까지 남겨 뒀다. **그 메모가 맞았다.**
  - **✅ Duolingo (❌ → ✅)** — **두 편을 읽고 판정했는데 그것으로 부족했다.** `⏳ 안 읽은 두 편` 이라 적어 둔 쪽에 **버린 대안과 대가와 사고가 다 있었다.** ⚠️ **`두 편을 읽었으니 충분하다` 가 이번에 틀렸다** — Temporal 을 한 편 덕에 되살린 것과 같은 모양이다.
  - **✅ Ramp** — 새 이름. ⚠️ **`ramp.com/blog/engineering` 을 추측했다가 404 를 받았다.** 검색으로 `engineering.ramp.com` 을 찾았다 — **주소를 추측하지 않는다는 규칙이 회사 블로그에도 그대로 적용된다.**
  - **❌ Capital One** — `dynamodb-streams-lambda-pattern-best-practices` 가 **404** 다. 두 경로 모두에서 사라진 것으로 보인다. **이로써 Capital One 은 세 번 확인하고 세 번 미달이다 — 재시도 안 함으로 옮길 만하다.**
  - ⚠️ **세 곳이 모두 `사내 AI 에이전트` 축이라 서로 겹친다.** 보통은 겹침을 피하지만 **이번에는 그것이 값이다** — Sentry(AI 가 PR 까지 열고 **병합은 사람이**, 매일 밤 에이전트를 심문) · Duolingo(테스트 생성, **리뷰가 병목**, 프로덕션 파일을 고친 사고) · Ramp(**병합 PR 의 30%**, 동기화 전 편집 차단) · ClickHouse(**분석의 70%**, 나머지 30% 는 일부러 사람에게). **`사내 AI 에이전트를 어디까지 믿을 것인가` 에 네 회사가 각각 다른 선을 그었다 — 비교 문서의 재료다.**

- **2026-09-06 열여섯 번째 후보 조사 — 두 곳을 올렸다(Fastly · Monzo). 목표 3곳 중 2곳이다.**
  - **✅ Fastly** — 위 대기 표로 올렸다. ⚠️ **남겨 둔 이름이 세 사이클 만에 값을 했다.** 첫 화면(보안 리서치·제품)으로는 떨어졌을 텐데 **검색으로 심층 글을 찾아 본문을 열었다** — `building-fast-and-reliable-purging-system`. **버린 대안·대가·수치가 셋 다 있다.**
  - **✅ Monzo** — 위 대기 표로 올렸다. **두 편을 열어 둘 다 기준을 넘었다**(데이터 메시 글 · 2019-07-29 장애 회고). ⚠️ **데이터 메시 글에는 `무엇을 잃었나` 가 명시적이지 않다**(전제와 투자만 적는다). **대가는 장애 회고 쪽에 있다** — 한 회사 안에서 글의 결이 갈리는 일곱 번째 사례다.
  - **❌ Duolingo (두 편을 열고 판정)** — ⚠️ **교육 축이 비어 있어 아까운 후보였다.** `reduce-cpu-usage-97-percent`(2026-06-22)는 자기 운영 시스템이 맞고 수치도 좋다(피크 CPU **포화 → 3.5%** · 파드 **32 → 8**, 이전 기준 18). 원인도 구체적이다 — SMS 요청마다 `requests.Session()` 을 새로 만들어 매번 TCP·TLS 를 다시 맺었고, 워커 스레드 10개가 전부 연결 수립에서 막혔다. **⚠️ 그런데 두 편 다 버린 대안이 없다.** `production-ready-ai-agent-platform`(2026-08-04)도 사내 플랫폼이 맞지만 **거절한 대안이 없고** 대가는 하나뿐이며(*"deterministic graders are the foundation"*) 수치도 **몇 주 → 약 10분** 하나다. **고친 이야기는 있는데 갈림길이 없다.** ⏳ **완전히 닫지는 않는다** — `ai-ios-unit-test-generation-pipeline` · `aislackbot` 은 안 읽었다.
  - **❌ The New York Times** — `open.nytimes.com` 을 **WebFetch 가 받지 못한다**(`unable to fetch`). **NYT Open 은 Medium 기반**이라 이미 막힌 경로와 같은 결로 보인다(추정). **뉴스·미디어 축은 여전히 비어 있다.**
  - **⏳ 남은 실마리** — ClickHouse 의 `ai-first-data-warehouse`(자기 시스템 글일 수 있다) · Capital One 의 `dynamodb-streams-lambda-pattern-best-practices`(안 읽었다).

- **2026-09-06 열다섯 번째 후보 조사 — HashiCorp 판정을 끝내고(❌) Wise 를 올렸다.**
  - **❌ HashiCorp (판정 확정)** — ⚠️ **이번엔 `첫 화면으로 판정하지 않는다` 를 끝까지 적용했다.**
    검색으로 심층 글을 찾았는데 나오는 것이 **조직·문화·커리어·연말 회고**다
    (원격 팀 하이퍼그로스 · 접근성 설계 · 커리어 전환 · 2025 연말 정리).
    **자기 시스템의 설계 회고가 안 나온다.** ⚠️ **절차를 밟았고 결과가 같았다 —
    그래서 이 판정은 앞의 것들과 달리 근거가 단단하다.**
  - **✅ Wise** — 위 대기 표로 올렸다. ⚠️ **Medium 이라 목록은 못 보고 검색으로 글 주소를 찾아
    브라우저로 열었다.** 세 사이클 전에 굳힌 방법이 그대로 통했다.
  - **⏳ 아직 안 두드린 것** — **Fastly**(CDN, Cloudflare 와 겹침).

- **2026-09-06 열네 번째 후보 조사 — 새 이름에서 하나를 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  - **✅ Sentry** — 위 대기 표로 올렸다. **앞 사이클에서 URL 을 확보해 둔 덕에 바로 본문을 열었다.**
  - **⏳ HashiCorp — 판정 보류.** `hashicorp.com/en/blog` 는 열리고 최신도 2026-09-03 인데
    **첫 화면이 제품 발표·기능 업데이트**다(Boundary·Vault·HCP 관련). ⚠️ **그런데 첫 화면으로
    판정하지 않는다는 규칙이 있고, 이번엔 심층 글 검색을 안 했다.** **다음 조사에서
    검색으로 심층 글을 찾아 본문을 열고 결론을 낸다** — 인프라 도구 벤더는 이 엔진에 없는 축이다.
  - **⏳ 아직 안 두드린 것** — **Wise · Fastly.**

- **2026-09-06 열세 번째 후보 조사 — 남겨 둔 한 편으로 Temporal 을 되살렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  - **✅ Temporal** — 위 대기 표로 올렸다. **앞 사이클에서 `버린 대안도 수치도 없다` 며
    떨어뜨렸는데, 그때 `workflow-engine-principles 는 안 읽었다` 고 남겨 둔 것이 맞았다.**
    ⚠️ **한 회사 안에서 글의 결이 갈리는 다섯 번째 사례다**(Nubank · Bolt · Booking.com ·
    Rightmove 에 이어) — 같은 블로그에서 **제품 홍보 글과 설계 원칙 글이 완전히 다르다.**
  - **⏳ Sentry — URL 을 확보했다. 다음 조사에서 본문을 연다.**
    `blog.sentry.io` 목록은 열리고 **슬러그를 추측하면 404 지만 목록에서 URL 을 받으면 된다.**
    자체 시스템으로 보이는 것 둘: `automated-debugging-workflow-sentry`(2026-08-06,
    **사내 디버깅 자동화의 기술 구조**) · `metrics-caught-ai-size-estimate`(2026-09-01,
    **애플리케이션 지표가 자기 도구의 버그를 잡아낸 이야기**).
    ⚠️ 다만 축이 관측·오류 추적이라 **Honeycomb·Datadog·Grafana 와 겹친다.**

- **2026-09-06 열두 번째 후보 조사 — 새 이름으로 돌아와 하나를 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **의심 목록이 끝나 미리 골라 둔 새 이름들을 두드렸다.**
  - **✅ Honeycomb** — 위 대기 표로 올렸다. ⚠️ **첫 화면(AI·조직 글)만 봤으면 떨어뜨렸을 것이다.**
  - **❌ Temporal** — `temporal.io/blog` 는 열리고 최신도 2026-09-04 인데 **첫 화면이 파트너십·
    제품 발표**다. 첫 화면으로 판정하지 않는다는 규칙대로 **검색으로 심층 글을 찾아 본문을
    열었다** — `higher-throughput-and-lower-latency-temporal-clouds-custom-persistence-layer`.
    **자기 시스템(Temporal Cloud) 이야기가 맞고** 세 기둥이 뚜렷하다(동적 샤딩 · **쓰기 선행
    로그로 여러 갱신을 모아 한 번에 쓰기** · 워크플로 완료 시 이벤트 이력을 객체 저장소로
    옮기는 계층 저장). **시끄러운 이웃 문제**를 푼 것도 밝힌다.
    ⚠️ **그런데 버린 대안이 없고 수치가 없다** — `we saw an immediate impact` 수준이고
    비교 벤치마크·지연 수치가 하나도 없다. **기준(버린 대안·대가·수치 중 둘) 미달이다.**
    ⏳ **다만 `workflow-engine-principles` 는 안 읽었다** — 설계 원칙을 다루는 글이라 결이
    다를 수 있다. **내구성 있는 실행 엔진은 이 엔진에 없는 축이라 다시 볼 값이 있다.**

- **2026-09-06 열한 번째 후보 조사 — Capital One 판정을 끝냈다(❌ 유지). 큐는 그대로 0/3 이다.**
  **⚠️ 이번엔 세 편을 확인했다** — 앞선 판정이 첫 화면만 본 것이었기 때문이다.
  - **❌ Capital One (판정 유지, 근거는 훨씬 단단해졌다)**
    - `optimizing-opa-performance`(2026-07-06) — **수치는 아주 좋다**(쿼리 평가 **26초 → 5ms** ·
      실행 시간 98% 감소 · 파일 **46MB → 20MB**). **⚠️ 그런데 자기 시스템이 아니다** —
      공개 EPSS CSV 를 내려받아 직접 파서를 만든 **가상 사례**다.
    - `transforming-vulnerability-management-at-enterprise-scale`(2026-07-27) —
      **이건 자기 시스템이 맞다**(디렉터·MVP 가 저자이고 `we built`·`our strategy`).
      ⚠️ **그런데 버린 대안도 대가도 없다.** 수치도 정성적이다(`weeks or months to hours` ·
      `hundreds of vulnerabilities ... each month` · 14일 주기 재빌드) — **총 컨테이너 수도
      팀 수도 배포 규모도 없다.** 결이 회고가 아니라 **포부에 가깝다.**
    - **결론** — Capital One 의 글은 **기술적으로 깊을 때는 자기 시스템이 아니고,
      자기 시스템일 때는 대가를 안 적는다.** Ably 와 비슷한 안내서형이지만 Ably 는
      자기 구조를 얹었고 이쪽은 **가상 사례이거나 성과 서사**다.
    - ⏳ **다만 한 편은 안 읽었다** — `dynamodb-streams-lambda-pattern-best-practices`(2025-11).
      검색 요약에는 **핫 샤드로 단일 Lambda 에 몰리는 문제 · 샤드당 순서 보장 · 팬아웃 필요 ·
      비용 대가**가 촘촘하다. **`Best Practices` 제목이라 일반 가이드일 가능성이 높지만
      완전히 닫지는 않는다.**

- **2026-09-06 열 번째 후보 조사 — 의심 목록에서 또 하나를 되살렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **Tailscale 을 되살린 방법(`첫 화면으로 판정하지 않는다`)을 그대로 썼다.**
  - **✅ Ably** — 위 대기 표로 올렸다. **판정이 뒤집혔다.** 첫 화면과 `topic/` 경로가 일반
    교육 글이라 놓쳤는데, **검색으로 심층 글을 찾으니 자기 프로덕션 구조를 다룬다.**
  - **⏳ Capital One — 아직 결론이 안 났다. 경로가 또 갈린다.**
    `capitalone.com/software/blog/` 가 **`capitalonesoftware.com/blog` 로 301** 되는데,
    그것은 **Capital One Software(별도 제품 사업부)** 다. 원래의 `/tech/blog/` 와 다른 곳이다.
    ⚠️ **검색에 걸린 제목들은 결이 좋다** — DynamoDB Streams 의 `sandwich pattern` 을
    **확장 한계·동시성 문제·비용 대가**와 함께 다루는 글, **월 1,000억 건 이상**을 처리하는
    사내 토큰화 엔진, 클라우드 이전 회고(`Always do the hard things first`).
    **다음 후보 조사에서 두 경로의 심층 글 본문을 열어 결론을 낸다.**

- **2026-09-06 아홉 번째 후보 조사 — 떨어뜨렸던 판정을 뒤집어 하나를 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **⚠️ 이번 사이클의 교훈은 앞 사이클의 교훈을 실제로 써먹은 것이다** — Rightmove 에서
  `첫 화면으로 블로그를 판정하지 않는다` 를 배웠고, 그 목록(Capital One · Ably · ClickHouse ·
  Tailscale)을 다시 봤다.
  - **✅ Tailscale** — 위 대기 표로 올렸다. **판정이 뒤집혔다.**
  - **❌ ClickHouse (판정 유지, 근거는 바뀌었다)** — 이번에는 **본문을 열어** 확인했다.
    `updates-in-clickhouse-1-purpose-built-engines` 는 **컬럼 스토어 일반론을 가르치는 글**이고
    수치도 맥락 없이 크다(초당 10억 행 · 1,000배 · PostgreSQL 대비 4,000배 — **벤치마크는
    다음 편에 있다고 미룬다**). 대가를 적기는 한다(백그라운드 머지 이해 필요 · `FINAL` 을 언제
    쓸지 · 인제스트가 무거우면 머지가 밀린다). ⚠️ **`ai-first-data-warehouse` 처럼 자기 시스템을
    다루는 글은 결이 다를 수 있다** — 그 주소로 다시 볼 값이 있다.
  - **❌ Supercell** — The New Stack 기사가 **브라우저로도 뉴스레터 폼만** 온다. **게임 축은
    또 막혔다.** ⚠️ 회사 자체 블로그가 아니라 3자 매체라는 점도 걸린다.
  - **❌ Swiggy** — `bytes.swiggy.com` 이 **브라우저로도 로드되지 않는다**(세 번째 실패).

- **2026-09-06 여덟 번째 후보 조사 — 새 축으로 돌아와 하나를 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **되살릴 목록이 끝나 새 이름을 찾는 조사다.** 노린 축: 인도 배달 · 게임 · 부동산.
  - **✅ Rightmove**(UK · 부동산 포털) — 위 대기 표로 올렸다. **부동산 축 첫 자리다.**
    ⚠️ **첫 화면만 보면 떨어뜨릴 뻔했다** — 최신 3편이 디자인·커리어 글이다.
    **`/category/software-engineering/` 로 들어가야 기술 글이 나온다**(5페이지 분량).
    **카테고리가 있는 블로그는 첫 화면으로 판정하지 않는다** — Capital One·Ably 를 그렇게
    떨어뜨렸는데 같은 실수였을 수 있다.
  - **❌ Swiggy**(IN · 배달) — `bytes.swiggy.com` 이 **두 번 다 응답이 없다**(WebFetch 무출력).
    ⚠️ 브라우저로는 열릴 수 있다. 인도 배달 축이라 값이 있다.
  - **⏳ Supercell**(핀란드 · 게임) — **회사 블로그가 아니라 3자 기사**를 찾았다:
    The New Stack `inside-supercells-minimalist-massive-social-network`(2026-03-14).
    **서버 엔지니어가 직접 이야기한 내용**을 매체가 정리한 것이고 *"a mighty team of two"* 로
    수억 게이머를 잇는 소셜 플랫폼을 만든 이야기다. ⚠️ **WebFetch 로는 본문이 안 온다**
    (뉴스레터 폼만). **브라우저로 다시 볼 값이 있다 — 게임 축이 Roblox 하나뿐이다.**
  - **❌ King**(게임) — 전용 기술 블로그를 못 찾았다.

- **2026-09-06 일곱 번째 후보 조사 — 되살릴 목록을 소진했고 빈손이다.** 큐가 0/3 이라 3순위로 들어왔다.
  **⚠️ 이 사이클의 결과는 후보가 아니라 두 가지 확정이다.**
  - **① Medium 목록은 어떤 경로로도 안 온다.** 홈(`medium.com/<pub>`) · 태그(`/tagged/<t>`) ·
    **아카이브(`/archive` → `/all` 로 리다이렉트)** 를 전부 시도했다. 마지막 것은
    **`No stories found matching these filters`** 를 돌려준다. **개별 글 주소만 열린다** —
    그래서 Medium 계열 후보는 **WebSearch 로 글 주소를 찾을 수 있을 때만** 평가할 수 있다.
  - **② 되살릴 목록이 끝났다.** 남은 셋이 전부 떨어졌다:
    - **❌ Tokopedia** — `learnings-from-migration-to-elastic-search` 를 열었다.
      Medium 발행일이 **2018-07-18** 인데 글 끝에 **`This was posted on Tokopedia tech blog at 2016`**
      이라고 적혀 있다. **10년 전 자료다.** 내용 자체는 좋다(Solr 커밋이 CPU 를 먹어 쿼리 캐시가
      매번 날아갔고, 지연이 3초 → 300ms 로, 중첩 매핑·커스텀 토크나이저의 대가까지 적는다).
      **하지만 이 글이 대표작으로 검색에 잡힌다는 것 자체가 블로그가 멈췄다는 신호다.**
    - **❌ Dream11** — 새 도메인 `blog.dream11engineering.com` 도 **Medium 이고 목록이 비어 온다.**
      `medium.com/dream11tech/archive` 는 `No stories found`. 자체 도메인 `tech.dream11.in` 은
      **298 사이클에 이미 평가해 떨어뜨렸다**(최신 2024-10 · 버린 대안 0 · 대가 사실상 0).
      ⚠️ 3자 자료(AWS·Aerospike 사례)에는 좋은 이야기가 있다 — Redis→Aerospike, Elasticsearch→
      OpenSearch(피크 동시 쿼리 4만, 10초 → 150ms), 저수준 Kafka 컨슈머 자체 개발.
      **회사가 직접 쓴 글의 주소를 찾으면 판정이 뒤집힐 수 있다.**
    - **❌ Meesho** — **회사가 쓴 기술 글의 주소를 하나도 못 찾았다.** 검색에 잡히는 것은
      3자 자료뿐이다(ScyllaDB 2026-04 발표 정리 · Confluent 고객 사례 · 개인 Medium 글).
      ⚠️ 그중 **`monolith → microservices → high scale federated architecture`** 라는 진화와
      ML 플랫폼 1세대의 실패(모델마다 맞춤 피처 로직 · DAG 가 빽빽해짐 · 비용 급증)는 결이 좋다 —
      **회사 발표 자료(ScyllaDB 컨퍼런스)의 주소를 찾으면 다시 볼 값이 있다.**

- **2026-09-06 여섯 번째 후보 조사 — 되살릴 목록에서 하나를 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  - **✅ Trainline** — 위 대기 표로 올렸다. **세 사이클 전 `medium.com/trainline` 로 301 된다며 떨어뜨린 곳**이다.
  - **⚠️ 새로 확인한 제약 — Medium 발행물 홈은 브라우저로도 목록이 안 온다.**
    `medium.com/trainline` 과 `medium.com/tokopedia-engineering` 둘 다 **제목·팔로워 수·탭 이름만** 오고
    글 목록이 비어 있다(JS 렌더링). **개별 글 주소는 전문이 온다** — 그래서 **글 주소를 WebSearch 로 찾아
    브라우저로 여는 것**이 지금의 방법이다. ⚠️ **그 대가로 "최신 글이 언제인지" 를 알 수 없다.**
  - **⏳ Tokopedia** — 목록이 안 와서 접었다. 검색으로 `learnings-from-migration-to-elastic-search`
    (Solr → Elasticsearch) 를 찾았으나 **발행일을 확인하지 못했다.** 다음에 그 주소를 직접 열어 본다.
  - **⏳ 남은 되살릴 목록** — Tokopedia · Dream11 · Meesho.

- **2026-09-05 다섯 번째 후보 조사 — 한 곳을 열어 한 곳을 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **⚠️ 이번에는 새 이름을 찾지 않았다.** 앞 조사에서 *"Medium 이라 못 읽는다로 떨어뜨린 목록이
  그대로 후보 명단"* 이라고 적어 뒀고, 그 명단 맨 위(Booking.com)를 브라우저로 열었더니 **한 번에 됐다.**
  - **✅ Booking.com** — 위 대기 표로 올렸다. **세 사이클 전에 "본문이 Medium 으로 간다"며
    떨어뜨렸던 곳**이다. 브라우저로 여니 20분 분량 전문이 그대로 온다.
  - **⏳ 아직 남은 되살릴 목록** — Trainline · Traveloka(⚠️ 2020~2022 에서 멈춤) · Tokopedia ·
    Dream11 · Meesho. **큐가 빌 때 여기부터 본다.**

- **2026-09-05 네 번째 후보 조사 — 브라우저를 켜자 둘이 한 번에 열렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **⚠️ 이번 사이클의 교훈은 회사가 아니라 도구다.** 앞 사이클이 빈손으로 끝나며 STATE 에
  *"Bolt 를 브라우저로 다시 본다"* 를 적어 뒀고, 그대로 했더니 **첫 시도에 전문이 왔다.**
  - **✅ Bolt** — 위 대기 표로 올렸다. **본문이 비어 오던 것이 브라우저로는 통째로 온다.**
  - **✅ Mercado Libre** — 위 대기 표로 올렸다. **Medium 이라 세 사이클 전에 떨어뜨렸던 곳**인데
    브라우저로 여니 전문이 온다. **연도가 1999·2010·2015·2018 로 다 붙어 있다.**
  - **⚠️ 그러니 "Medium 이라 못 읽는다"로 떨어뜨린 후보들을 다시 봐야 한다** —
    Booking.com(`medium.com/booking-com-development`, **250개 이상 MySQL 클러스터 백업 카탈로그 이전** 등
    회고 여럿) · Trainline · Traveloka · Tokopedia · Dream11 · Meesho 가 그 목록이다.
    **접근 지도에 `medium.com` 은 브라우저로 열린다고 적혀 있었는데 후보 조사에서 그것을 안 썼다.**
    **큐가 빌 때마다 새 이름을 찾을 것이 아니라, 이 목록을 브라우저로 다시 여는 것이 훨씬 싸다.**

- **2026-09-05 세 번째 후보 조사 — 여덟 곳을 두드려 하나도 못 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  **⚠️ 빈손으로 끝난 사이클이다**(311 에 전례가 있다). 노린 새 축은 **물류 · 부동산 · 보험 ·
  암호화폐 · 개발자도구**였다.
  - **⏳ Bolt**(에스토니아 · 모빌리티) — **가장 아까운 곳이다. 다음에 브라우저로 다시 본다.**
    `bolt.eu/en/blog/category/tech-at-bolt/` 는 **목록이 잘 오고 제목도 회고형**이다:
    `migrating-looker-to-databricks`(2026-08-04, **월 1000만 쿼리를 Presto→Databricks**) ·
    `how-bolt-simplified-fraud-checkpoints`(**과잉설계에서 단순함으로**) ·
    `tracking-payments-at-scale` · `scaling-security-testing-bolt-bug-bounty`.
    **⚠️ 그런데 본문이 셋 다 비어 온다** — 제목·읽는 시간·이미지만 오고 글이 없다(JS 렌더링).
    **`engineering.ramp.com` 과 같은 형태다.** 브라우저 `get_page_text` 로는 열릴 수 있다.
    ⚠️ 모빌리티는 Uber·Grab·Careem 과 겹치지만 **유럽·아프리카 시장이고 에스토니아 회사**다.
  - **❌ ClickHouse** — `clickhouse.com/blog` 는 열리고 최신도 **2026-09-05** 인데
    **첫 페이지가 제품 발표와 고객 사례**다(ClickPipes GA · Managed Postgres · 마이그레이션 가이드).
    자기 설계의 대가를 다루는 글이 안 보인다. ⚠️ **58페이지라 뒤쪽에 깊은 글이 있을 수 있다** —
    구체적인 글 주소를 찾으면 그때 다시 본다.
  - **❌ Tailscale** — `tailscale.com/blog` 도 같은 이유다. 최신 목록이 **제품 발표**(PAM 베타 ·
    DNS 필터링 · Aperture GA)다. ⚠️ 이 회사는 깊은 글로 알려져 있으니 **아카이브에서 특정 글을
    찾으면** 다시 볼 값이 있다.
  - **❌ Flexport**(US · 물류) · **❌ Redfin**(US · 부동산) — `flexport.engineering` ·
    `redfin.engineering` 둘 다 **응답이 없고 검색에도 안 잡힌다.** 엔지니어링 서브도메인이
    사라진 것으로 보인다. **물류·부동산 축을 노렸는데 둘 다 접근 자체가 안 된다.**
  - **❌ 보험 전반**(Lemonade · Root · Hippo) — **엔지니어링 블로그를 하나도 못 찾았다.**
    3자 분석 글만 나온다. **보험은 0곳인데 후보 자체가 없다** — 게임과 같은 모양이다.
  - **❌ Sentry** — `blog.sentry.io` 목록은 열리는데 **글 주소를 맞히지 못했다**(404).
    ⚠️ 목록에서 정확한 URL 을 받아 다시 보면 될 일이다 — **못 읽은 것이지 없는 것이 아니다.**

- **2026-09-05 두 번째 후보 조사 — 일곱 곳을 두드려 하나를 올렸다.** 큐가 0/3 이라 3순위로 들어왔다.
  이번에는 **접근 지도에 없는 새 축만** 골랐다(에너지 · 아프리카 · 중국 · 통신 · 동남아 · 전통은행).
  - **✅ Kraken Technologies**(옥토퍼스 에너지) — 위 대기 표로 올렸다. **에너지 축 첫 자리다.**
    ⚠️ **`tech.octopus.energy` 는 이전 안내 페이지만 뜬다** — 실물은 `engineering.kraken.tech` 다.
    앞의 글(2015~2019)은 Octopus Energy 이름으로, 최근은 Kraken 이름으로 나온다.
  - **❌ Flutterwave · Paystack**(NG · 핀테크) — **엔지니어링 블로그 자체를 못 찾았다.**
    `flutterwave.com/us/blog` 는 사업 소식(라이선스 취득·처리액 성장)이고 기술 글이 아니다.
    아프리카 자리를 Moniepoint 하나로 두고 있었는데 **두 번째를 못 찾았다.**
  - **❌ PingCAP / TiDB**(CN) — `pingcap.com/blog` 는 **열리고 최신도 2026-09-03** 인데
    제목이 전부 **제품 활용·AI 마케팅**이다(서버리스 MySQL for AI Agents 류). 자기 설계의
    대가를 다루는 글이 안 보인다. **중국 자리를 늘릴 후보였는데 결이 안 맞는다.**
  - **❌ Ably**(UK · 실시간 인프라) — 열리지만 최신 글이 **제품 발표**다(tfgen · LiveObjects Java).
    아키텍처 결정과 대가를 다루는 글이 목록에 안 보인다.
  - **❌ Capital One**(US · 전통 대형은행) — `capitalone.com/tech/blog` 는 열리지만
    **성과 홍보 중심**이다(*"hands-free security remediation without sacrificing development velocity"*).
    **전통 대형은행 축이 비어 있어 아쉽다** — 카카오뱅크는 인터넷은행이라 결이 다르다.
  - **❌ Alibaba Cloud**(CN) — `www.alibabacloud.com/blog` 가 **본문이 비어 온다**(JS 렌더링으로 보인다).
    ⚠️ 브라우저로는 열릴 수 있다.
  - **❌ Traveloka**(ID · 여행) — `medium.com/traveloka-engineering` **Medium** 이고
    글이 **2020~2022 에서 멈췄다.** 동남아 자리(Grab 하나)를 늘릴 후보였다.

- **2026-09-05 후보 조사 결과 — 열한 곳을 두드려 하나를 올렸다**(369 다음의 후보 조사다).
  큐가 0/3 이라 3순위로 들어왔다. **⚠️ 이번 수확률이 낮은 이유는 회사 탓이 아니라 벽 탓이다** —
  열 곳 중 **여섯이 403, 둘이 Medium, 둘이 도구가 아예 못 여는 호스트**였다.
  - **✅ Nubank**(BR · 핀테크) — 위 대기 표로 올렸다. **라틴아메리카 첫 자리다.**
  - **❌ Mercado Libre**(AR · 이커머스) — 회고 제목이 아주 좋다(`the-technological-evolution-at-mercado-libre`
    — 모놀리스에서 멀티클라우드로, `from-a-single-point-of-failure-to-a-cell-based-architecture`).
    그런데 **전부 `medium.com/mercadolibre-tech` 호스팅이고 403** 이다. 자체 도메인 블로그가 없다.
    **⚠️ 브라우저로는 열릴 수 있다**(원장에 `medium.com` 이 그렇게 적혀 있다) — 라틴 자리가 급하면 다시 볼 값이 있다.
  - **❌ Booking.com**(NL · 여행) — **목록(`blog.booking.com`)은 WebFetch 로 잘 열리고 최신도 2026-07-29** 인데,
    **글 제목을 누르면 `medium.com/booking-com-development` 로 간다**(403). 목록만 자체 도메인이고 본문은 Medium 인
    형태다 — **이 원장에 없던 새로운 종류의 벽**이라 따로 적어 둔다. `Breaking the Loop`(250개 이상 MySQL 클러스터의
    백업 카탈로그를 AWS 로) 같은 회고가 여럿이라 아깝다.
  - **❌ The New York Times**(`open.nytimes.com`) · **❌ The Guardian**(`theguardian.com/info/series/digital-blog`) —
    **둘 다 도구가 그 호스트를 아예 못 연다**(*"Claude Code is unable to fetch from ..."*). 403 과는 다른 종류의
    벽이라 재시도해도 같을 것이다. **미디어·뉴스 축은 이 도구로는 막혀 있다.**
  - **❌ Khan Academy**(US · 교육) — `blog.khanacademy.org/engineering/` 는 **열리는데 최신이 2025-09** 이고,
    목록이 색상 시스템·인턴 이야기·직무 소개라 **심도가 얕다.** Rakuten 과 같은 이유다(사실상 멈춘 블로그).
  - **❌ Etsy**(`www.etsy.com/codeascraft`) · **❌ Delivery Hero**(`tech.deliveryhero.com`) ·
    **❌ Bloomberg**(`www.techatbloomberg.com/blog`) — **셋 다 403.**
  - **❌ Trainline**(UK · 철도) — `engineering.thetrainline.com` 이 **`medium.com/trainline` 으로 301** 된다.
  - **⚠️ DoorDash 를 또 두드렸다** — `careersatdoordash.com/engineering-blog` 는 **이미 STATE.md 의 자료 접근
    지도에 403 으로 적혀 있었다.** 원장을 먼저 읽었으면 아꼈을 한 번이다. **후보를 떠올린 다음, 두드리기 전에
    접근 지도부터 본다.**

- **369 후보 조사 결과 — 네 곳을 두드려 둘을 올렸다.** 큐가 0/3 이라 3순위(후보 조사)로 들어왔다.
  - **✅ Fly.io** — 위 대기 표로 올렸다. **363 에서 ⏳ 로 남긴 것을 이번에 확인했다.**
  - **✅ Oxide Computer** — 위 대기 표로 올렸다. **하드웨어를 만드는 회사가 하나도 없던 자리다.**
  - **❌ Duolingo**(US · 교육) — `blog.duolingo.com/hub/engineering/` 는 **열리고 최신도 2026-08-04** 인데,
    **두 편을 열어 보니 버린 대안이 없다.** `production-ready-ai-agent-platform`(2026-08-04)은
    아예 대가라는 틀 자체를 부정한다 — **"Moving fast is usually framed as a tradeoff against
    building production-ready systems. This platform collapses that tradeoff."**
    `reduce-cpu-usage-97-percent`(2026-06-22)는 **수치가 좋지만**(CPU 약 97% 감소, 파드 32→8,
    피크 CPU 3.5% 미만) **버려진 대안도 대가도 없는 버그 수정기**다.
    **Monzo·GetYourGuide 와 같은 이유로 뺀다**(결정은 있는데 대가가 없다).
  - **❌ Picnic**(NL · 물류·식료품) — **`blog.picnic.nl` 이 `jobs.picnic.app` 로 301** 된다.
    **엔지니어링 블로그가 채용 페이지로 접혔다** — Riot Games·GetYourGuide 와 같은 형태다.
    `picnic.tech` 는 오픈소스 저장소 목록일 뿐 글이 없다.
    ⚠️ 예전 Medium 계정(`medium.com/picnic-engineering`)은 확인하지 않았다 — **Medium 은 403 이
    잦으므로**(아데빈타·무신사·당근) 기대는 낮다.
  - **❌ 게임 전반** — 63곳 중 게임이 Roblox 하나뿐이라 다시 두드렸으나 **후보 자체를 못 찾았다.**
    363 에서 Riot Games 가 블로그를 뉴스로 접은 데 이어, 이번 검색에서도 **주요 스튜디오가 백엔드를
    사내에서 만들고 공개하지 않는다**는 정리만 나온다. **⚠️ 새 단서(특정 글 주소)가 없으면 다시
    두드리지 않는다** — 같은 벽을 세 번째로 들이받는 셈이다.

- **363 후보 조사 결과 — 다섯 곳을 두드려 셋을 올렸다.** 큐가 0/3 이라 3순위(후보 조사)로 들어왔다.
  - **✅ ZOZO · ✅ 쏘카 · ✅ 카카오뱅크** — 위 대기 표로 올렸다. 셋 다 **글 본문까지 열어** 버린 대안·대가·수치를 확인했다.
  - **❌ Monzo**(UK · 핀테크) — `monzo.com/blog/technology` 는 **열리고 최신도 2026-08-13** 인데, 두 편을 열어 보니 **결정과 수치는 있고 대가가 거의 없다.** `a-meshy-approach-to-data` 는 중앙 소유권을 버린 이유와 결과 수치(비용 약 40% 감소·데이터 도착 약 25% 단축, dbt 모델 12,000개·팀 100곳 이상)를 주지만 트레이드오프를 적지 않고 *"아직 전사 마이그레이션 30% 진행 중"* 이라 한다. `the-engineering-behind-the-platform` 도 자체 서비스를 만든 이유는 적지만 그 대가를 안 적고 수치는 **마이크로서비스 3,000개 이상** 하나뿐이다. **GetYourGuide 를 떨어뜨린 것과 같은 이유다**(결정은 있는데 대가가 없다). 다만 예전 장애 회고들은 다를 수 있으니 **구체적인 회고 글 주소를 찾으면 그때 다시 볼 것.**
  - **❌ Riot Games**(게임) — `technology.riotgames.com` 이 **`riotgames.com/en/news?q=tech blog` 로 301** 된다. 전용 엔지니어링 블로그가 뉴스로 접힌 것으로 보인다(`/news` 는 **504**). 게임 자리가 Roblox 하나뿐이라 아쉽지만 **1차 블로그가 사라졌다.**
  - **✅→ Fly.io** — **369 에서 확인해 대기 표로 올렸다.**
- **311 후보 조사 결과 — 셋을 보고 하나도 못 올렸다.**
  - **❌ SoundCloud** — `soundcloud.com/blog` 은 **뉴스룸**이고 엔지니어링 블로그가 아니다. `developers.soundcloud.com` 은 API 문서다.
  - **❌ Kuaishou(快手)** — 검색해도 **전용 엔지니어링 블로그가 없다.** 오픈소스 저장소와 IR 블로그뿐이다. **중국 기업이 WeChat 공식계정만 쓰는 두 번째 사례다**(Xiaohongshu 가 첫 번째, 305).
  - **❌ GetYourGuide** — `inside.getyourguide.com` 이 `getyourguide.careers/blog` 로 리다이렉트되고 **채용·문화 블로그**다. 그래도 305 의 교훈대로 기술 글 한 편(`LLM evals in three days`, 2026-08-25)을 열어 봤는데 **버린 대안 0 · 수치 0** 이고 한계도 *"Three days is not enough to master 'LLMs in production'"* 한 줄뿐이었다. **결정은 여덟인데 대가가 거의 없다.**

- **305 후보 조사 결과 — 셋을 보고 하나만 올렸다.**
  - **✅ Cybozu** — 위 대기 표로 올렸다.
  - **❌ Xiaohongshu(小红书)** — 검색해도 **전용 엔지니어링 블로그가 없다.** 중국 기업이 WeChat 공식계정을 주로 쓰는 탓으로 보인다(**추정**). 3자 정리 글만 나온다.
  - **❌ HelloFresh** — `engineering.hellofresh.com` 이 **403**.

- **298 후보 조사 결과 — 여섯 곳을 보고 하나만 올렸다.**
  - **✅ Meituan** — 위 대기 표로 올렸다.
  - **❌ Dream11**(IN) — `tech.dream11.in` 은 1차 자료이고 열리지만 **최신 글이 2024-10** 이다. 본문 한 편(지능형 이미지 전송)을 열어 보니 **버린 대안 0 · 대가 사실상 0**(GIF 를 제외한다는 한 줄뿐)이고 **수치만 있다**(동시 접속 1,500만 · 세션당 이미지 약 300장 · 이그레스 비용 **약 70% 감소**). **셋 중 하나만 넘겨 떨어뜨렸다.** Medium 판(`medium.com/dream11tech`)도 있으나 Medium 은 막힌 곳이다.
  - **❌ Rakuten**(JP) — `engineering.rakuten.today` 는 1차 자료이고 기술 심도도 있으나 **최신 글이 2023-10 이고 대부분 2021년**이다. 사실상 멈춘 블로그로 본다.
  - **❌ Meesho**(IN) — `www.meesho.io/blog` 이 **403**. Medium 판만 남는데 막힌 곳이다.
  - **❌ Tokopedia / GoTo** — 공식 블로그가 `medium.com/tokopedia-engineering` 로 **Medium 호스팅**이다. 막힌 곳.
  - **❌ Sea / Shopee** — **1차 블로그 주소 자체를 못 찾았다.** `shopee` 는 DNS 없음으로 이미 막혔고, Sea Group 쪽 별도 엔지니어링 블로그가 검색에 안 잡힌다. **두 번째 실패라 재시도 안 함으로 옮긴다.**
  - **❌ VNG**(베트남) — 검색해도 **엔지니어링 블로그가 없다.** 회사 소개·채용 페이지뿐이다.

- **⚠️ 283 정정 — Roblox 는 이미 완료된 회사다.** 273 에서 '게임 자리가 비어 있다' 며 후보로 적었는데, **`index.json` 완료 목록에 `roblox` 가 있다.** 아래 Roblox 항목은 **새 후보가 아니라 보강 단서**로만 읽는다 — `Inside the Tech` 시리즈에 안 읽은 편이 있으면 보강에 쓸 수 있다.

- **Roblox** (US · 게임) — **접근 경로를 찾았다**: `blog.roblox.com` → `corp.roblox.com` → **`about.roblox.com/newsroom/<연>/<월>/<슬러그>`** 가 최종이다(리다이렉트 두 번, 본문은 다 온다). **⚠️ 다만 대기로 올리지 않았다** — `inside-tech-solving-matchmaking-roblox`(2023-10)와 `inside-the-tech-solving-for-safety-in-immersive-voice-communication`(2024-01)을 열었는데 **둘 다 버린 대안이 없고 수치가 약하다**(전자는 *"a quick 10x jump in requests"* 뿐, 후자는 *"almost all English voice abuse reports"* 뿐). 대가는 적는다(*"we can't use standard distributed systems techniques, like relying solely on caching"* · 오탐 우려 · ML 한계). **기준(버린 대안·대가·수치 중 둘) 미달이라 접었지만, `Inside the Tech` 시리즈에 다른 편이 여럿이므로 게임 자리가 급하면 다시 볼 값이 있다.** ⚠️ 2023~2024 글이라 최신은 아니다.

- **253 에서 다섯 곳을 두드려 둘을 건졌다.** 확정으로 막힌 곳 — **Cygames** `tech.cygames.co.jp` 는 **WebFetch 로도 브라우저 `get_page_text` 로도 본문이 안 나온다**(*"No text content found"*, `/archives/` 는 404). **두 번 다른 방법으로 시도해 두 번 다 실패했다 — 게임 자리를 메울 후보였지만 접는다.** **Gojek** `www.gojek.io/blog` 는 **429 가 세 번째다**(246 에 두 번). 일시적 제한이 아닌 것으로 보인다 — 접는다. **Agoda** `careersatagoda.com/blog` **403**.

- **265 에서 여덟 곳을 두드려 하나만 건졌다**(한국 밖에서만 찾았다). 확정으로 막힌 곳 — **Atlassian** `www.atlassian.com/engineering` 은 **엔지니어링 경로가 일반 블로그로 계속 리다이렉트된다**(`/engineering` → `/blog/atlassian-engineering/` → `/blog` 로 두 번 따라갔다. **전용 엔지니어링 블로그가 없어진 것으로 보인다**) · **N26** `tech.n26.com` **DNS 없음** · **Robinhood** 뉴스룸(`robinhood.com/newsroom/`)에 **엔지니어링 섹션이 없다**(분류가 Crypto·Design·Education·Ideas·News 뿐) · **Wolt** 은 기술 블로그를 `careers.wolt.com/en/blog` 로 옮겼는데 **채용·문화 중심이고 기술 글이 하나뿐**이다(2026-06-04 analytics engineering 소개 한 편) · **Twitch** `blog.twitch.tv/en/tags/engineering/` 는 **목록이 JS 로 그려져 안 온다** · **eBay** `innovation.ebayinc.com/tech/` 는 **60초 타임아웃**.

- **📌 Grab 은 이미 `done` 인데 2026년 새 글이 많다 — 보강 후보다.** `engineering.grab.com` 최신이 **2026-08-21** 이고, **Palana 2부작**(AI 에이전트를 위한 격리·신원·감사 구조, 2026-06-19/21) · **Agent platform (Part 1)**(2026-07-24) · **Apache Iceberg 데이터 레이크 이전**(2026-07-10) · **Counter Service 저장소 이전**(2026-07-03) 이 있다. **이 사이트의 Grab 페이지는 `counter-service`·`iceberg-lake`·`dispatchgym` 셋인데 그 두 주제의 후속 글이 새로 나온 셈이다.** **2부작이 있어 파기 좋다**(262).

- **246 에서 여덟 곳을 두드려 한 곳만 건졌다.** 확정으로 막힌 곳 — `shopee.engineering` **DNS 없음** · `developers.smartnews.com/blog` 는 `www.smartnews.com/blog` 로 301 되는데 그쪽이 **404** · `blog.paypay.ne.jp` **403** · `blog.revolut.com` **403** · `deliveroo.engineering` **403** · `engineering.ramp.com` 은 **200 인데 본문이 비어 온다**(JS 렌더링). **재시도 여지가 남은 둘** — `www.gojek.io/blog` 는 **429**(일시적일 수 있다, 시간을 두고 다시) · `tech.cygames.co.jp` 는 **헤더만 오고 목록이 JS 로 그려진다**(브라우저 `get_page_text` 로는 열릴 수 있다 — **게임 자리가 비어 있으니 값이 있다**, `/archives/` 는 404 였다).

- **iFood** (BR · 배달) — `engineering.ifood.com.br` 이 **WebFetch 403**(사이클 206). 라틴아메리카 0곳을 메울 후보였고
  브라질 최대 배달이라 배민·Careem 과 비교할 축이 좋은데 **직접 열리지 않는다.** 다른 경로가 보이면 다시 볼 것.
- **Wildlife Studios** (BR · 게임) — `blog.wildlifestudios.com` **DNS 자체가 없다**(사이클 206).
  게임과 라틴아메리카를 한 번에 메울 후보였는데 주소를 잘못 알고 있었다. **정확한 블로그 주소를 찾으면 다시 볼 것.**
- **라틴아메리카 — 사이클 215 에서 다섯 곳을 두드려 전부 실패했다.** `engineering.rappi.com` **403**,
  `engineering.quintoandar.com.br` · `tech.mercadolibre.com` **DNS 자체가 없음**. (iFood 403 · Wildlife Studios DNS 없음은 사이클 206.)
  **자체 도메인 기술 블로그를 가진 라틴아메리카 회사를 아직 못 찾았다** — Medium 호스팅이 많은 것으로 보인다.
  **새 단서(구체적인 블로그 주소)가 없으면 다음 후보 조사에서 라틴아메리카를 다시 뒤지지 않는다.**
- **물류 전문 — 자체 블로그를 못 찾았다.** `tech.ocado.com` **DNS 없음**, `ninjavan.co/en-sg/blog` **404**,
  `careersatdoordash.com/engineering-blog` **403**. **대신 Target(매장 기반 주문 분배)으로 이 자리를 일부 메웠다.**
- **Backblaze** (US · 스토리지) — `www.backblaze.com/blog` ✅ **열린다.** Drive Stats 수치는 넘친다
  (2025년 연환산 실패율 **1.36%**, 데이터셋 **3억 8,800만 건**·하루 **24만 건** 증가, 논문 **227편** 인용).
  **그런데 본문을 읽어 보니 데이터·홍보 성격이라 의사결정과 대가가 없다** — 기준 ②를 못 채운다.
  **설계 결정을 다루는 글을 찾으면 그때 올릴 것.**
- **Unreal Engine**(게임) — `unrealengine.com/en-US/tech-blog` **403**(사이클 215). 게임이 Roblox 하나뿐이라
  다시 볼 가치가 있으니 다른 경로가 보이면 확인할 것.
- **ClickHouse** (US · SaaS) — `clickhouse.com/blog` ✅ 열린다. **본문도 확인했다**
  (`protect-postgres-from-supporting-processes`: 보조 프로세스(PgBouncer·백업 에이전트·익스포터·로그 수집기)를
  cgroup v2 슬라이스와 `GOMEMLIMIT`·`memory.high`·`memory.max` 로 가둔다). **그런데 수치가 하나도 없다** —
  큐에 넣는 기준 ②(수치)를 못 채운다. **수치가 있는 다른 글을 찾은 뒤에 올릴 것.**

후보 조사 사이클이 이것부터 본다. **여기 있다는 것은 이름을 들어 봤다는 뜻일 뿐,
1차 자료가 의사결정과 대가를 말하는지는 확인되지 않았다.** 확인하고 나서 위 표로 올린다.

- **Airbnb** (US, 마켓플레이스) — **대기에서 내렸다.** 축은 여전히 좋다(재고가 남의 집,
  검색이 지리+날짜). 다만 `medium.com/airbnb-engineering` 이 **WebFetch 403 을 두 번**
  냈고(사이클 129·134), 브라우저는 이 세션에서 두 번 응답 불능이었다. **읽을 수 없는 회사를
  큐 맨 위에 두면 다음 신규 사이클이 통째로 막힌다.** 브라우저가 살아나면 그때 올린다.
- **Spotify** (SE/EU, 스트리밍) — 블로그는 읽히고 EU 가 0곳이라는 점이 매력. 다만 최근 글이
  LLM·데이터 플랫폼 쪽에 쏠려 있고 추천·스트리밍 축은 Netflix·YouTube 와 겹친다. 후순위
- **Delivery Hero** (DE, 배달) — `tech.deliveryhero.com` 이 **WebFetch 403**(사이클 168).
  검색 결과에는 본문 수준 내용이 보였는데(6개월마다 아키텍처 리뷰, 모놀리스 우선 후 분해,
  전 세계 50개 이상 통합) **직접 열리지 않는다.** 배민의 모회사라 축이 흥미로울 수 있으니
  다른 경로가 보이면 다시 볼 것.
- **인도 후보 (Zomato · Swiggy · Flipkart)** — **사이클 166 에서 접근 확인 실패.**
  `blog.swiggy.com/category/engineering/` 는 **404**, `blog.zomato.com/...` 는 **301 리다이렉트 뒤
  본문 요청이 60초 타임아웃**, Swiggy 의 `bytes.swiggy.com` 은 **Medium 호스팅**이라 403 위험이 있다
  (Airbnb 선례). 다만 **글감 자체는 좋아 보인다** — Zomato 의 *TiDB → DynamoDB 전환*, **300개 이상
  마이크로서비스 벤치마킹 플랫폼 자체 제작**, NYE 트래픽 대응기 / Swiggy 의 **k8s 워크로드 Graviton
  이전**(가격 대비 성능 최대 40% 개선). **다시 볼 때는 `www.zomato.com/blog/...` 정규 URL 로
  시도할 것**(리다이렉트된 주소다).
- **Nubank** (BR, 핀테크) — **막혔다(사이클 165).** 남미 첫 회사가 될 후보였고 Clojure·Datomic·
  Kafka 라는 드문 스택이지만, `building.nubank.com.br/engineering-tech/` 가 **WebFetch 403**.
  검색으로는 본문 수준 근거를 못 얻었다. **다른 경로(international.nubank.com.br 의 발표 자료 등)를
  찾으면 다시 볼 것** — Airbnb 처럼 읽을 수 없는 회사를 대기로 올리면 신규 사이클이 통째로 막힌다.
- **Monzo** (UK/EU, 핀테크) — **재 보고 뺐다(140).** 예전에는 마이크로서비스·Cassandra 로
  유명했는데 **최근 글이 AI 도구·채용·조직 문화 쪽으로 기울었다.** 아키텍처 결정과 대가를
  다루는 글이 안 보인다. 옛 글을 파고들 이유가 생기면 다시 본다.


## 보류

파던 중에 멈춘 곳. 큐 잔량에 세지 않는다. 회사 JSON 의 `hold_reason` 이 같은 사실을
기계가 읽는 형태로 갖고 있고, `--gaps` 는 그것을 보고 대상에서 뺀다.

| 회사 | 어디서 멈췄나 | 다시 여는 조건 |
|---|---|---|
| 카카오톡 (메시징) | 도메인 6/7 · 기능 6개. 동기화·다중 기기가 비었다 | 두 번 확인해 두 번 다 자료가 없었다(사이클 028). 새 발표 단서가 생기면 연다 |

| **bol.com** | EU(NL) · 커머스 | `techlab.bol.com/en` | ⏸️ **보류(사이클 226)** — **블로그 글이 2024-11-07 에서 멈췄다.** 목록 16페이지의 1페이지가 최신인데 2025·2026 글이 하나도 없고, 2026 항목 둘은 **경력 팟캐스트**(`/en/podcasts/`)다. 멈춘 블로그로는 도메인 두 개를 열 재료가 안 나온다. **새 글이 올라오면 다시 꺼낸다** — 확인해 둔 재료는 모놀리스 데이터 분리(4TB 중 3TB · 이관 잡 19~23시간 · 전체 2~3개월 · CPU 4%→약 15% · 버린 대안 셋) |

## 완료

- **Duolingo** (US · 교육) — 도메인 3개 · 기능 3개(`when-and-what-are-two-models` 언제 다시 보여 줄지와 무엇을 보여 줄지를 따로 푼다 · `convenience-decides-adoption` 세 번 갈아엎고 나서 편의가 이긴다는 것을 인정한다 · `pipeline-outruns-review` 파이프라인이 리뷰가 삼킬 수 있는 속도보다 빨리 만든다). **교육 축 첫 자리다.** **⭐⭐⭐ 무료 사용자가 압도적으로 많은 구조가 기술 요구를 정한다** — 매일 **5,870만 명**이 들어오는데 돈을 내는 건 **1,270만 명**이라, **한 사람당 계산이 아주 싸야 하고 동시에 내일 다시 오게 만들어야 한다.** **머무르게 하는 일이 곧 매출이라 가르치려는 힘과 붙잡으려는 힘이 같은 손잡이에 달려 있다**(재구성). **⭐⭐⭐ 이 엔진에서 가장 선명한 연표를 세웠다 — 1년 사이 네 세대.** 로컬 MCP(2024-11, **설정이 고통스럽다** · `hand-editing mcp.json` · 소수만 썼다) → 중앙 설정 페이지(2025-05, **깨진다** · Node·Python·Go·Docker · `mismatched npm versions, resource-hungry containers, and zombie processes`) → 표준화된 HTTP MCP(2025-08, **깨지진 않는데 안 쓴다** · `Configuration still required user action`) → 슬랙 앱(2025-09). **⭐⭐⭐ 세 번의 실패가 전부 같은 원인이었고 기술 문제를 다 풀고 나서야 진짜 문제가 보였다** — `not every engineer wants to configure a local AI environment; most just want answers`. 결론을 회사가 문장으로 적는다: **`Convenience wins. A Slack App people can just @-mention is far more adoptable than any MCP-setup guide, no matter how polished.`** **⭐⭐ 사람이 있는 곳으로 가면 도구의 성질이 바뀐다** — 개인 편집기의 도구는 혼자 쓰는 것인데 **채널의 봇은 여러 사람 앞에서 답한다.** 그래서 채널별 맥락·권한 통제·프라이버시 규칙이 새로 필요해졌다(재구성). **⭐⭐ 편의를 극단까지 밀면 봇이 권한 우회로가 된다** — 아무나 @멘션하는데 봇은 도구 **200개 이상**에 닿는다. 한 문장으로 닫는다: `Engineers shouldn't gain access through the bot that they couldn't get directly`. **⭐⭐⭐ 자동화가 성공할수록 병목이 사람 쪽으로 옮겨 간다** — `The pipeline can produce PRs faster than the existing review process can absorb them`. **250개 전부를 사람이 리뷰했고**, 답은 문을 여는 것이 아니라 **앞을 거르는 것**이다(두 번째 리뷰어 에이전트 계획). **그러면 그것은 누가 보는가가 남는다**(재구성). **⭐⭐ 도구를 위해 제품 코드를 바꿨다** — AI 가 테스트를 잘 쓰게 하려고 **구체 인스턴스 대신 프로토콜**을 쓰도록 코드베이스를 옮겼다. **바꾼 이유가 사람이 아니라 생성기였다**(재구성). **⭐⭐ 쉬운 파일부터 간다** — 파일 선택 가중치가 **파일 타입 2.5x** 대 **커버리지 공백 0.5x** 라, **가장 지저분하고 가장 테스트가 필요한 코드가 뒤로 밀린다**(재구성). **⭐⭐ 고칠 권한이 곧 위험이다** — CI 자동 수정 에이전트가 **테스트 PR 에서 프로덕션 소스 파일을 고친 사고**가 났고, 대응은 `We're actively adding guardrails` 로 **아직 진행 중**이다. **⭐⭐ `언제` 와 `무엇` 이 다른 질문이라 두 시스템으로 남았다** — Birdbrain 이 단어 단위 시스템을 **대체하지 않고 보완한다**(`This complements our other personalization system`). **난이도를 사람이 매기지 않고 데이터에서 배운다.** **⭐ 같은 회사가 두 종류의 AI 를 다르게 믿는다** — 학습 쪽은 사내 모델을 **A/B 로** 재고, 개발 쪽은 외부 LLM 을 **사람 승인·사람 리뷰로** 막는다(재구성). **수치** — 2025년 매출 **10억 3,760만 달러(+39%)**, **구독 약 86%** · 2026 2분기 매출 **2억 9,850만 달러** · DAU **5,870만(+23%)** · 유료 **1,270만(+17%)** · Birdbrain 이 먹는 양 **하루 5억 개 이상**의 연습 · 슬랙 봇 주간 **약 300명(회사의 30%)**·찬성률 **약 80%**·도구 **200개 이상** · 에이전트 제작 **몇 주 → 약 10분** · 테스트 파이프라인 17주 **PR 250개·약 85,000줄·함수 4,460개(클래스 233개)** · 하루 **약 20개 PR** · 첫 시도 CI 통과 **76%** · **SwiftLint 실패율 13.6%** · MVVM 커버리지 **9% → 30%**. **⚠️ 2016년 논문 본문을 못 읽었다** — PDF 를 두 번 열어 두 번 다 파싱 실패했고, **첫 시도에서 돌아온 그럴듯한 요약(데이터 규모·개선치)을 근거로 쓰지 않았다.** **⚠️ 지금 개인화가 어디까지 갔는지 모른다**(확인한 수치가 **2020년 10월의 `레슨의 20% 이상`**) · **⚠️ 두 시스템이 충돌할 때를 모른다** · **⚠️ 새 콘텐츠의 난이도를 어떻게 정하는지 모른다** · **⚠️ 정확도·비용·실패율이 에이전트 글 어디에도 없다** · **⚠️ 연표는 에이전트 도메인에만 섰다.**

- **ClickHouse** (US · SaaS — 분석 DB) — 도메인 3개 · 기능 3개(`updates-as-patches-not-rewrites` 고치는 대신 무엇을 고쳤는지만 적어 둔다 · `one-load-job-became-nine` 하나로 굴리던 적재를 아홉으로 쪼갠다 · `seventy-percent-to-ai-thirty-percent-kept` 무엇을 기계에 안 맡길지 먼저 정한다). **⭐⭐⭐ 세 도메인이 한 줄로 이어진다 — 자기 제품으로 자기 창고를 짓고, 그 창고에서 자기 엔진의 한계를 먼저 만나고, 그 창고 위에 AI 를 올린다.** **⭐⭐⭐ 대가가 쓰기에서 읽기로 옮겨 간 것을 벤치마크가 그대로 잰다** — 갱신 가시성은 **최대 1,700배** 빨라지는데 질의는 **8~21%(평균 15.3%)** 느려지고, 폴백은 **39~121%**, `ReplacingMergeTree + FINAL` 은 **평균 280%** 다. **비용을 없앤 게 아니라 옮긴 것이고 회사가 그 크기를 공개한다.** **⭐⭐ 새 기계를 만들지 않고 이미 도는 기계에 얹었다** — 삽입이 원래 빠르고 백그라운드 머지가 어차피 돌기 때문에 패치가 `almost zero overhead` 로 접힌다. **모든 파트가 같은 키로 정렬돼 `a single linear scan of both parts, no re-sorting, no random access`** 라는 성질이 값을 한다. **⭐⭐ 델타는 위치에 기대는데 그 위치가 움직인다** — `_part_offset` 빠른 경로가 어긋나면 `_block_number`·`_block_offset` 해시 조인으로 떨어지고 **패치가 메모리에 다 들어가야 한다.** 메모리에 안 묶이는 전체 머지 조인은 **`not yet implemented`** 라고 직접 적는다. **⭐⭐ 1,000배를 자랑하는 글이 못 하는 것도 같이 적는다** — 서브쿼리·비결정성 제한 · `TOO_MANY_PARTS` 압력 · **25.7 실험적** · 권장 범위 **테이블의 약 10% 까지**. **⭐⭐ 회사가 자기 실패를 두 갈래로 정확히 가른다** — `The insert job was taking too long to execute, and just one error would jeopardize insertion of all data because of dependencies among different data models`. **시간은 나누면 되고 결합은 의존을 끊어야 풀린다** — 작업 하나를 **아홉**으로 쪼갰다. **⭐⭐ 자기 제품을 쓰면 그 비용이 장부에서 사라진다** — 인프라 비용을 **월 약 $1,500** 이라 적으면서 `excluding ClickHouse Cloud as internal service` 를 단다. **가장 큰 항목이 빠지므로 이 사례는 얼마나 싼지를 증명하지 못한다**(재구성). **⭐⭐⭐ AI 도메인의 본체는 넘긴 70% 가 아니라 남긴 30% 다** — 공인 재무 지표·실시간 운영 모니터링·반복 표준 보고를 **일부러 전통 BI 로 남겼고**, 경계를 **세 겹**으로 그었다(일의 종류 · 데이터 범위 · 결론의 지위). ⚠️ **그중 기계가 강제하는 것은 한 겹뿐이다** — PII·고객 데이터를 **프롬프트가 아니라 접근 범위로** 막는다. 나머지 둘은 사람이 지킨다(재구성). **⭐⭐ 모델이 아니라 맥락이 문제였다** — 필드마다 **정의·업무 맥락·값의 범위·그 데이터를 만드는 업무 과정·원천 간 엔티티 관계**를 적은 **사람이 쓴 위키**가 이 시스템의 재료다. **⭐ 글쓴이가 자기 회의부터 적는다** — `I had tried early LLMs with data sources and found the results disappointing and unreliable`(환각·맥락 부족·복잡한 업무 로직). **수치** — 관리형 고객 **3,000곳 이상** · ARR **전년 대비 250% 이상** · 시리즈 D **4억 달러** · 벤치마크 TPC-H `lineitem` SF100 **6억 행·압축 30GiB**(25.7, m6i.8xlarge) · 단일 행 갱신 **90~170초 → 0.04~0.07초** · 창고 원시 원천 **19개** · 하루 **60억 행·50TB** · 2년 누적 **470TB**(압축) · 한 테이블 누적 **약 1조 행** · 인프라 **월 약 $1,500**(Cloud 제외) · 초기 팀 **3명** · DWAINE 사용자 **250명 이상** · 하루 **200 메시지·대화 50~70건** · 분석의 **약 70%** · 지원 요청 **50~70% 감소**. **⚠️ 창고 크기가 자료마다 다르다** — AI 글은 **2.1PB**, 2편은 **470TB(압축)**. **압축 기준인지 시점 차이인지 모른다.** **⚠️ `up to 4,000× faster than PostgreSQL` 은 자기 벤치마크이고 조건이 다른 시스템 간 비교라 그대로 받지 않았다.** **⚠️ 요금 단가를 못 얻었다**(요금 페이지가 철학만 적는다) · **⚠️ Cloud 의 저장·컴퓨트 분리 구현을 모른다** · **⚠️ 1편 발행일을 확인하지 못해 연표를 세우지 않았다**(2편이 `A year later` 인데도) · **⚠️ 적재를 왜 아홉으로 갈랐는지 모른다.**

- **Monzo** (EU·UK · 핀테크 — 네오뱅크) — 도메인 3개 · 기능 3개(`one-team-drives-all-migrations` 이전을 팀마다 맡기지 않고 한 팀이 전부 민다 · `one-node-test-hid-quorum-break` 한 대로 시험한 것이 여섯 대에서는 다른 일이 된다 · `standards-in-ci-not-in-docs` 자율을 두되 어기는 것만 자동으로 막는다). **⭐⭐⭐ 이 회사의 서명은 `자율을 두되 어기는 것만 자동으로 막는다` 이고, 그것이 세 도메인에 다 나온다** — 이전에서는 `semgrep` 이 옛 라이브러리의 새 의존을 막고, 데이터에서는 표준이 PR 을 막는다(`Automate, don't gatekeep`). **소유는 분산하고 방법은 좁힌다** — `Be opinionated: Fewer choices lead to better outcomes at scale`. **⭐⭐⭐ 시험이 규모를 안 바꾸면 그 시험은 다른 것을 시험한 것이다** — 2019-07-29 장애의 핵심이다. **정족수는 대수가 아니라 다수결이라 대수를 바꾸면 성질이 바뀐다.** 시험은 1대(`we'd have agreement from the other two servers` 로 덮인다), 운영은 6대(**파티션당 2~3벌이 빈 노드로 옮겨져 `없음` 이 다수가 된다**). **⭐⭐ 설정 하나가 두 가지를 정하고 있었다** — `auto_bootstrap: false` 가 데이터 스트리밍만이 아니라 **새 노드가 활성으로 합류하는지도** 함께 정했다. **⭐⭐ 담당자가 자기 작업을 배제한 순간을 그대로 적는다** — 13:24 `All of these metrics appear normal and unaffected by the operation`. **지표가 정상인 것과 원인이 아닌 것은 다르다.** 중간에는 모순된 증거까지 나온다(같은 서비스에서 어떤 읽기는 성공하고 어떤 읽기는 실패). **⭐⭐ 고치러 가는 길이 같은 이유로 막혔다** — 설정 서비스가 카산드라에 걸려 있어 내부 edge 가 404 를 내고 **배포와 고객 지원이 함께 멈췄다.** **⭐⭐ 복구를 가능하게 한 것은 데이터베이스 밖에 저장해 둔 이벤트다** — 평소엔 비용이던 것이 유일한 복구 수단이 됐고, 같은 이벤트가 데이터 창고에서는 랜딩 계층의 재료다. **정형화가 두 번 값을 한다**(재구성). **⭐⭐ 의존 그래프가 부분 이전을 막는다** — `all services it might (transitively) call need to also support the new functionality`. 그래서 **대량 배포 도구가 선택이 아니라 전제**가 되고, 새 구현을 **꺼진 채 배포**해 두고 설정으로만 켠다. **⭐⭐ 되돌리는 속도가 두 곳에서 정반대다** — 라이브러리 이전은 **설정 60초**, 장애 복구는 **노드당 8~10분**. **상태를 가진 것은 빨리 되돌릴 수 없다**(재구성). **⭐ 중앙집중이 비싸다는 것을 알면서 골랐다** — 분산 이전은 `unfinished migrations and a lot of coordination effort` 를 남겼고, 중앙은 `high price for one team` 을 치른다. **⭐ 회사가 스스로 방법의 한계를 적는다** — 이전 방식은 **모노레포와 일관된 스택이 없으면 성립하지 않는다.** **수치** — FY2025 매출 **12억 파운드(+48%)** · 조정 세전이익 **1억 1,390만 파운드(8배)** · 고객 **1,200만 명 이상**(신규 240만) · 예금 **166억 파운드(+48%)** · 마이크로서비스 **2,800~3,000개 이상** · 카산드라 사용 서비스 **500개 이상**·클라이언트 **2,300개 이상** · 장애 시 노드 **21+6대·복제 3·정족수 2** · 장애 **약 2시간**·정합 복구 **8시간**·노드 제거 **8~10분** · 설정 갱신 **60초** · dbt 모델 **12,000개 이상**·팀 **100개 이상**·인터페이스 **수백 개**·이전 **30% 시점에 일부 도메인 비용 40%↓·랜딩 25%↓** · 네트워크 격리 **1,500 서비스·9,300 연결 → 평균 6개**. **⚠️ 플랫폼 소개 글에는 버린 대안이 없다** — 대가는 **장애 회고**에 있다. **자료가 얇아 보여 더 찾았더니 `how-we-run-migrations-across-2800-microservices` 가 나왔다 — 한 도메인의 자료가 얇다고 그 도메인이 얇은 것은 아니다.** **⚠️ 매출 구성을 못 얻었다**(연차보고서 요약이 총액만 적는다. PDF 본문 필요) · **⚠️ 클러스터 쪼개기가 어디까지 갔는지 모른다**(다중 클러스터의 흔적은 2019-12 글에서 확인) · **⚠️ 데이터 인터페이스의 강제 방식이 글에 없다** · **⚠️ 연표(eras) 못 세웠다.** **⏳ 안 읽은 글** — `Building a Modern Bank Backend`(2016, **2026년 글과 나란히 놓으면 연표**) · `Autoscaling Monzo`(2020) · `how-we-moved-our-faster-payments-connection-in-house`(**결제망 내재화**) · Linkerd→Envoy 서비스 메시 이전 · AI 축 두 편(**LLM 에이전트 평가 체계 — Sentry 와 비교 재료**).

- **Fastly** (US · CDN·엣지 컴퓨트) — 도메인 4개 · 기능 4개(`purge-must-reach-everywhere` 지우는 일을 한 곳에 맡기지 않는다 · `simple-model-wins-on-rare-days` 평상시를 잘 맞히는 모델을 버리고 드문 날을 고른다 · `structure-hides-content-policy-hides-rest` 구조가 막아 주는 데까지만 막고 나머지는 약속으로 메운다 · `count-fast-or-count-right` 빨리 세는 것과 정확히 세는 것 중 하나를 고르게 한다). **⭐⭐⭐ 네 도메인이 한 판단을 네 번 반복한다 — 중앙에 모으는 편의를 버리고 그 자리에서 끝낸다.** 퍼징은 중앙 큐를 버렸고(`단일 장애점` · 장애 때 일부 서버와 오래 연락 두절), 보안은 중앙 스크러빙을 버렸다(최적이 아닌 경로가 만드는 지연). **⚠️ 대가도 네 번 같다 — 전역으로 아는 곳이 없다.** 퍼지는 **언제 모두가 받았는지 아는 곳이 없어** 상한 대신 **평균 150ms 미만**을 팔고, 속도 제한은 **POP 사이에 계수를 공유하지 않아 최대 10% 적게** 센다. **⭐⭐ 요금 단위가 구조를 드러낸다** — 전달은 GB 를 지역별로, 요청은 1만 건 단위로 따로, 컴퓨트는 요청과 **vCPU 밀리초**를 나눠, 저장은 객체 GB·KV GB·**시크릿 개당**이 다 다르다. **바이트·요청·시간·개수가 각각 다른 자원을 가리키므로 하나를 아끼는 설계가 다른 하나를 늘린다.** **⭐⭐ 프로토콜을 만들지 않고 1999년 논문을 가져왔다** — Bimodal Multicast(Birman et al.). 고른 이유 넷 중 하나가 **`understandable`** 이다. ⚠️ **논문은 손실 20%·프로세스 25% 장애를 견디도록 만들어졌는데 이 회사 POP 간 손실률은 0.1% 미만이다** — 험한 곳용을 순한 곳에 썼고, 그래서 방화벽 오설정 분할(p95 약 10초)과 **DDoS 8분 장애(p95 1분 미만)**를 지나왔다. **⭐⭐ 평균을 일부러 못 맞히기로 한 결정** — 용량 모델의 회귀를 맞출 때 **높은 CPU 표본에 가중치를 더 준다**(`the upper range is where planning decisions happen`). 정석을 다 해 보고 버렸다: `AutoML systems, neural nets, tree models, ensembles, regressions, specialized time-series prediction models, and even LLMs` — 전부 `struggled with the rare cases that matter most for capacity planning`. **⭐⭐ 두 종류의 `안 본다` 를 한 문단에 나란히 적는다** — 평문을 못 보는 것은 **구조**(TLS 악수가 클라이언트와 목적지 사이에서 직접 일어난다)이고, 목적지를 안 남기는 것은 **약속**이라 검증할 수 없다. **⭐⭐ 한 네트워크가 반대 약속을 둘 판다** — 보안은 **들여다보는 값**을, 프록시는 `Nor do we subject proxy traffic to deep packet inspection` 으로 **안 들여다보는 값**을 받는다. **⭐⭐ 파는 쪽이 자기 문서에 못 막는다고 적는다** — `No security product...will detect or prevent all possible attacks or threats.` 오차도 예시까지 들어 공개한다(100rps 한도가 **110rps 에서 걸릴 수 있다**). **⭐ 더 좋은 것을 알면서 덜 좋은 것으로 시작했다** — MASQUE 가 목표인데 `a deliberate, low-risk approach` 로 HTTP/2 CONNECT 를 먼저 냈다. **수치** — 매출 2026 2분기 **1억 8,330만 달러(+23%)**, 전달 **73%(+17%)** · 보안 **23%(+43%)** · 컴퓨트·관측 **4%(+69%)** · POP **약 83곳**(+4 예정) · **622 Tbps** · p99 TTFB **1ms 미만** · 전역 퍼지 **평균 150ms 미만** · POP 간 손실 **0.1% 미만** · 용량 모델 오차 **5% 이내**(버린 모델들 **25% 이상**) · 속도 제한 윈도우 **1·10·60초** · 월드컵 **39일 104경기·결승 동시 시청 18억**. **⚠️ 표준 문서를 열어야 프록시의 한계가 보였다** — RFC 9298·9484 로 보면 **현재 CONNECT 는 TCP 만 나르는데** 회사 글은 MASQUE 를 head-of-line 문제로만 설명한다. **회사 자료만 읽으면 `이렇게 했다` 에서 끝난다는 STYLE 7번의 실증이다.** **⚠️ `deep dive` 가 붙은 글이 고객용 how-to 였다** — 제목의 깊이와 글의 성격은 다르다. **⚠️ 보안 축에 설계 회고가 없다**(매출 23%인데 제품 문서와 행사 후기뿐) · **Adaptive Threat Engine 의 판단 구조 비공개** · **프록시 글에 수치가 하나도 없다** · **연표(eras) 못 세웠다.**

- **Wise** (EU·UK · 핀테크 — 국경 간 송금) — 도메인 3개 · 기능 3개(`standards-as-dependencies` 표준을 문서가 아니라 의존성으로 배포한다 · `deploy-as-events` 배포를 한 번의 거래가 아니라 지켜보는 흐름으로 바꾼다 · `silent-compaction-backlog` 성공한 이전 뒤에 조용히 자란 병목을 찾는다). **⭐⭐ 세 도메인이 한 줄로 이어진다** — 표준을 도구로 배포하니 서비스 1,000개의 배포와 관측이 한 스택으로 모이고, **그래서 그 스택 하나의 병목이 전사에 닿는다.** **⭐⭐ 독립성과 일관성이 서로를 밀어내는 문제를 문서가 아니라 버전으로 푼다** — 조직을 `empowered to innovate and make decisions independently` 라 적으면서, 플러그인 **버전만 올리면 조직 전체 워크플로가 바뀌게** 만들었다(SLSA 를 Java 저장소 700개 이상에 굴린 방식). **⭐⭐ 배포를 관점 전환으로 적는다** — `a paradigm shift from viewing deployments as simple transactions to seeing them as orchestrated sequences of events`. 흐름으로 보면 그 안에 검증과 되돌리기를 끼워 넣을 수 있다(트래픽 5% · 30분 · 자동 롤백). **⭐⭐⭐ 이 회사에서 가장 정직한 글은 마지막 것이다** — Thanos→Mimir 이전은 성공이었는데(피크 질의 지연 75% 감소) **그 뒤에 병목이 조용히 자랐다.** 증상 넷(긴 범위 질의 5XX·지연 / 읽기 경로 컴퓨트 / AZ 간 전송비 / S3 저장비)이 **어느 것도 압축을 안 가리켰다** — `nor did it cross our minds as the likely cause`. **⭐⭐ 회사가 자기 우선순위 실수를 그대로 적는다** — `inadvertently leaving the compactor's optimisation lower on the priority list`. 새 도구를 배우느라 쓰기·읽기에 집중했고 컴팩터가 뒤로 밀렸다. **⭐⭐ 좋은 기본 도구가 모든 것을 알려 주지는 않는다** — Grafana 믹신 대시보드·알림·런북을 **쓰고 있었는데** 압축기 저성능 신호가 없었다. **전환점은 깃허브 이슈의 댓글 하나였다.** **⭐ 되먹임 구조가 문제의 핵심이다** — 백로그 때문에 시작 시 메타데이터 동기화가 **약 9시간**이 걸리고, 그것이 압축을 더 밀었다. 게다가 **기본 설정이 규모에 안 맞아 일부 압축 작업이 조용히 건너뛰어졌다.** **수치** — 엔지니어 **850명 이상** · 서비스 **1,000개 이상** · Java 저장소 **700개 이상** · 클러스터 **6 → 20개 이상** · iOS 무변경 빌드 **28초 → 2초** · Android Gradle 모듈 **300개 이상·약 100만 줄** · 카나리 **5%·30분** · **2024년에만 사고 날 뻔한 배포 수백 건 차단·수천 시간 절약** · 빌드 **15% 단축**(월 50만 빌드에서 월 1,000시간 이상) · Mimir **초당 약 600만 샘플** · **블록 약 25만 개**(문서 기준 `50K blocks would generally not be normal`) · 가장 큰 테넌트에 **두 달치 백로그** · 고친 뒤 **S3 70%↓ · AZ 간 전송 40%↓ · 질의 지연 90%↓**. **⚠️ 스택 소개 글에는 `무엇을 잃었나` 가 거의 없다** — 여섯 갈래 이전의 전후 수치는 다 있는데 대가가 없다. **개별 주제 글을 찾아야 대가 칸이 채워진다는 것을 이 회사가 한 파일 안에서 증명한다**(Mimir 글의 tradeoff 는 전부 confirmed). **⚠️ 매출·수수료 구조를 확인하지 못했다** — 상장사이므로 IR 을 열면 채울 수 있다. **⚠️ 연표(eras) 못 세웠다** — 다만 본문이 **2022년 스택 글**이 있다고 밝힌다. **2022 와 2025 를 나란히 놓으면 시간축이 나올 수 있다.** **⏳ 못 찾은 글** — `our earlier post about the state of our CI/CD pipeline`. **그 글을 찾으면 Octopus 를 버린 대가가 나온다** — 지금은 얻은 것만 적혀 있다.

- **Sentry** (US · SaaS — 오류 추적·관측) — 도메인 2개 · 기능 2개(`ai-opens-human-merges` AI 는 PR 까지 열고 병합은 사람이 한다 · `nightly-agent-audit` 매일 아침 어젯밤의 에이전트를 심문한다). **⭐⭐ 두 도메인이 한 줄로 이어진다 — AI 를 들이면 AI 를 지켜보는 일이 새로 생긴다.** **⭐⭐ 선의 근거가 기술이 아니라 조직이다** — 완전 자율 병합을 거부하며 *"Your org might not be ready to trust the machines that far, and that's ok."* **⭐⭐ 핵심 발견 하나** — *"Sampling both success and failure conversations, not just the ones with tool errors, mattered more than expected."* **오류 없이 끝나도 결론이 틀릴 수 있고 그것은 추론을 읽어야만 보인다.** **⭐ 피드백 고리를 요청에 심었다** — 엔지니어에게 병합/닫기 · 한 줄 피드백 · **`Seer 를 잘 쓴 건지` 표시**를 함께 요청한다. **⭐ 같은 숫자가 반대 뜻을 가질 때** — 병합 없이 닫힌 PR 이 12.5% 늘었는데 안을 보니 중복이거나 리뷰어가 더 포괄적인 수정을 고른 경우여서 **성공으로 읽는다**(⚠️ 자기 지표를 자기가 해석하는 자리라 검증하지 않았다). **⭐ 두 기능이 같은 절제를 공유한다** — 이미 처리된 PR 은 조용히 건너뛰고, 이미 추적 중인 문제로는 티켓을 만들지 않는다. **⭐ 왜 진작 안 했는지를 적는다** — *"we never got around to it due to friction"*. 그 전에는 일회성 흐름을 손으로 돌리고 JSON 을 눈으로 파싱했다. **관측 회사가 자기 에이전트에는 눈을 못 달고 있었다**(재구성). **수치** — 매일 밤 대화 **약 800건** · 표본 **445~551건** · 도구 호출 **약 11,000건** · **오류율 21%**(400 중 83) · **30~56초 지연 행** · PR 액션률 **+21%** · 48시간 응답률 **+13%** · 개입 기준 **4시간 무반응**(루틴은 매시간) · 요금은 Developer 무료(1명) / Team $26 / Business $80(연간). **⚠️ 읽은 글 셋 중 하나는 자기 시스템이 아니었다** — `metrics-caught-ai-size-estimate` 는 **개발자 개인의 오픈소스 프로젝트** 사례라 프로파일에서 뺐다(Capital One 과 같은 함정). **⚠️ Seer 의 내부 구조를 못 봤다.** **⚠️ 오류 추적 제품 자체의 구조를 아직 안 팠다** — 이 회사의 뿌리인데 읽은 글이 전부 AI 워크플로다. **오픈소스이므로 자료가 있을 것이다.** **⚠️ 매출 비공개. 연표(eras) 못 세웠다.**

- **Temporal** (US · SaaS — 내구성 있는 실행) — 도메인 3개 · 기능 3개(`replay-must-match` 다시 밟은 길이 처음 길과 한 걸음도 달라선 안 된다 · `shard-count-is-forever` 하나를 키우지 않고 개수를 늘린다, 대신 샤드 수는 처음에 정해야 한다 · `write-heavy-multi-tenant-persistence` 쓰기가 무거운 다중 테넌트에서 시끄러운 이웃을 바닥에서 막는다). **이 엔진에 없던 축이다 — 내구성 있는 실행(durable execution).** **⚠️ 한 사이클 전에 ❌ 로 떨어뜨렸다가 `안 읽은 글` 메모 덕분에 되살린 곳이다.** **⭐⭐ 축은 하나로 모인다 — 상태가 아니라 상태에 이르는 길을 저장한다.** *"Temporal will recreate the state by parsing the Event History and replaying each step."* **편의를 저장에서 코드로 옮긴 설계**이고, 그 값을 사용자 코드가 낸다. **⭐⭐ 금지되는 것이 매일 쓰는 것들이다** — 시스템 시간 직접 읽기·난수·로컬 시계 분기·API/DB/LLM 호출(액티비티로 옮겨야 한다). **`now()` 와 `random()` 이 금지된다.** **⭐⭐ 가장 무서운 자리는 배포다** — 비결정성 오류는 *"typically from code changes made to running Workflow Executions"* 이고, 안전하지 않은 수정 목록이 구체적이다(커맨드 재정렬·추가·제거 · **타이머 시간을 0으로/0에서**, .NET 은 -1 · 타입 ID 변경). **⭐⭐ 되돌릴 수 없는 결정을 시작 시점에 밀어 놓았다** — **샤드 수는 클러스터를 세운 뒤 바꿀 수 없다**(*"the one configuration setting which cannot (currently) be changed"*). 그런데 그 수가 락 지연과 처리량을 정한다. **⭐ 확장의 방향 자체가 결정이다** — *"we decided not to design for scaling up a single workflow instance"*. 하나를 키우지 않고 개수를 늘리며, 사용자에게 **천 개의 자식 워크플로가 천 개씩** 맡는 모양을 권한다. **⭐ 경계 안에서 끝내고 밖으로는 나중에 흘린다** — 2단계 커밋·Paxos·Raft 를 안 쓰고 **Transfer Queue** 로 푼다. 지연은 주되 유실은 안 준다. **⭐ 줄일 수 없는 쓰기의 모양을 바꾼다** — 실행 상태가 바뀔 때마다 쓰는 것이 제품의 정의라 줄일 수 없어, **WAL 에 모아 한 번의 집계된 갱신**으로 내린다. **⭐ 시끄러운 이웃을 가장 어려운 층에서 막는다** — *"databases are stateful, and take longer to scale, capacity cannot be added quickly to handle spikes in load."* **수치** — 샤드 권장 **512 / 4,096** · 샤드 락 지연 **50ms → 1ms** · 상태 전이 **150/s → 1,350/s** · DB CPU **80% 목표에 79%** · 요청 지연 SLO 150ms 에 **50ms 미만** · 요금은 Essentials $100~ · Business $500~ · 저장 활성 $0.042 대 보존 $0.00105(**약 40배**). **⚠️ 수치가 글마다 크게 다르다** — `scaling-temporal-the-basics` 에는 촘촘한데 **영속 계층 글에는 하나도 없다**(*"we saw an immediate impact"* 뿐). **한 편으로 회사를 판단하면 안 되는 여섯 번째 사례다.** **⚠️ 이벤트 이력의 크기 제한이 문서에 없다** — 이력이 곧 저장이고 저장이 곧 요금인데도. **⚠️ 오픈소스와 관리형이 같은 바닥을 쓰지 않는다** — 영속 계층이 다르다. **⚠️ 매출·고객 수 비공개. 연표(eras) 못 세웠다.**

- **Honeycomb** (US · SaaS — 관측) — 도메인 2개 · 기능 2개(`column-store-no-indexes` 색인도 스키마도 없이 아무 필드나 훑게 만든다 · `swap-kafka-under-load` 관측이 돌아가는 채로 그 밑의 카프카를 갈아 끼운다). **⭐⭐ 요금 구조가 기술 요구를 정하는데 핵심이 안 받는 쪽에 있다** — **좌석 무제한 · 쿼리 무제한**이고 월 이벤트 수로만 받는다. **관측 도구를 좌석으로 팔면 볼 사람을 줄이게 되고 그러면 관측이 안 된다**(재구성). 대신 질의 비용을 회사가 떠안고 그것이 자체 컬럼 저장소를 만든 이유로 이어진다. **⭐⭐ 이 설계의 특징은 만든 것이 아니라 안 만든 것이다** — **색인이 없다.** 색인은 `무엇을 자주 볼지 안다` 는 전제 위에 서는데 디버깅에서는 그것을 모른다. 같은 이유로 사전 집계도 버렸다(*"you cannot predict what dimensions you'll need to examine during debugging"*). 행 지향 DB 를 버린 이유 넷도 전부 같은 축과 부딪힌다(스키마 강제·비싼 이전·파일 재작성·색인 필요). **⭐ 감수한 것을 스스로 적는다** — 컬럼 스토어는 `많은 행 × 적은 열` 에 강하지만 **한 행의 모든 열을 가져오는 데는 행 저장소보다 못하다**(*"a deliberate tradeoff"*). **⭐⭐ 잘 만든 구조가 다른 축에서 무너진 사례** — 서비스가 수백~수천 개인 고객에서 **데이터 양이 아니라 데이터셋 디렉터리와 파일의 수**가 질의를 느리게 했다. 답은 논리 단위와 물리 조직을 떼어 내는 것(가상 데이터셋 + `virtual_dataset` 합성 열)이고 **중앙값 20초 → 약 0.2초**다. **⭐⭐ 나빠진 것을 적고 떠난다** — 브로커 교체가 몇 년 전 **8~12시간**에서 이전 직전 **48~72시간**으로 늘어 있었고(폐쇄 소스 계층 저장), 그래서 오픈소스 Kafka 4.1.1(KRaft) + EKS 로 옮겼다. **⭐ 버린 대안 셋의 이유가 다 다르다** — Warpstream 은 *"we can't trade higher latencies for more cost-effective data transfer"*(99.99% SLO), MirrorMaker 2 는 **오프셋 관리 구조 비호환**, EBS 는 지연 때문에 NVMe 로. **⭐ 무중단보다 데이터 안전을 앞에 뒀다** — *"we accept a window of downtime between the producer cutover and the consumer cutover"*. **⭐ 두려운 절차를 반복 연습으로 다룬다** — 이전 실행이 **4~5시간 → 2~3시간**, 롤백 리허설에만 **4시간 이상**. **수치** — 세그먼트 롤아웃 **100만 이벤트·1GB·12시간** · 가상 데이터셋으로 **20초 → 0.2초** · 클러스터 **6개** · 초기 **7개 팀** 조율 · 요금은 Free 월 2,000만 이벤트 / Pro 월 $150~ 7.5억. **⚠️ 나빠졌던 수치는 남기고 좋아진 수치는 안 남긴 자리가 있다** — 이전 뒤 브로커 교체 시간이 얼마인지 적지 않는다. 총 기간도 `several quarters` 로만, 처리량·비용·브로커 수는 없다. **⚠️ 매출·고객 수 비공개.** **⚠️ 연표(eras)를 못 세웠다** — 다만 `scaling-kafka-observability-pipelines`(예전 글)를 2026년 글과 나란히 놓으면 나올 수 있다. **⏳ 안 읽은 글** — `solving-murder-mystery-columnar-datastore`(자체 컬럼 저장소 버그 추적) · `incident-report-exercises-cleanups-and-evacuations`(장애 보고서).

- **Ably** (EU/UK · SaaS — 실시간 인프라) — 도메인 2개 · 기능 2개(`assume-simultaneous-failure` 장애를 막는 장치도 장애 대상이라고 보고 배치한다 · `order-costs-latency` 순서를 약속하면 지연을 사야 한다). **⚠️ 다섯 사이클 전에 `열리는데 제품 발표` 로 떨어뜨렸다가 판정을 뒤집어 올린 곳이다** — 첫 화면과 `topic/` 이 일반 교육 글이라 심층 글을 못 봤었다. **⭐⭐ 흔한 답을 그 자리에서 버린다** — 리전 간 로드밸런서를 *"the load balancer itself exists in some region and could become unavailable"* 라며 뺀다. **장애를 막으려고 둔 장치가 그 자신도 장애의 대상**이라는 문장이 첫 도메인 전체를 관통한다. Raft/Paxos 도 같은 결로 버린다(*"their efficiency breaks down if the latency becomes too high"*) — **알고리즘이 나빠서가 아니라 전제하는 네트워크가 다르다.** **⭐⭐ 가장 아픈 인정 — 고치려는 행동이 병을 키운다** — 내결함성 기법 자체가 자원을 쓰는데 **장애의 원인이 자원 고갈이면 대응하려는 그때 CPU 와 메모리가 없다.** 게다가 단순한 기법일수록 **O(N²) 이상**으로 튄다. **부분 열화**(*"working some of the time"*)도 어려움으로 적는다 — 죽었다고 보면 멀쩡한 용량을 버리고 살았다고 보면 실패가 새어 나온다. **⭐ 약속의 근거가 확률이다** — 감지·합의 시간 + 역할 재배치 시간 + AZ 실패율로 복합 장애 확률을 모델링한다. **⭐ 두 도메인이 같은 지연에서 만난다** — 리전을 넘는 합의도, 리전을 넘는 메시지 순서도 느려진다. **지역 분산은 내결함성을 주고 순서를 빼앗는다.** **⭐ 가격 단위가 아키텍처를 드러낸다** — 메시지는 건수로, **연결과 채널은 `100만 분` 단위**로 판다($1.00, 할인 시 $0.20). **동시성 유지 자체가 원가다.** **수치** — 기록은 **최소 두 AZ 에 트랜잭션**으로 · 채팅 지연 **중앙값 6.5ms** · 요금 Standard $29 / Pro $399 + 사용량. **⚠️ `eight 9s` 와 `99.999%` 가 같은 것인지 확인하지 못했다** — 내결함성 글과 채팅 글의 표현이 다르다. **여덟 개의 9 와 다섯 개의 9 는 크게 달라 나란히 쓰지 않았다.** **⚠️ 두 글 다 회고형이 아니다** — 일반 이론·안내서 틀에 자기 구조와 주장을 얹은 형태라 `무엇이 한계에 닿아 갈아엎었나` 가 없다. **특히 순서 쪽은 `Ably 가 실제로 어떻게 하는지` 가 통째로 빠져 있고 `보장한다` 는 결론뿐이라** `stack` 에 `unknown` 으로 남겼다. **⚠️ 연표(eras)를 못 세웠다.** **⚠️ 매출·고객 수 비공개.**

- **Tailscale** (CA/US · SaaS — 네트워킹) — 도메인 3개 · 기능 3개(`direct-if-possible-relay-if-not` 직접 잇되 안 되면 눈감은 릴레이로 넘긴다 · `json-file-to-etcd` 이십 줄짜리 지름길이 백오십 메가에 닿을 때까지 버틴다 · `two-implementations-on-purpose` 하나로 합치지 않고 둘을 나란히 둔다). **⚠️ 세 사이클 전에 `열리는데 마케팅` 으로 떨어뜨렸다가 판정을 뒤집어 올린 곳이다** — 첫 화면이 제품 발표라 심층 글을 못 봤었다. **⭐⭐ 세 도메인이 다 `버린 길` 을 갖고 있다** — 중앙 게이트웨이형 VPN · MySQL/PostgreSQL/SQLite/CockroachDB · 점진적 in-place 재작성 · libtailscale. **⭐⭐ 되냐 안 되냐가 아니라 확률로 말한다** — 포트 예측 프로브 **256회 64% · 1,024회 98% · 2,048회 99.9%**(약 20초), **양쪽 다 hard NAT 이면 각 17만 회 · 28분**(생일 역설 없이는 **1.2년**). **⭐⭐ 못 하는 것을 못 한다고 적는다** — UDP 를 DNS 빼고 막는 네트워크에서는 *"No amount of clever NAT tricks is going to get around the firewall eating your packets."* 헤어핀 미지원 NAT, 이중 NAT 이 포트 매핑을 깨뜨리는 것까지 나열한다. **모든 경우에 되는 하나의 방법 대신 사다리를 만들고 바닥(DERP)을 깔았다.** **⭐⭐ 중앙을 없애지 않고 무력하게 만들었다** — 컨트롤 평면은 허브-스포크인데 *"it carries virtually no traffic"*, 개인키는 *"never, ever leaves its node"*, 릴레이는 *"there is never a way for a DERP server to decrypt your traffic."* **⭐⭐ 네 데이터베이스 후보를 버린 이유가 전부 성능이 아니다** — MySQL·PostgreSQL 은 **Docker 테스트 인프라**와 HA 시맨틱, SQLite 는 *"couldn't bring myself to make an argument"*, CockroachDB 는 *"relatively new for a database"*. 그리고 etcd 를 고른 이유 셋 중 하나가 **Go 라 테스트에 직접 링크할 수 있다**는 것이다 — **처음 20줄 지름길을 고른 이유(외부 의존 없는 테스트)와 같은 기준이 두 번 이겼다.** **⭐ 가장 흔한 길을 가장 세게 버린다** — 점진적 in-place 재작성이 *"the worst of all worlds"* 이고, 이유 셋이 전부 사람과 속도 쪽이다. 그리고 이 선택을 *"a pragmatic choice with tradeoffs, rather than an ideological one"* 이라 스스로 못 박는다. **⭐ 미완을 목록으로 적는다** — Rust 구현에 P2P·NAT 순회·DNS·exit node·SSH·Taildrop·**보안 감사**가 없다. **수치** — 직접 연결 **90% 이상**(회사 추정) · IPv6 보급 **약 33%** · JSON 파일 **150MB** · 쓰기 **1초→밀리초** · 인메모리 인덱스에 **2~3주** · 요금 좌석당 **$8/$18**(기기는 무제한). **⚠️ 매출·사용자 수 비공개.** **⚠️ 저장소 이전의 연도를 모른다**(etcd 3.4.3 이라는 단서뿐) — `eras` 를 못 세웠다. **⚠️ 코디네이션 서버가 죽으면 무엇이 멈추는지 회사가 안 적는다.**

- **Rightmove** (EU/UK · 커머스 — 부동산 포털) — 도메인 2개 · 기능 2개(`sitemap-by-events` 밤새 다시 세던 것을 바뀔 때마다 고쳐 쓴다 · `unweave-java-from-html` 자바와 HTML 을 풀어 화면을 프런트엔드 사람 손에 돌려준다). **부동산 축 첫 회사다.** **⭐⭐ 사업 구조가 기술의 무게를 정한다** — 트래픽의 **85% 이상이 직접·자연 유입**이고 포털 체류 시간 10분 중 **9분**을 가져간다. 광고를 사서 손님을 데려오는 회사가 아니라 **사이트맵이 잡무가 아니라 매출 경로다.** 매출도 거래가 아니라 회원 수 × 단가로 움직인다(중개 지점 16,591곳 · ARPA 1,726파운드 · 유지율 96%). **⭐⭐ 버린 것을 장점 칸에 남겨 뒀다** — RFC 표에 옛 배치의 장점이 셋 적혀 있다(추가 저장소 불필요 · 사내 기존 패턴 · **디버깅이 쉽다**). 그럼에도 회복력 하나가 이겼다: *"Not resilient: A single instance meant any failure disrupted the process."* **⭐ 5시간이 30분이 된 이유는 빨라져서가 아니다** — **이미 RX Java 로 병렬화하고 캐시를 쓰고도 5시간**이었다. 바뀐 것은 방향이다: 수십만 건의 REST 로 **물어보던 것을 이벤트로 받아 두는 쪽**으로. **⭐ 상태를 갖는 대가를 치르면 상태로 할 수 있는 일이 생긴다** — 로컬 DB 를 두자 **지역별 실시간 매물 수**가 덤으로 나왔고 회사가 그것을 장점 칸에 적는다. **⭐ 두 번째 부채는 성능이 아니라 사람 문제였다** — JSP 는 *"a pattern that interweaves Java code with HTML"* 이라 **화면을 고치려면 자바를 알아야 했다.** 사내 컴포넌트도 못 쓰고 최신 사내 서비스와도 못 붙었다. **⭐ 화면 만드는 기술로 문서를 만든다** — 서드파티 PDF 라이브러리의 제약을 피해 Puppeteer 로 정적 HTML 을 헤드리스 브라우저에 렌더링한다. **수치** — 해외 매물 지역 **266,569개** · 사이트맵 생성 **5시간 → 30분** · REST 요청 **수십만 건** 제거 · (사업) H1 2026 매출 2억 2,580만 파운드(+7%). **⚠️ 한 회사 안에서 글의 결이 정반대다** — 사이트맵 글은 RFC 장단점 표와 수치를 다 적는데 **프런트엔드 글은 수치가 하나도 없다**(개발 기간·성능·비용·사용자 수 전부, `thousands of users` 하나뿐). **Nubank·Bolt 에 이어 세 번째 사례다.** **⚠️ 재무를 3자 매체로만 확인했다** — `plc.rightmove.co.uk` 1차 IR 을 안 읽어 `revenue_streams` 가 `inferred` 다. **⚠️ 다시 지은 앱의 이름을 글이 밝히지 않는다** — 보고서·권한·대량 온보딩으로 보아 중개사용 사내 도구로 보이나 `connections` 에 `unknown` 으로 뒀다. **⚠️ 기술 글이 `/category/software-engineering/` 에 5페이지 분량인데 두 편만 읽었다.** **⚠️ 연표(eras)는 못 세웠다.**

- **Trainline** (EU/UK · 커머스 — 철도·버스 예약) — 도메인 1개 · 기능 1개(`cdn-in-flight` 날고 있는 비행기의 배달망을 갈아 끼운다). **여행 축 셋째다**(Booking 은 숙박, trivago 는 메타서치, 여기는 철도·버스). **⭐⭐ 이 글의 값은 교훈 한 줄에 있다** — *"Most if not all of our testing was small-scale testing. This didn't allow us to see the bigger picture till the end."* **작은 시험은 동작은 보여 주지만 비용과 한계는 안 보여 준다.** 실제로 두 번 물렸다: 리다이렉트가 1개일 땐 쌌는데 **100개로 늘리자 청구가 튀었고**(Lambda@Edge → CloudFront Functions), 그 대안도 **수천 개에서 타임아웃**이 나 리다이렉트 배포를 따로 떼어 냈다. **⭐ 이전의 성격을 스스로 이름 붙인다** — *"This wasn't a mere lift-and-shift; it was more like re-engineering the aeroplane while in flight!"* 아키텍처를 다시 생각하고 **CDN 모놀리스를 다룰 만한 조각으로 쪼갰다.** **⭐ 새 플랫폼의 제약을 그대로 적는다** — CloudFront 는 확장자 기반 캐시 정책도, 같은 디렉터리 안 선택적 캐시도, 임의 헤더 조건부 캐시도 어렵다. 그래서 **캐시 책임을 CDN 규칙에서 앱의 `cache-control` 로 옮겼다.** **⭐ 되돌릴 길이 앞으로 가게 했다** — 전환 한참 전에 CNAME TTL 을 5분으로 낮췄고, *"This safety net gave us the confidence to proceed."* **⭐ 민감 데이터 쪽 기본값이 보수적이다** — 원본이 헤더를 안 주면 `max-age` 0, 즉 캐시하지 않는다. **수치** — 운영사 270곳 이상·45개국·사용자 1억 이상 · 도메인 300곳 이상 이전 · 주 도메인이 트래픽 70%+ 이고 설정 JSON 8,500줄+ · 9개월 미만(계획 6주, 코어 6~8명) · 가중 DNS 5→10→25→50→75→100% · (사업) FY2026 순 티켓 판매 63.19억 파운드(+7%)·매출 4.53억(+2%)·조정 EBITDA 1.77억(+11%). **⭐ 사업 구조가 숫자에 드러난다** — 영국 B2C 온라인 커미션이 **5%→4.5%** 로 내려가(2022년 예고, 2025년 4월 발효) **판매액 +7% 인데 매출은 +2%** 다. **⚠️ 도메인이 하나뿐이다** — `medium.com/trainline` 은 **발행물 홈도 태그 경로도 목록이 안 온다**(브라우저로도). 검색으로도 다른 기술 글을 못 찾아 **읽은 글이 CDN 이전 한 편(2024-01)뿐**이고 **블로그가 지금도 사는지 모른다.** **⚠️ Platform One 을 못 팠다** — 표를 모으고 값을 매기는 핵심일 텐데 실적 각주에 이름만 나온다. **⚠️ 성과 수치가 없다**(비용 절감·성능 개선을 봤다고만 적는다). **⚠️ 연표(eras)도 못 세웠다** — 옛 CDN 을 `CDN X` 로만 부르고 언제부터였는지 없다.

- **Booking.com** (EU/NL · 커머스—여행) — 도메인 2개 · 기능 2개(`break-the-backup-loop` 백업을 지키는 카탈로그를 백업 대상 밖으로 꺼낸다 · `shift-left-dwh-quality` 품질을 마지막 리뷰 하나에 걸지 않고 생애주기로 흩는다). **여행 축 둘째다**(trivago 는 메타서치). **⭐⭐ 두 기능이 같은 이야기의 두 규모다** — 한쪽은 작은 결함이 하류로 번지는 것을 앞에서 막고, 다른 쪽은 그것이 **순환 의존성이라는 구조로 굳어 버린 것**을 뒤늦게 끊는다. **⭐⭐ 백업 카탈로그가 자기가 지켜야 할 DB 안에 살고 있었다** — 복구 작업을 만들려면 Director 가 필요하고 Director 는 카탈로그가 있어야 하는데, 그 카탈로그가 온프렘 `dbadb` 안의 한 스키마였다. **⭐⭐ 가장 좋은 대목은 발견이 아니라 고백이다** — *"Of course this observation is not new"*, 그리고 왜 안 고쳐졌는지를 적는다: 되돌아보고 다시 설계할 시간이 팀에 늘 있지는 않고 **클라우드 이전 같은 큰 계기가 왔을 때** 고친다고. **⚠️ 계기 없이 고치는 방법은 이 글에도 없다.** **⭐ 통념을 알고도 어긴다** — 보통 이전은 겹치지 말라는데, 나란히 세우는 방식이라 OS(CentOS 8 EOL→OL9)·Bacula(v12→v16)·DB(온프렘→RDS)를 한 번에 새로 세우는 편이 *"intermediate hell"* 을 피해 안전했다. **⭐ 실패를 적는다** — KMS 키는 **생성 시점에만** 다중 리전으로 정할 수 있어 나중에 붙이려다 스냅샷→복호화→재암호화로 클러스터를 다시 만들었다(*"a quite painful lesson"*). **⭐ 잴 수 없는 것을 인정한다** — 공유 호스트의 스키마는 CPU·IOPS 를 격리해 잴 수 없고 QPS 가 자원으로 선형 변환되지 않아, 크게 잡고 2개월 뒤 줄였다(*"reliability must always come first"*). **⭐⭐ 품질 쪽은 엄격함의 실패까지 적는다** — 처음엔 너무 엄해 **진입 문턱이 높게 느껴졌고**, 그래서 일부는 협상 불가로 두되 일부는 단계 도입 + 기술부채 티켓으로 바꿨다: **웨어하우스가 개선하기보다 들어오기 더 어려운 시스템이 되면 안 된다.** **⭐ 가드레일이 속도를 죽이지 않았다** — 7개월간 MR 물량이 **3배 이상** 늘었는데 승인 중앙값은 **2시간 미만 → 1시간 미만**으로 줄었다(AI 사전 리뷰 도입과 겹친다). **수치** — MySQL 클러스터 250개 이상 · 하루 약 1,000개 백업 · `db.r7g.2xlarge`→`xlarge` · dbt 모델 약 1,000개 · 검사 통과 95% 초과 · 85%가 Silver/Gold · 사업부 8곳 40개 이상 사용 사례 · (모회사 기준) 2025년 총 예약액 1,861억 달러 · 객실 밤 12억. **⚠️ Booking.com 단독 매출은 확인하지 못했다** — 공개 자료가 모회사(Booking Holdings) 기준이다. **⚠️ 연표(eras)를 못 세웠다** — Perl 모놀리스→Java·Kotlin 이전이 알려져 있으나 1차 자료를 못 찾았고, 온프렘 카탈로그 구조의 시작 연도도 없다. **⚠️ 본문은 브라우저(`get_page_text`)로만 온다.** **⚠️ 안 읽은 글이 남았다** — `A Migration Adventure` · `Kotlin Multiplatform in Production` · `The Causality Gap` · `Stability in Jetpack Compose`.

- **Mercado Libre** (기타/AR · 커머스) — **연표 3시기** · 도메인 3개 · 기능 3개(`three-clicks-to-production` 세 번 눌러 앱이 뜨고 커피 내리는 동안 고쳐 본다 · `stock-cells` 대륙 하나의 재고를 격벽 셋으로 나눈다 · `six-months-of-saying-no` 삼만 개를 다시 쓰게 하지 않는 것이 첫 관문이다). **라틴 둘째 · 아르헨티나 첫 회사다.** **⭐⭐ 첫 사이클에 연표가 섰다** — **1999**(저장소 하나에 개발자 200명 · 단일 Oracle · 주 1회 배포 · 코드 프리즈) → **2010** MeliCloud(마이크로서비스 · 인스턴스 17,500 · 하루 1,400 인스턴스 배포) → **2015** Fury(지금). **⭐⭐ 2010년대의 대가를 회사가 이름 붙인다** — 마이크로서비스로 간 뒤가 *"chaotic freedom"* 이었고 팀이 제품 개선 대신 운영 문제 해결에 시간을 썼다. Fury 는 그 반작용이다. **⭐⭐ 세 기능을 꿰는 축은 '남의 코드를 안 건드린다'** — 마이크로서비스 3만 개와 공개 API 계약이 모든 선택의 첫 관문이다. FaaS 를 버린 이유도(*"considerable rework on our development teams"*), 셀에 라우팅 키를 안 넣은 이유도(*"adding a routing key would have triggered a cross-organizational migration — one far more disruptive than the architectural change we were trying to implement"*) 같다. **⭐⭐ 그래서 나온 것이 브로드캐스트 게이트웨이다** — 회사가 완벽하지 않다고 먼저 말한다: *"It's not the perfect architecture — broadcasting requests adds overhead — but it provided something more valuable: a safe migration path."* 새 데이터는 **셀별 배타적 ID 범위**로 보내 ID 모양을 안 바꾸고도 결정적 라우팅을 얻는다. **⭐ 반대 방향의 결정도 있다 — 의도적 모놀리스.** 재고 도메인이 극저지연·고가용성·강한 일관성을 요구해 쪼개지 않고 주위만 셀로 감쌌다: *"the key wasn't monolith versus microservices, but choosing the architecture the business needed."* **⭐ 버린 이유를 일곱 개 적는다** — AWS Batch(예측 불가 버스트) · Lambda(15분 제한 + 3만 개 리팩터링) · ECS(멀티클라우드 유연성) · Cloud Run(당시 사이드카 미지원) · Anthos(운영 복잡도) · Knative(기존 아키텍처와 충돌) · Nomad(보조 도구 필요 + 관리형 클러스터 없음). 교훈에 **`Do not buy the buzz`** 가 있다. **⭐ 고른 것을 끝으로 두지 않는다** — 다른 오케스트레이터로 최소 혼란으로 옮길 수 있게 설계했다며 *"we're in a state of Continuous Beta"* 라 맺는다. **수치** — 엔지니어 15,000명 이상 · 마이크로서비스 30,000개 · 인스턴스 100,000개 · 저장소 26,000곳(품질 검증 7종) · 셀 이전 수십 TB 로 **p95/p99 약 70% 감소** · 복제 일관성 100ms 미만 · 평가에 약 6개월. **⚠️ 매출·사업부별 비중을 확인하지 못했다** — 기술 블로그만 읽었다. **상장사라 IR 을 열면 채울 수 있다.** **⚠️ 기능 단위 연표(`history`)는 세 번 다 못 세웠다** — 쿠버네티스 전환 시점도, 단일 MySQL 의 시작 연도도 글에 없다. **⚠️ 본문은 Medium 이라 브라우저(`get_page_text`)로만 읽힌다.** **⚠️ Fury 연작에 안 읽은 편이 있다** — 트래픽 보안 · 비용 최적화 · 멀티클라우드 전략.

- **Bolt** (EU/에스토니아 · 모빌리티) — 도메인 3개 · 기능 3개(`checkpoint-back-to-simple` 설정으로 다 되게 만들려다 되돌아온다 · `psp-reconciliation` 결제대행사마다 다른 보고서를 한 모양으로 만들고 은행 명세와 맞춰 본다 · `one-engine-one-dialect` 쓰는 엔진과 읽는 엔진이 달라 생긴 틈을 없앤다). **⭐⭐ 이 회사는 실패를 세 번 적는다** — 설정 주도 프레임워크(*"Ironically, the 'no-engineer config' idea had increased complexity"*) · 정규식 자리표시자(*"silently broke translations in certain cases"*) · LLM 변환(*"hallucinated, making up function names, introducing illogical errors, and reordering joins"*, **모델을 Opus 4/GPT-5 로 올려도 그대로**). **⭐⭐ 전부를 부정하지 않고 자리를 가린다** — 규칙 설정화는 *"a significant win"*, 생애주기 설정화는 *"backfired"*. 결론이 *"Flexibility is powerful — but only when applied to the right place."* **⚠️ 다만 어느 자리가 옳은지 가리는 방법은 안 적는다.** **⭐⭐ 복잡함이 느는 것은 안에서 안 보인다** — 알아챈 계기가 *"Returning to the system after a break, we realised"* 였다. **⭐ 논쟁을 반복으로 끝냈다** — 밑에서 올라온 POC 에 엔진 소유 팀이 회의적이었고(*"sceptical, and understandably so"*), **가장 무거운 워크로드에서 같은 실험을 한 달 더 돌리자** 논의가 *"Should we?"* 에서 *"How do we implement it?"* 으로 바뀌었다. **⭐ 읽히게 만드는 일과 옳게 만드는 일을 갈랐다** — 원본은 손대지 않고(중복도 그대로) 파싱 때 모든 열을 문자열로 강제하며 정리는 전부 하류에서. **⭐ 연표를 하나 세웠다** — 2021년 설계한 두 엔진 구조(Spark 쓰기 + Presto 읽기)가 2025년 2월 POC → 11월 완료로 닫혔다. 그 구조가 감수하던 것도 회사가 적는다: *"Tuning the layout to suit one engine meant a worse layout for the other."* **수치** — 50개국 이상 · 검문 약 60개를 8년에 · 분석 데이터 32PB · 쿼리 월 1000만 · 사용자 3,000명 이상 · 피크에 지표가 4~7배 · POC 65%/36% → 재현 30%/25% → 최종 **45% 빠르고 40% 저렴(7자리 절감)** · 엔지니어 1명→6명, 스크립트 500줄→3,000줄. **⚠️ 사기 검문에는 성과 수치가 하나도 없다**(탐지율·오탐률·지연 전부) — 이 글이 재는 것은 사기가 아니라 **엔지니어의 인지 부하**다. **⚠️ 결제 대사에도 규모 수치가 없다**(PSP 수·대사율·건수). **⚠️ 매출 비공개.** **⚠️ 사기 검문의 네 단계에 연도가 없어 `eras` 는 비웠다.** **⚠️ 본문은 브라우저(`get_page_text`)로만 온다.**

- **Kraken Technologies** (EU/UK · 기타 — 에너지) — 도메인 3개 · 기능 3개(`ship-100-a-day` 승인 하나로 하루 백 번을 스물다섯 나라 환경에 내보낸다 · `types-after-the-fact` 이미 커진 코드에 타입을 뒤늦게, 만지는 것부터 입힌다 · `each-client-its-own-pipeline` 고객사 환경 스물다섯을 각자 돌게 하고, 바닥은 도는 채로 간다). **에너지 축 첫 회사다.** **⭐⭐ 축은 순서다 — 쪼개지 않기로 한 것이 먼저이고 나머지는 전부 그 값이다.** 10만 개 테스트도, 2.5년짜리 타입 작업도, Import Linter 도 한 덩어리를 유지하려고 낸 값이다. **⭐⭐ 코드베이스가 2년에 3.7배로 자란다** — 400만(2024-01) → 600만(2024-08) → 900만(2025-02) → 1500만 가까이(2026-03). **이 속도로 자라는데 쪼개지 않는다.** **⭐⭐ 두 기능이 정면으로 부딪힌다** — 하루 100번 넘게 내보내는데 *"the slowest thing in our CI pipeline"* 이 mypy 다. 그런데 `follow_imports` 를 `silent` 로 낮추지 않는다(*"We don't use it at Kraken (yet)"*) — **빠짐없음을 사고 속도를 내줬다.** **⭐⭐ 되돌리지 않기로 한 결정이 나머지를 정한다** — `fix forward` 를 기본으로 두고 롤백 대신 환경 pinning 으로 확산만 막는다. 그래서 **모든 DB 마이그레이션이 앞뒤 호환이어야 하고** 한 변경이 여러 배포로 쪼개진다. **⭐ 사업 구조가 타입 문제로 나타난다** — 고객사마다 추상 모델을 확장하므로 추상 모델 참조가 **가능한 모든 구체 모델의 유니온**이 되고, 그걸 풀려고 플러그인이 **앱을 띄워 런타임 인트로스펙션을 한다**(정적으로 보려고 한 번 살려 보는 역설). **⭐ 자기 구멍을 그대로 적는다** — 테스트 환경이 *"not particularly representative of production"* · 안 쓰는 플래그가 *"Easy to let unused flags languish"* · **암묵적 머지 충돌은 도구로도 안 없어진다.** **⭐ 회고 한 줄이 값지다** — Black 일괄 적용은 *"much harder to do now that the codebase has grown"*, **일괄 변경의 창은 코드가 작을 때만 열린다.** **⭐ 2016 → 지금의 세대 교체가 확인된다** — ELB 헬스체크·순차 배포·Consul·통짜 워커가 네 곳에서 한꺼번에 막혔고(Terraform 동시성 · 마이그레이션 중 **Celery 용량 0** · *"Bad data in Consul could crash an entire environment"* · 큐별 확장 불가) 환경별 ArgoCD 로 옮겼다. **수치** — 하루 100회 이상 배포 · 환경 25곳 이상 · 10개국 이상 · 배포 한 바퀴 30분 미만 · 테스트 10만 개 이상 · 개발자 500명 이상 · 계정 9천만 이상 · 하루 15GWh · 메시지 하루 800만 건 정점(이전 분당 34만). **⚠️ Octopus Energy 와의 관계를 1차 문장으로 못 찾았다** — 제품 사이트가 고객사(case study)로만 적는다. **⚠️ 과금·가격·매출 비공개.** **⚠️ 연표(eras)는 못 썼다** — 다만 블로그가 2015년부터 있어 재료가 남아 있다.

- **Nubank** (기타 BR · 핀테크) — 도메인 3개 · 기능 3개(`one-gateway-many-countries` 나라마다 배선을 새로 깔던 일을 게이트웨이 하나 뒤로 감춘다 · `precompute-on-write` 읽을 때 계산하지 않으려고 쓸 때 미리 접어 둔다 · `agents-that-act` 상담이 아니라 조작을 시키려고 프롬프트를 사람 손에서 뗀다). **라틴아메리카 첫 회사다.** **⭐⭐ 축은 하나로 모인다 — 지점이 없으므로 소프트웨어가 지점이다.** 지연 100ms 가 창구 대기줄이고, 나라를 넘는 일은 창구를 여는 게 아니라 그 나라 금융망에 배선을 까는 일이며, 1억 3천만 명의 상담은 사람으로 못 채워 에이전트가 조작까지 한다. **⭐⭐ 무엇을 포기할지 먼저 정했다** — *"Eventual consistency was acceptable within defined bounds, but unpredictable latency was not."* **⭐⭐ 고칠 수 없는 것은 피해 간다** — 꼬리 지연의 원인이 자기 코드가 아니어서(JVM 예열·Spot 인스턴스 회수) 고치는 대신 임계 경로에서 뺐다. **⚠️ 다만 폴백 경로는 여전히 그 위를 지나간다**(이 사이트의 재구성). **⭐ 손쉬운 수를 명시적으로 버린다** — *"Adding a passive cache in front of the existing flow would not fundamentally solve the issue."* **⭐ 게이트웨이가 파는 것은 성능이 아니라 무지다** — *"software engineers are no longer required to understand the intricate networking protocols or disparate standards."* **⭐⭐ 모델이 좋아지는 것이 위험인 구조** — *"smarter models assume a lot less"* 라 업그레이드마다 프롬프트를 다시 최적화해야 한다. **수치** — P90 1200→280ms(76%) · 기한 360ms · five nines · 복구 창 40분→5분 미만(87%) · 개통 50% · 맞춤 작업 70% · MTTI 50%. **⚠️ 같은 회사인데 글마다 결이 갈린다** — 지연 편과 에이전트 편은 대가를 직접 적는데 **FinConnect 편은 개선 수치 다섯에 잃은 것이 한 줄도 없어** 결정 7개가 전부 재구성이 됐다. **후보 조사에서 읽은 한 편이 회사 전체를 대표하지 않는다.** **⚠️ IR 을 못 읽는다**(`international.nubank.com.br` 403 · `investors.nu` 인증서 만료) — 수익 3갈래 비중이 `inferred` 이고 3자 매체끼리 숫자가 갈린다(2026 2분기 매출 55억 vs 59억 달러). **⚠️ Clojure·Datomic 의 실물을 끝내 못 봤다** — 블로그의 Clojure 글 **두 편이 다 컨퍼런스 참관기**였다. 이 회사의 가장 큰 차별점일 텐데 **회사 블로그에 근거가 없다.** **⚠️ 에이전트 편에 성과 수치가 하나도 없다**(해결률·정확도·비용 전부). **⚠️ 연표는 못 썼다.**

- **Oxide Computer** (US · 기타 — 서버·하드웨어) — 도메인 2개 · 기능 2개(`service-processor` 랙의 모든 층을 자기가 만든다 · `jumbo-frames-path` 프레임을 키우려고 층마다 박힌 1500을 찾아낸다). **⭐⭐ 이 회사의 출발점은 기술이 아니라 벤더에 티켓을 여는 일이다** — 펌웨어부터 컨트롤 플레인까지 한 벌로 만들어 파는 이유가 그것이고, 실제로 점보 프레임 시제품에서 **가상 NIC 의 인터럽트 문제를 출시 전에 직접 고쳤다**(벤더 드라이버였다면 티켓을 여는 자리다). **⭐⭐ MTU 를 올리는 일이 설정 변경이 아니었다** — xde 드라이버와 **OPTE 의 라우터 광고 생성기 둘 다**에 1500이 박혀 있었고(*"that generator hardcoded 1500 too"*), 게스트는 virtio 와 라우터 광고 **두 경로로** 값을 배우므로 한쪽만 고치면 서로 다른 값을 본다. **⭐ 지금 쓸 크기를 줄여 나중을 샀다** — 흔한 9000 대신 **8500**(500 예비)을 고르며 *"it is easy to grow later and very hard to shrink once customers build expectations around it."* **⭐ 업계 관행을 이유와 함께 버린다** — *"MTU is a property of a path, not of a port."* **⭐ 기대 관리를 회사가 먼저 한다** — *"jumbo frames are not a network go-fast button"*, 실제로 내부 VPC 는 **+6%**(52.44→55.73Gbps)인데 외부는 **+324%**(7.70→32.67Gbps). **수치** — 단일 VM 쌍 천장 약 60Gbps(스트림 32·64·128 다 같음) · 슬레드 합산 약 90Gbps · IPv4 34.5 대 IPv6 34.9. **⚠️ 자료의 성격이 등급을 갈랐다** — 설계 글(`hubris-and-humility`)은 고른 것만 적어 대가가 `inferred` 가 됐고, **사고 회고(`cosmo-sp`)와 성능 회고(`performance-has-layers`)에서만** `confirmed` 가 나왔다. **⚠️ 매출·출하 대수·가격이 전부 비공개다.** **⚠️ 연표를 못 썼다** — 연도가 붙은 회고를 찾지 못했다. **⚠️ 컨트롤 플레인(Nexus)·하이퍼바이저·스토리지 층은 아직 안 팠다.**

- **Fly.io** (US · SaaS) — 도메인 2개 · 기능 2개(`sprite-create` 1~2초에 뜨는 컴퓨터 만들기 · `corrosion-state-sync` 합의 없이 라우팅 표 퍼뜨리기). **⭐⭐ 빠르게 만드는 방법이 더하는 것이 아니라 버리는 것이었다** — 사용자용 컨테이너·로컬 NVMe·호스트 오케스트레이션 셋을 없애 `create` 를 1분에서 1~2초로 줄였고, 그 대가를 회사가 하나씩 적는다(자기 이미지를 못 쓴다 · *"the performance isn't adequate for a hot Postgres node in production"* · 밀리초 응답을 요구하는 워크로드와 어긋난다). **⭐⭐ 실패를 가장 많이 적는 회사다** — Corrosion 편에서 **스스로 설계 실수를 인정한다**: *"In retrospect, our Corrosion rollout repeated a mistake we made with Consul: we built a single global state domain."* 여기에 RwLock 데드락(몇 초 만에 전 프록시 잠김) · nullable 컬럼 backfill(*"kryptonite to large Corrosion tables"*) · 백오프 루프가 Corrosion 쓰기를 불러 *"saturating our uplinks almost everywhere"* 까지 셋을 더 적는다. **⭐ 두 기능이 한 문장으로 이어진다** — 1~2초에 뜨는 컴퓨터가 성립하려면 공개 URL 전파가 합의를 기다리면 안 된다. **⭐ 연표는 2023년 하나** — `January of 2023` 은 Nomad, `December of 2023` 은 flyd 라고 글이 직접 못 박는다. **⚠️ 수치가 얇다** — 매출 비공개, Sprites·Corrosion 규모 수치가 거의 없어 `business.metrics` 를 시간·비용 위주로만 채웠다. **⚠️ Nomad 이전 구조의 시작 연도가 없어**(`For the year following our launch`) 그 시기는 세우지 않고 `context` 로 옮겼다.

- **PayFit** (EU · SaaS) — 도메인 1개 · 기능 1개(`name-it-before-you-cut` 자르기 전에 이름부터 맞춘다). **⭐⭐ 이 회사의 답은 코드가 아니라 이름이었다** — 급여 명세가 전에는 *"considered as an internal implementation detail"* 이었고, **무엇을 '내부 상세' 라 부르는 순간 그것은 경계 밖이 된다.** **⭐ 모델링을 엔지니어만 하지 않는다**(영업·고객지원·제품·디자인이 여러 나라에서 모였다). **⭐ JetLang 은 강점이자 짐이다** — 노동법을 담으려고 만든 로우코드가 풀코드와 동거하며 **책임을 흐리고 진실의 원천을 여럿으로 만들었다.** **규모** — 고객 10,000곳 · 종업원 200,000명 · 3개국 · 2023년 앱 성능 30퍼센트 개선. **⚠️ 이 회사의 글에는 대가가 거의 없다** — 네 편 중 대가를 적은 것은 DDD 편 하나뿐이고 그마저 성과 수치가 없다. **⚠️ 코드나 시스템이 어떻게 됐는지는 끝내 안 나온다.** **⚠️ JetLang 본문은 못 찾았다**(356 에서 WebSearch 예산 소진). **⚠️ 블로그가 얇고 2024-07 에서 멈췄다.**

- **bol** (EU · 커머스) — 도메인 2개 · 기능 2개(`move-four-years-of-past` 과거를 두고 갈 수 없어 사 년 어치를 옮긴다 · `slow-down-to-go-fast` 빨리 가려다 느려지는 자리에서 먼저 멈춘다). **⭐⭐ 같은 회사 안에서 검증이 정반대다** — 데이터 사이언스 쪽은 단계마다 품질을 보는데 **3TB 이관에는 검증 이야기가 아예 없다**(⚠️ 다른 팀의 글이라 방침으로 읽지는 않았다). **⭐ 같은 판단을 두 번 했다** — 중개 앱을 2031년까지 유지하는 안을 버렸고 *"there's nothing as permanent as a temporary solution"* 라 적는다. **미루는 쪽을 두 번 다 거부했는데 둘 다 값을 숫자로 안 적는다.** **⭐⭐ 무엇을 쓸지 고를 때 사내 사용량이 결정적이다** — ORM 조사에서 네 번 다 그랬고, 이관 팀은 *"nobody in the company had ever tackled something quite like this before"* 였다. **아는 사람이 있느냐가 반복되는 기준으로 보인다.** **⭐ 실패는 아낌없이 적는데 성과는 얇게 적는다.** **⚠️ 두 도메인 다 한 편씩만 읽고 닫았다** — 353 에서 세 편을 더 열었으나 셋 다 기준 미달(튜토리얼 · 소개글 · 실행 안 한 해커톤 평가). **⚠️ 블로그 최신이 2024-11-07.**

- **SmartHR** (JP · SaaS) — 도메인 2개 · 기능 3개(`when-a-rule-is-not-enough` 규칙으로 그은 경계가 못 하는 것이 있다 · `share-a-few-connections` 놀고 있는 접속을 걷어내고 몇 개를 돌려 쓴다 · `measure-before-the-season` 계절이 오기 전에 재고 재는 일을 넘긴다). **⭐⭐ 두 도메인이 같은 단일 실패점에 정반대로 답한다** — 인증은 **떼어내서 격리**하려 하고 가장 큰 Rails 앱은 **그대로 두고 앞에 세워 버틴다.** **버티는 쪽이 훨씬 빨리 끝났다**(단기 완료가 조건이라 GKE 대신 Compute Engine 을 골랐다). **⭐⭐ 데이터베이스에서 두 번 막혔는데 한 번은 늦었고 한 번은 이르다** — 접속 수는 장애 뒤, CPU 는 정점 전. **⭐ 자기 방법의 한계를 적는다** — Packwerk 가 새 영역에서는 됐는데 얽힌 인증에서는 안 됐다고 쓴다. **⭐ 자기가 고른 것이 나중에 틀린 것도 적는다** — PgCat 은 개발이 멈췄고 이미 관리형으로 옮겼다. **⭐ '언제 손을 떼는가' 를 설계 대상으로 삼는다**(EXIT 로드맵). **⚠️ 세 이야기가 다 진행 중이다** — DB 는 아직 함께 쓰고 인증 리프트는 시작 단계다. **⚠️ 블로그의 결이 넓어 사내 행사·커리어 글이 절반쯤 섞여 있다.** **⭐⭐ freee 와 비교 문서 재료** — freee 가 후회로 적은 순서를 실제로 밟아 보고 **그것만으론 부족하다**는 결론을 낸다.

- **freee** (JP · SaaS) — 도메인 2개 · 기능 4개(`refactor-before-you-cut` 떼어내기 전에 옛것을 정리했어야 했다 · `swap-without-anyone-noticing` 아무도 모르게 갈아 끼우고 한 번만 멈춘다 · `swap-the-floor-before-the-peak` 정점이 오기 전에 바닥을 갈아 끼운다 · `send-only-the-writes` 읽기를 옆으로 보내고 쓰기만 원래 자리로 보낸다). **⭐⭐ 두 도메인이 같은 아픔의 두 층이다** — 회계 DB 의 **바닥을 갈아 끼우는 데 석 달**, 그 **위에 얽힌 인증 기반을 떼어내는 데 1,454일**. **⭐⭐ 한 번에 다 넘기는 법이 없다** — 제품마다 켜고 끄고(회계를 마지막에), 되돌릴 창을 이삼 주 열어 두고, 5→50→100 퍼센트로 연다. **⭐⭐ 되돌릴 길이 서지 않으면 안 넘긴다** — 2020년엔 마스터 승격을 직접 만들었고 2023년엔 Blue/Green 을 *"切り戻し手法を確立できない"* 이유로 보류했다. **⭐ 후회를 적고 되먹임 고리까지 짚는다**(적게 내보내니 돌아볼 일이 적었고, 그러니 고칠 것이 안 나왔다). **⭐ 같은 프로젝트를 두 글이 다른 각도로 다룬다** — 둘을 겹쳐야 4년의 모양이 보인다. **⚠️ 그런데 결이 고르지 않다** — 굵은 이야기는 DBRE·인증 쪽에 몰려 있고 **QA 95편 중 두 편을 열어 보니 둘 다 수치도 버린 대안도 없었다**(343). **⭐⭐ SmartHR 과 정반대 순서다** — freee 가 후회로 적은 *"旧機能のリファクタはマイクロサービス化の前に着手すべし"* 가 SmartHR 이 실제로 한 일이다. **비교 문서 재료.**

- **Sansan** (JP · SaaS) — 도메인 5개 · 기능 6개(`rebind-what-was-attached` 저장소 이관 · `narrow-to-win` 명함 전용 인식 · `measure-the-mixed-line` 공정 실적 · `paper-does-not-undo` 실물 원본 · `layer-by-layer-async` Swift Concurrency · `coordinator-in-between` Jetpack Compose). **⭐⭐ 다섯 도메인이 같은 회사의 다섯 층이다** — 개발 환경 · 인식 · 공정 실적 · **실물** · 십 년 된 앱. **대부분의 회사는 소프트웨어 안에서 끝나는데 여기는 우편물이 도착하고 사람이 옮긴다.** **⭐ 글의 두께가 층마다 다르다** — 개발 환경과 앱 쪽은 대가를 아낌없이 적고(CI/CD 가 이관보다 손이 갔다 · 병합 충돌 걱정은 기우였다 · **AI 개선에 기대는 것이 불확실하다는 인정**), 인식 쪽은 성과 중심이며(NineOCR 편은 버린 대안도 한계도 0), Digitization 쪽은 대담이 많다. **⭐ 자기가 만든 것을 안 쓴다고 적는다**(초해상, 30% 이상 올리는데도 뺐다 — 입력이 좋아져서). **⚠️ 그런데 가장 아프다고 말한 항목(이메일·전화)의 정확도는 공개하지 않는다.** **⭐⭐ 다섯 번 다 점진을 골랐는데 버린 이유가 매번 달랐다.**

- **Freshworks** (IN · SaaS) — 도메인 3개 · 기능 3개(`split-then-cut` 앞에서 나누고 뒤에서 자른다 · `rename-before-push` 밀기 직전에 이름을 갈아 끼운다 · `know-both-versions` 두 판을 동시에 아는 코드로 만든다). **⭐ 대가를 적는 정도가 글마다 크게 갈린다** — 고가용성 편 **다섯**(Newrelic explain 쿼리가 서킷 브레이커 감시를 방해해 껐다) · 업그레이드 편 **다섯**(실제로 터진 사고 셋) · HAProxy 편 **두 줄** · Sidekiq 편 **없음**. **⭐ 그런데 대가를 가장 많이 적은 두 편이 결과의 근거는 가장 적게 적는다** — 무중단·회귀 0 이라면서 트래픽도 오류율도 전환 기간도 없다. **⚠️ 블로그가 네 경로에 흩어져 있고 목록 페이지가 안 열리며 살아 있는 글과 죽은 글이 섞여 있다** — 글 전체 목록을 끝내 확인하지 못했다. **⚠️ 사업의 무게(EX ARR +24% · Freddy AI 71%)와 글의 무게(CX 쪽 Rails 운영)가 어긋난다.**

- **Paytm** (IN · 핀테크) — 도메인 4개 · 기능 2개(`leave-what-costs-more` 다 옮기지 않기로 정한다 · `own-the-measuring` 재는 일을 직접 떠안는다). **⚠️ 도메인 넷 중 둘은 기능 없이 남았다** — 블로그 열 편을 전부 읽었는데 **의사결정과 대가를 함께 적은 글이 둘뿐**이고 나머지는 정책 안내문·사용자 안내문·수치만 있는 발표문이다. **⭐⭐ 그 두꺼운 두 편이 서로 반대다** — 이관 글은 **대가를 아낌없이 적는데 검증이 한 문장**이고(50억 개를 옮기고 개수 대조도 체크섬도 없다), 관측 글은 **수치를 앞세우는데**(40개월 100% 가용성 · 비용 2% 미만 · 한 사람이 운영) **그 100% 를 어떻게 쟀는지 안 적는다.** **⭐ 없는 도구는 파이썬으로 짧게 만들어 붙인다**(접근 로그 분석기 · 카디널리티 감시기). **⚠️ 사업의 심장(가맹점 대출 중개, FY26 1분기 +100%)을 다루는 글이 한 편도 없고 블로그가 2023-04 에서 멈췄다.**

- **Grab** (SG · 모빌리티) — 도메인 5개 · 기능 5개. **⭐ 같은 회사 안에서 재는 대상이 갈린다** — 앞의 셋(이상거래 카운터 저장소 · 데이터 레이크 · 배차 실험)은 **수치로 가득한 규모·비용 이야기**(p99 50% 개선 · 질의 70초→6초 · S3 비용 95% 절감)인데, **에이전트 계열 셋은 각각 신뢰(Palana) · 준비 시간(LLM-Kit) · 일의 결과(SOP)를 잰다.** **⭐⭐ 그리고 세 편이 서로를 한 번도 안 부른다** — **만드는 쪽은 느슨하게**(강제하지 않는 프레임워크), **가두는 쪽은 빡빡하게**(기본 거부와 프록시 경유 자격), **모는 쪽은 자유를 없앤다**(SOP 트리). **⚠️ 버린 대안의 이름이 자주 빠지는 버릇이 에이전트 계열에서도 이어진다** — SOP 편은 수치가 가장 강한데 **버린 대안도 한계도 0줄**이다.

- **kakao** (KR · 메시징) — 도메인 7개 · 기능 6개. **hold 를 유지한 채 닫았다**(311) — 남은 `동기화·다중 기기` 는 공개 1차 자료를 **두 번 찾아 두 번 다 없었고** `tech.kakao.com` 본문이 안 열린다. 새 발표가 나오면 `hold_reason` 을 지우고 다시 판다.
- **Roblox** (US · 게임) — 도메인 4개 · 기능 3개. **hold 를 유지한 채 닫았다**(311) — 남은 `콘텐츠 저장·전송` 은 **공개 1차 자료가 없다**(CDN 은 커뮤니티 포럼 글뿐, 하이브리드 아키텍처 글은 회사 스스로 아직 실시간으로 안 돈다고 밝히는 발표문). 새 자료가 나오면 다시 판다.

- **Cybozu (サイボウズ)** (JP · SaaS) — 도메인 2개 · 기능 2개. **⭐ 20년 넘은 제품을 아직 팔기 때문에 멈추지 않고 계속 옮겨야 하는 회사** — 새로 만드는 이야기가 아니라 **옛 가정을 지키면서 새 바닥에 올리는 이야기**다. 파일 잠금 때문에 **StatefulSet 을 버리고**(*"リリースのたびにダウンタイムが発生する"*) 파드를 한 노드에 묶었다 — **가용성을 얻고 분산을 내줬다.** **⭐ 관리 대상이 너무 많으면 저장을 없앤다** — 테넌트 **4만 건 초과**라 설정 대신 주소에서 발급자를 조립해 관리 대상을 0개로 만들고, **그 값을 사용자가 매번 주소를 입력하며 치른다고 스스로 적는다.** **⭐ 문서를 믿지 않고 커널까지 내려가 재 본다.** **⚠️ 글의 두께가 크게 다르다** — 여섯 편을 읽고 둘만 기능이 됐다. **목록이 아니라 본문으로만 판단할 수 있는 회사다.**

- **Meituan (美团)** (CN · 커머스) — 도메인 4개 · 기능 4개. **⭐⭐⭐ 판단을 믿는 대신 확인할 수 있는 형태를 만드는 회사** — 네 도메인에서 네 번 같은 모양이 나온다(의미 유사도를 **10칸 버킷 번호**로 · 애매한 기준을 **예·아니오로 이진화**해 일치율 85~90% 문턱 · **제출 전 AI 감사**를 통과해야 사람 리뷰로 · **샌드박스 실행 결과**만 학습 데이터로). **대가도 같은 방향으로 남는다 — 확인할 수 있는 것만 다뤄진다.** **⭐⭐ 기준을 하나로 만드는 일이 자동화보다 먼저다**(*"1个'独裁者'好过10个'民主者'"* · *"先'人人对齐'，再'人机对齐'"* — 회사가 두 일이 같은 논리라고 스스로 적는다). **⭐ 결론에 유효 기간을 붙인다**(*"这一结论有阶段局限性"*). **⚠️ 그리고 '푸는 글' 과 '내놓는 글' 사이에서 솔직함이 갈린다** — 평가 방법론과 EvoCUA 는 한계를 다섯·넷 적는데 벤치마크·모델 발표문 셋은 **자기 한계가 0줄**이다. **🔴 옛 글을 내리는 블로그라 2022~2025-05 자료는 못 읽었다.**

- **Wix** (기타/이스라엘 · SaaS) — 도메인 3개 · 기능 5개. **⭐⭐ 같은 문제를 두 층에서 정반대로 푼 회사** — 무중단 DB 이관을 인프라 팀은 *"no code changes"* 로, 제품 팀은 읽기마다 상태를 묻는 방식으로 풀었고 **되돌리기도 정반대**(쓰기를 넘기면 끝 vs 마지막까지 옛 쪽에도 쓴다). **⭐⭐ 모델을 손대지 않는다 — 네 편에서 확인**(접근 제한 · 행동 제한 · 환경 정비 · 통과 조건. **대가가 같은 방향으로 남는다 — 검사할 수 있는 것만 검사된다**). **⭐ 대가를 적는 정도가 글마다 크게 다르다** — *"We don't have a tidy case study with a before/after graph"* 라고 먼저 적는 글이 있는가 하면 실패가 한 줄도 없는 글도 있다.

- **monday.com** (기타/이스라엘 · SaaS) — 도메인 4개 · 기능 5개. **⭐⭐ 같은 시스템을 두 목소리로 쓴 회사** — 만든 사람 쪽은 **8 person-years → 6 person-months**(성공률·롤백률 없음), 에이전트 1인칭 쪽은 **한계 다섯과 밤 11시의 사고**. **⭐⭐ 크리티컬 패스에는 미리 가져다 둔다** — 번호도 권한도 같은 답(**P50 240→6ms**). **막힌 제약을 우회하는 대신 그 제약이 안 걸리는 자리로 옮긴다.** **⚠️ 글마다 숫자의 성격과 대가의 밀도가 갈린다** — 관측 편의 *"paradise"* 문장 vs **권한 편 0줄**.

- **Adevinta** (EU · 커머스/분류광고) — 도메인 3개 · 기능 6개. **남이 만든 것을 그대로 받아들이지 않는 회사** — AI 코딩 도구를 **엔지니어 77명의 실제 업무 165건**으로 재고 오차 원인 다섯을 부록에 적으며, PaddleOCR 은 **파라미터 105개 중 70개가 무시되던 것**을 20개로 줄여 뜯어 썼다. **인프라에 대한 사실을 인프라로 승격시킨다**(계정 생성을 예산 승인 흐름에). **⚠️ 같은 블로그 안에서 실패를 쓰는 글과 안 쓰는 글이 갈린다.** 매출은 **2024 상장폐지로 공개되지 않는다.**

- **Snap** (US · 소셜/카메라·AR) — 도메인 2개 · 기능 5개. AI 개발 도구 3부작(`code-review-agent` · `agentic-code-search`)과 SPECS/AR(`mutual-gaze-align` · `spatial-benchmark` · `near-far-targeting`). **자를 어떻게 세울지가 반복해서 문제가 되는 회사** — 골든셋을 만들고 범위를 밝히거나, 못 잰다고 적거나, 자를 만들고 결과가 나쁘다고 적는다. **설계 근거로 남의 제품 동작(Claude Code 의 grep)을 든 첫 사례.**

- **컬리** (KR, 커머스/신선식품, 2026-08-27) — 도메인 5개 · 기능 5개. **47번째 회사.**
  자리: 쿠팡은 종합 익일배송, 배민은 음식 배달, Target 은 매장이 거점, Wayfair 는 큰 물건인데
  **여기는 신선식품 콜드체인이고 새벽에 문 앞에 두고 간다** — **받는 사람이 없어 사진 한 장이 배송을
  증명한다.** 그리고 **1P(직매입)에서 3PL(제3자 물류)로 넓어져** 남의 물건도 대신 받는다.
  기능 — `misdelivery-detection`(**질문을 바꿔 희소성을 피했다**: '오배송인가' 대신 '늘 보던 문 앞인가' ·
  On-device 이유 셋 · **양치기 소년 현상**) · `inbound-sync`(**재시도 24시간의 근거가 업무 데드라인** ·
  버린 대안에 이유 명시 · 멱등성은 소비자에 맡긴다) · `access-block`(**출발점이 권한이다** —
  *"개발팀에겐 nginx 접근 권한이 없습니다"* · **관리 화면 대신 구글 시트**) · `encryption-module`
  (**직접 만든 이유가 명시적** — 후보 라이브러리에 취약점 · `@Converter` 를 고른 것도 프레임워크 사정) ·
  `stream-window`(**시간이 시계가 아니라 이벤트로 흐른다** · 가짜 이벤트에 **파티션별 키**).
  ⚠️ **사업 수치를 하나도 못 찾았다** — `kurlycorp.com` DNS 없음. **하이퍼커넥트에 이어 두 번째다.**
  ⚠️ **알림을 다루는 같은 생각이 세 기능에서 반복되는데 세 글이 서로를 언급하지 않는다.**

- **하이퍼커넥트** (KR, 소셜/실시간 영상, 2026-08-27) — 도메인 3개 · 기능 4개. **46번째 회사.**
  자리: 이 사이트에 **실시간 1:1 영상 매칭이 없었다**(당근은 지역 중고거래, Discord 는 음성 커뮤니티,
  인스타그램·Slack 은 비동기). **낯선 사람을 즉시 이어 주면 누구와 이을지를 매번 시스템이 골라야 하고
  그 판단이 몇 초 안에 나와야 한다.**
  기능 — `objective-relaxation`(**가정은 AI 문제에서 일종의 기술 부채입니다** · **가정이 실제로 깨진
  기록**: DAU 를 올렸더니 *"PUR 이 떨어졌습니다"* · 버린 접근 여덟) · `stream-join`(**버린 대안 다섯** ·
  Exactly Once 를 껐더니 중복 제거가 Redis 로 밀려나 **정확성의 경계가 프레임워크 밖으로** · 300ms 에서
  3ms 미만) · `raid-recovery`(빠른 디스크와 안 사라지는 디스크를 **고르지 않고 묶었다** · LSM-tree 라
  성립한다 · 복구 **18~24시간에서 약 1시간** · **Discord 의 경험을 인용해 후보를 버린다**) ·
  `arch-migration`(**200개 넘는 마이크로서비스를 1년에** · **실제 절감액도 멈출 기준도 없다**).
  ⚠️ **제품 쪽 글은 버린 대안이 많고 수치가 없으며, 인프라 쪽은 갈린다**(ScyllaDB 는 촘촘, ARM64 는 비중만).
  ⚠️ **사업 수치를 못 찾은 채로 닫았다** — Match Group IR 에 하이퍼커넥트도 아자르도 나오지 않는다.
  ⚠️ **안 연 글** — 클러스터 이전(2020-11, 6년 전).

- **CyberAgent** (JP, 광고, 2026-08-27) — 도메인 4개 · 기능 5개. **45번째 회사.**
  자리: **이 사이트에 광고를 파는 회사가 없었다**(넷플릭스·유튜브는 미디어, 구글은 없다).
  이 회사는 **광고를 팔면서 그 광고가 실릴 미디어(ABEMA)도 직접 굴린다** — 일본의 실시간
  스트리밍이라 넷플릭스(주문형)·유튜브(UGC)와 축이 다르다. 카테고리 `광고` 를 새로 만들었다.
  기능 — `ad-pacing`(**버린 대안 셋에 이유가 각각** — 선형 차 대신 로그 비 오차 · PID 의 D 항 제거 ·
  임계값 대신 베르누이 추첨 · 축은 정확도가 아니라 **운용 비용**) · `two-tier-cache`(**버린 대안 넷 중
  셋이 "컴포넌트를 늘리지 않는다" 는 같은 이유** · TTL 을 1분과 4분으로 쪼개 **신선도 상한 5분을 유지**) ·
  `env-split-migration`(**이 회사에서 버린 대안이 가장 많은 글**인데 **롤백 서술이 한 줄도 없다** ·
  임시 부품을 절차서에 올려 철거 계획과 세트로 관리한다) · `alert-context`(회사가 이름 붙인
  *"알림의 형해화"* · 정비 시간에 끄는 흔한 답과 **반대로** 평소 꺼 두고 이벤트로 켠다) ·
  `observability-pipeline`(관리형의 **이중 과금**을 피해 직접 굴린다 · **관측 도구 자신의 로그를
  관측에서 뺀다** · 버린 쪽의 장점을 인정한 드문 자리).
  ⚠️ **글마다 밀도가 극단적이다** — 여섯 편 중 자기 수치를 낸 것은 셋뿐이고, **버린 대안의 수와
  수치의 유무가 상관이 없다.** ⚠️ **같은 시스템의 다른 층을 다루는 글들이 서로를 전혀 언급하지 않는다.**
  ⚠️ **IR 에서 세그먼트별 수치와 ABEMA 시청자 지표(WAU/MAU)를 못 찾았다.**

- **Wayfair** (US, 커머스/대형 물품, 2026-08-27) — 도메인 3개 · 기능 5개. **44번째 회사.**
  자리: 이 사이트의 커머스(Target·쿠팡·Zalando·무신사·Vinted·Mercari) 중 **크고 무겁고
  잘 깨지고 반품이 비싼 물건**이 없었다. 그래서 **물리적 상태를 판정하는 일**이 소프트웨어
  도메인이 된다. 기능 — `damage-judgment`(창고에서 상자를 분기 · 사람 라벨이 **16% 에서 갈렸다**) ·
  `beyond-taxonomy`(*"사용자의 사진을 러브시트로 분류하면 검색을 그 카테고리로만 제한한다"*) ·
  `dimension-validation`(**버린 대안에 숫자가 있는 유일한 축** — 옛 방법 정밀도 50% 미만·재현율 7%
  → **85%·70%** · 받는 쪽이 **공급업체 2만 곳**이라 지표를 고른 근거가 기술이 아니라 관계다) ·
  `resolution-choice`(**반사실이 없다** — *"다른 해결책을 골랐다면 결과가 어땠을지 우리는 모른다"* ·
  그래서 고르지 않고 좁힌다 · **Saffron 을 본문에서 링크로 거는 유일한 글**) ·
  `supplier-intervention`(**Wilma** — 단일 프롬프트 **70%** 를 버리고 작성자별로 나눠 **96%** ·
  **티켓의 약 65% 를 사람 없이 종결하는 이 회사 유일한 자동화**, 근거는 **사람 기준선 80%/90%**).
  ⚠️ **태그 목록이 서로 크게 겹친다** — 태그 총 건수를 새 재료의 양으로 읽지 않는다.

- **LinkedIn** (US, 소셜/구인·구직, 2026-08-27) — 도메인 2개 · 기능 2개. **43번째 회사.**
  자리: 이 사이트의 소셜(인스타그램·Discord·Slack·당근) 중 **구인·구직 그래프가 없었다.**
  프로필이 이력이고 연결이 곧 시장이라 **검색·랭킹의 대상이 사람과 일자리 양쪽**이다.
  기능 — `ai-code-review`(**기성 도구를 거절한 이유 셋**, 결정적인 것은 *"벤더의 모델을
  카나리로 돌릴 수 없고 두 번째 리뷰어로 페일오버할 수도 없다"* · 주 79,000+ 리뷰 ·
  채택률 63.9%) · `qa-agent`(**대가를 먼저 못 박는다** — *"환영 버그를 보고하는 자율
  에이전트는 쓸모없는 것보다 나쁘다"* · **2단계 검증, 둘 다 동의해야 보고** · 유효 버그 200+).
  **둘이 한 생각으로 읽힌다 — AI 를 갈아끼울 부품으로 둔다**(이 정리는 이 사이트의 것).
  ⚠️ **도메인 `랭킹 모델을 얼마나 빨리 다시 만들 수 있는가` 는 `hold_reason` 으로 보류**했다 —
  본문이 한 편뿐인데 **목록·분류 페이지가 WebFetch·브라우저 둘 다로 안 열려** 두 번째
  글을 찾을 길이 없다. 새 글 주소를 알게 되면 지우고 다시 판다.

- **Target** (US, 커머스/리테일 물류, 2026-08-27) — 도메인 3개 · 기능 5개. **42번째 회사.**
  자리: **매출 출하의 97.6% 가 매장 발**이다(4분기 97.4%). 쿠팡처럼 물류센터를 깐 것이 아니라
  **이미 있던 매장 1,995곳이 배송 거점**이라, 재고가 파는 곳과 보내는 곳에 동시에 있다.
  기능 — `split-shipments`(2ⁿ−1 배송 후보 · **벨 수 Bₙ** 이행안 · 계단형 비용 함수 ·
  **시간 8% 로 격차 91%**) · `inventory-placement`(**이접 제약**이 정수로 넘긴다 · 품목 친화도가
  분할을 앞에서 줄인다) · `infra-showback`(**차지백을 버렸다** · 제품 단위 · ITDP) ·
  `layout-bandits`(**A/B 와 정적 배치를 버렸다** · LinUCB · p95 25ms · $50M) ·
  `repurchase-timing`(**가장 정확한 SLRC(0.143)를 안 골랐다** — 0.131 로 학습 1300h→250h).
  **다섯이 다 '정확한 답을 포기하고 얼마에 사느냐' 로 읽힌다**(이 정리는 이 사이트의 것).
  ⚠️ 분류별 목록 URL 을 못 찾아 **첫 페이지 15편 중 9편만** 봤다(전체 약 100편).

- **Moniepoint** (NG, 핀테크, 2026-08-27) — 도메인 2개 · 기능 2개(**핵심이 아닌 것이 핵심을 흔들지
  못하게 한다** · **맞았다가 아니라 어떻게 그렇게 판단했는가를 남긴다**). **41번째 회사, 아프리카 첫 곳.**
  `NG` 를 validate.py 와 index.json 양쪽에 추가했다. `ui_map` 을 넣은 네 번째 회사.
  자리: **가용성이 기능이 아니라 상품이다** — *"0.1% 의 가용성 저하는 대시보드의 선 하나가 아니다.
  통과하지 못한 수천 건의 거래이고, 그 순간 신뢰를 잃은 수천 명의 고객이다."*
  월 TPV **$17B** · 일 결제 **2,600만 건** · 분당 API **2억** · 나이지리아 최대 머천트 어콰이어러.
  🔑 특기할 것 — ① **부가 기능을 임계 경로에서 뺀다**(저축 직접 호출을 버림: *"데모에서는 되고
  프로덕션에서는 무너진다"*) ② **읽지 않고 넣어서 중복을 판정한다**(insert-first, 판정이 발행보다 먼저)
  ③ **건강을 판정하는 장치가 가용성을 깎고 있었다**(기본 Spring Boot 헬스체크를 버림)
  ④ **핵심이면 직접 쥔다** — Kafka 는 관리형에 안 맡기고 Strimzi 로(*"Kafka 가 주변적이라면"* 관리형을 권한다)
  ⑤ **매칭이 아니라 매칭의 출처를 남긴다** — *"어느 파이프라인이 판단했고 누가 그 파이프라인을 만들었는지"*
  ⑥ **거버넌스가 인터페이스보다 먼저다** — *"거버넌스가 없으면 대화형 AI 인터페이스는 그냥 나쁜 SQL 을
  더 빨리 쓰는 챗봇이다."*
  📌 **'두 번째 글' 규칙이 여기서도 두 번 값을 했다**(217 Kafka on VMs · 218 이관 글).
  ⚠️ **비상장이라 매출·수수료율이 없고**, **사용자 수가 자료마다 다르다**(블로그 1,000만 vs 홈페이지 2,000만 계정).
  블로그가 작다 — 8편 남짓이고 `payments`·`data` 분류는 비어 있다.


- **Doximity** (US, 소셜, 2026-08-27) — 도메인 3개 · 기능 3개(**중복은 견디고 빠짐은 못 견딘다** ·
  **프로덕션에서만 보이는 것을 프로덕션에서 잰다** · **완벽해지지 않는다는 것을 전제로 만든다**).
  **40번째 회사이자 의료 첫 곳.** `ui_map` 을 넣은 세 번째 회사.
  자리: **사용자가 개인도 가맹점도 아니라 '면허' 다** — 미국 의사의 85% 이상이 회원이고,
  세는 기준이 '봤나' 가 아니라 **'했나'**(Dialer 통화 · 팩스 · 프롬프트 · PeerCheck 검토 · 온콜 · Scribe).
  FY2026 매출 **$644.9M**(+13%) · 조정 EBITDA 마진 **55.5%** · 총이익률 **89.1%**.
  🔑 특기할 것 — ① **겹침은 받고 간극은 못 받는다**(CDC 인계) ② **미루는 설계의 값은 정확성 책임이
  뷰로 옮겨 가는 것**(*"병합 전과 후에 같은 결과를 내야 한다"*) ③ **원인이 느린 코드가 아니라 캐시가
  놓인 층이었다**(Redis 4.5만 번 → 1번, p95 214초 → 69초) ④ **재는 도구가 답을 바꾼다** — 계측형은
  *"싼 것을 비싸 보이게"*, **채점 모델은 환각한다**(싼 평가 모델을 버렸다) ⑤ **완벽해지지 않는다고
  제품 소개 글에 먼저 적는다.**
  📌 **'읽는 사이클' 이 이 회사에서만 세 번 값을 했다**(212 · 213 · 214). 특히 임상 AI 도메인은
  **한 편만 봤을 때 버린 대안이 0개였는데 두 편을 더 읽으니 6개**가 나왔다.
  ⚠️ **블로그 92편 중 8편만 읽었다.** 매출 부문별 구성은 실적 발표에 없다.
  ✅ **IR 접근법을 뚫었다** — Q4 Inc 계열 IR 은 브라우저 `get_page_text` 로 표까지 전문이 온다.


- **Yelp** (US, 검색, 2026-08-27) — 도메인 3개 · 기능 3개(**안 쓰는 데이터를 알아보는 법** ·
  **제자리에서 갈아 끼운다** · **광고비가 매출인 회사의 매출 운영**). **39번째 회사.**
  **`ui_map` 을 넣은 두 번째 회사**다(토스 다음).
  자리: **재고도 거래도 자기 것이 아니다** — 소유권 주장 지점 **840만 곳 중 돈 내는 곳은 51만 곳**,
  거기서 **2026 Q2 순매출 $376M**. trivago 와 가장 가깝지만 그쪽은 가격을, 여기는 **평판을** 모은다.
  🔑 특기할 것 — ① **재는 일 자체가 비싸면 앞뒤가 안 맞는다**(CloudTrail 100만 건당 $1 을 버리고
  서버 접근 로그 → 그 원본이 하루 TiB 라 **Parquet 으로 객체 수 99.99% 감축**)
  ② **지우는 대신 마찰을 놓았다**(`Default Access Retention` — 지우지 않고 Terraform PR 승인)
  ③ **되돌릴 길의 폭이 곧 걸리는 시간이다** — 같은 회사가 두 답을 냈다(Cassandra 는 쉬운 롤백을 알고도
  버렸고, PostgreSQL→MySQL 은 사서 **거의 1년**을 썼다) ④ **DB 를 바꾼 이유가 '아는 사람 수' 였다**
  ⑤ **틀림이 조용하고 확인 기회가 월 1회다**(*"고객은 보통 월 1회만 청구서를 받는다"*).
  📌 **읽는 사이클이 두 번 값을 했다** — 209 에서 PostgreSQL 글, 210 에서 Revenue Automation 두 편.
  ⚠️ **블로그 43페이지 중 3페이지(23편)만 봤다** — 검색·ML 묶음은 통째로 안 열었다.
  IR 하위 페이지는 **JS 렌더링**이라 매출 구성을 못 받았다.


- **Mercari** (JP, 커머스, 2026-08-27) — 도메인 3개 · 기능 3개(**Exchange 추상** · **자격증명 스펙트럼** ·
  **복제하지 않고 나라를 늘린다**). **38번째 회사.** 사업 수치를 **IR 데이터시트 CSV** 로 받았다
  (PDF CMap 을 풀 필요가 없었다 — 일본 상장사는 `pdf.irpocket.com/....csv` 로 분기 수치를 통째로 준다).
  🔑 특기할 것 — ① **기술 부채가 회계로 샜다**(*"경리 팀이 특정 자금 이동이 어떤 API 를 썼는지까지 알아야 할 수도 있다"*)
  ② **보안을 높이려고 넣은 화면이 탈취 경로가 됐다**(로그인 직후 패스키 등록 유도 → 공격자가 악용 → 중단)
  ③ **복제하지 않고 늘린다** — 나라별 포크·완전 재구축·마이크로서비스 증식을 셋 다 버리고
  **차원을 더했다**(코드에는 모듈, 원장에는 Region). ④ **테이크레이트가 일본 10.1% vs 미국 32.6%** 인데 이유가 1차 자료에 없다.
  📌 **이 회사부터 기능에 화면 도해(`ui`)를 넣기 시작했다.**
  ⚠️ 스펙트럼 색 이름(Red/Green/Blue)과 대만·홍콩 출시 시점은 **글마다 어긋나 확정하지 못했다** — 단정하지 않고 남겼다.


- **Careem** (AE, 모빌리티, 2026-08-22) — 도메인 2개(하나는 보류) · 기능 1개(**인프라 비용이 새는 자리**).
  **37번째 회사, 중동 첫 곳.** `AE` 를 validate.py COUNTRIES 와 index.json countries 에 추가했다.
  business_model 에 **회사 패턴을 적지 않았다** — 기능이 하나뿐이라 '세 기능에 걸친 패턴' 을 쓸 근거가 없다.
  🔑 특기할 것 — ① **지우면 가벼워질 줄 알았는데 더 무거워졌다**(삭제는 예약이라 언두 로그 5.7TB · HLL 58.7억,
  지연 20ms vs SLA 1ms → DMS Serverless 로 옮겨 담아 270TB→78TB · 0.54ms)
  ② **버린 대안을 시간으로 계산했다**(*"58.7억에서 10만으로 약 3.5개월"*) — 일정과 비교할 수 있어야 버릴 수 있다
  ③ **가장 느린 코덱이 지표 하나에서는 가장 효율적으로 보인다**(Gzip 의 낮은 CPU 는 *"프로듀서가 놀아서"* 생긴 착시).
  ⚠️ **소유 구조·매출·진출 국가는 끝내 못 찾았다.** `화면을 서버가 정한다` 는 **수치가 하나도 없어 보류(hold_reason)**.
  📌 **여기서 얻은 규칙** — 엔지니어링 글이 **여섯 편뿐인 회사에 도메인 셋은 과했다.**
  개설 사이클에서 **도메인 수를 정하기 전에 글이 몇 편인지부터 센다.**

- **TigerBeetle** (기타, SaaS, 2026-08-22) — 도메인 3개 · 기능 3개(**결정론적 시뮬레이션 테스트** ·
  **정적 자원 할당** · **확장의 축**). **36번째 회사, 하드웨어에 가장 가까운 첫 곳.**
  계정과 이체 둘만 다루는 원장 DB, **Apache 2.0 + 관리형 클라우드**, 시드 640만 달러 · **시리즈 A 2,400만 달러**.
  business_model 에 세 기능에 걸친 패턴을 적었다 — **먼저 좁혀서 대신 확실하게 만든다**
  (다룰 것을 좁혀 메모리를 미리 구하고, 워크로드를 좁혀 한 왕복 8,000건을 정하고,
  비결정성을 좁혀 같은 시드가 같은 실행을 내게 한다). **대가도 한결같다 — 좁힌 밖은 못 한다.**
  🔑 특기할 것 — ① **거절 이유가 성능이 아니라 '보는 자리'**(Jepsen·Antithesis 는 API 경계에서 멈춘다)
  ② **할당을 없애면 산수가 남는다**(배열의 열거형 + index/count/offset/size 규약)
  ③ **본질적 경합은 기계를 늘려 못 푼다**(암달의 법칙 → 왕복·락·레코드 크기를 줄이는 쪽으로 축을 바꿨다).
  검증 경고 0건. ⚠️ **사업 수치가 거의 없고 성능 수치는 회사의 주장이다.** Zig 는 1차로 확인 못 했다.

- **PlanetScale** (US, SaaS, 2026-08-22) — 도메인 3개 · 기능 3개(**동시성과 처리량** ·
  **백업·복구** · **고객의 실수를 감당하기**). **35번째 회사, 데이터베이스 회사 첫 곳.**
  요금표로 파는 방식을 확인했다 — **사용량이 아니라 인스턴스 크기(SKU)**, **metal(스토리지 포함)과 EBS 를 갈라 판다.**
  business_model 에 세 기능에 걸친 패턴을 적었다 — **남의 것을 맡으면 남의 실수도 맡는다**
  (고객의 15분 트랜잭션 · 고객 코드가 남긴 세션 상태 · 고객이 실수해도 되돌릴 수 있게 하는 백업).
  **고칠 권한이 없는 것은 고객 쪽만이 아니다** — 서브트랜잭션의 근본 해법 CSN 은 *"10년 넘게 논의됐고
  패치도 있지만 어느 것도 머지되지 않았다."* **그래서 글을 쓰는 것 자체가 대응 수단이 된다.**
  🔑 특기할 것 — ① **한도를 올리면 더 나빠진다**(트랜잭션 풀: 역압 신호를 없앤다) vs
  **한도를 올려도 소용없다**(서브xid: 미룰 뿐) — **우리가 만든 상한과 업스트림이 정한 상한의 차이**
  ② **백업을 뜨려면 먼저 복구를 해야 한다**(12시간마다 복원이 실제로 한 번 실행된다 — 다만 회사가
  검증이라고 설명하지는 않는다) ③ **만드는 데 42분, 되돌리는 데 12시간에서 며칠**. 검증 경고 0건.
  ⚠️ **비상장이라 매출·고객 수가 없다.** 오염된 풀 글에는 **수치가 전혀 없다.**

- **Zerodha** (IN, 핀테크, 2026-08-22) — 도메인 3개 · 기능 3개(**규제 문서 대량 생성** ·
  **과거 거래·리포트 데이터** · **로그 저장**). **34번째 회사, 인도 첫 회사이자 증권 첫 회사**
  (`IN` 을 validate.py 와 index.json 에 추가했다). 수익 구조를 1차 자료로 확인 —
  **현물 무료 · 옵션 건당 ₹20 정액**이라 **매출이 거래대금이 아니라 주문 건수에 붙는다.**
  business_model 에 세 기능에 걸친 패턴을 적었다 — **'우리가 맞춰야 하는' 도구를 거절한다**
  (Citus 는 스키마를 고쳐야 해서 · cLoki 는 파티셔닝·TTL 을 못 정해서 · Loki 는 자체 호스팅이
  복잡하고 RBAC 이 없어서 · FSx 는 리전에 없어서 · EBS 는 40대가 공유 못 해서).
  **그 대가로 부품을 직접 엮고 운영을 떠안는데, 그 전부를 기술팀 31명이 한다.**
  🔑 특기할 것 — ① **가장 빠른 EBS(400ms)를 두고 S3(4~5초)를 골랐다**(기준이 속도가 아니라 공유 가능성)
  ② **캐시를 키-값이 아니라 데이터베이스로**(*"하루가 끝날 때 수천만 개의 테이블"*)
  ③ **색인을 그만두니 20배가 줄었다**(행당 340B → 17.38B). 검증 경고 0건.
  ⚠️ **블로그가 2024-03 에 멈췄고 주문 처리(거래소 연결) 자료는 없다.** FY25 매출은 1차 발표를 못 찾았다.

- **Vinted** (EU, 커머스, 2026-08-22) — 도메인 3개 · 기능 3개(**아이템 검색** ·
  **데이터베이스 샤딩** · **자체 데이터센터 망**). **33번째 회사, 발트 첫 회사.**
  2025 회사 발표로 뒷받침 — GMV **€10.8bn**(+47%) · 매출 **€1.1bn**(+38%) · 순이익 €62m ·
  매출/GMV 약 **10.2%**. business_model 에 세 기능에 걸친 패턴을 적었다 —
  **옛것을 켜 둔 채 새것을 옆에 세우고 옮긴다**(섀도잉+3배 증폭 / 테스트 클러스터+카나리+
  되돌릴 수 있는 컷오버 / 레거시와 병렬로 깐 망 + 가상 토폴로지), **대가는 한결같이 시간**이고,
  **되돌리기 어려운 자리에는 자동화를 안 넣는다**(페일오버 수동 · 망 배포 수동).
  🔑 특기할 것 — ① **범주 한정 제안은 CTR +2.4%·사용률 +2.7% 인데 구매 확률이 약 1.3% 낮아 접었다**
  (⑬ 축 최상급 재료) ② **사람 손을 없애러 간 Vitess 프로젝트가 페일오버는 수동으로 남겼다**
  (Orchestrator 가 스플릿 브레인 → 3년간 긴급 reparent 1회) ③ **주-보조(MLAG·VRRP)를 아예 안 쓴다**.
  검증 경고 0건. ⚠️ **'한 점짜리 재고'는 세 편을 읽고도 확인 못 해 추정으로 남겼다.**

- **Allegro** (EU, 커머스, 2026-08-22) — 도메인 3개 · 기능 3개(**검색 적합성 평가** ·
  **프론트엔드 배포** · **저장을 어디에 둘 것인가**). **32번째 회사, 동유럽 첫 회사.**
  IR 1차 자료로 뒷받침했다 — FY2025 그룹 GMV **PLN 69,736m** · 매출 **PLN 12,103m** ·
  조정 EBITDA **PLN 3.5bn**, 폴란드 테이크레이트 **12.26%**, **Allegro Pay 가 GMV 의 16%를 자기 대출로**.
  business_model 에 세 기능에 걸친 패턴을 적었다 — **경계를 넘는 대신 경계를 없앤다**
  (심판을 클라우드 API → 로컬로 비용 60%↓ / FaaS 를 접고 의존성을 프로세스 안에 / GCS → 사내 Ceph /
  프로세스 3계층 → 단일 프로세스). **대가도 한 방향이다 — 격리가 사라진다**(의존성 1,206개가
  한 프로세스 메모리를 나눠 쓰고, Node.js 가 메모리를 못 되돌리는 것이 곧 회사의 한계가 된다).
  🔑 특기할 것 둘 — ① **평균 점수로 모델을 고르면 두 가지로 속는다**(Qwen κ 0.70 인데 파싱 5% 실패 /
  PLLuM 정확도 0.84 인데 κ 0.17) ② **완화책 다섯이 전부 다른 층에서 막혔다**(플랫폼 기능 · 기존 설비 ·
  조직 규칙 · 다른 설계와의 충돌 · 유지 비용). 검증 경고 0건.
  ⚠️ **검색 랭킹 본체와 Allegro Pay 여신 자료는 끝내 못 찾았다.**

- **trivago** (EU, 검색, 2026-08-22) — 도메인 2개 · 기능 2개(**Kafka 소비 파이프라인** ·
  **내부 API 통합**). **31번째 회사, 메타서치는 처음**(자기 재고가 없고 리퍼럴이 매출의 약 97%).
  business_model 에 두 기능에 걸친 패턴을 적었다 — **'상대를 바꾼다'를 포기한 자리에서 시작한다**:
  가격도 상류 API 도 남의 것이라 **lag 으로 남의 속도를 재고**, **상류 15개를 고치는 대신 앞에
  번역 층(GraphQL Mesh)을 세웠다.** 대가도 같은 모양이다 — **상대가 조용히 바뀌면 이쪽이 늦게 안다**
  (저트래픽 토픽은 2주 뒤 lag 메타데이터가 지워지고, 상류 스키마는 통보 없이 바뀌어 런타임에 발견).
  🔑 **같은 회사가 같은 기술을 두 곳에서 다르게 썼다** — 고객향 GraphQL 은 Apollo Federation +
  Karate 통합 테스트 + PreProd 환경까지 두는데(*"잘못된 변경 하나가 웹사이트 전체를 깨뜨릴 수 있다"*),
  사내 게이트웨이는 **Federation 을 명시적으로 버리고 스키마 레지스트리도 통합 스테이징도 없다**
  (*"자랑스럽지 않다"*). **차이를 만든 것은 기술이 아니라 깨졌을 때의 값이다.** 검증 경고 0건.
  ⚠️ **메타서치의 본체(가격 수집·비교·랭킹·광고 입찰) 자료는 끝내 못 찾았다** — 회사가 기술
  블로그에서 다루지 않는다.

  데이터 레이크 · **배차 실험·검증**). **30번째 회사, 동남아 첫 회사**(`SG` 를 validate.py 와
  index.json 에 추가했다). 습관 둘을 business_model 에 적었다 — **① 벽이 되는 건 데이터 크기가
  아니라 개수다**(인덱스 64바이트 · 1MB 미만 파일 수천 개 · "큰 표에 인덱스를 더하지 않는다";
  세 글이 서로를 언급하지 않는데 같은 결) **② 바꾸기 전에 확인할 자리를 따로 만든다**
  (`WithShadow`/`WithSplit` 이관 모드 · DispatchGym 시뮬레이션 · 합승 전 DBSCAN 사전 검증),
  **그리고 안 되면 되돌린다**(인덱스 NVMe → 되돌림). 검증 경고 0건.
  ⚠️ **이 회사 글에 자주 빠지는 것 — 버린 대안의 이름**(Iceberg 도, 합승 매칭 방식도 안 밝힌다).
  ⚠️ **슈퍼앱의 핵심 질문(이동과 배달이 같은 기사 풀을 나눠 쓰는가) 자료는 못 찾았다.**

- **Adyen** (EU, 핀테크, 2026-08-22) — 도메인 2개 · 기능 2개(회계·리포팅 원장 · 결제 처리 경로).
  **29번째 회사.** 축 둘 — **병목이 결제가 아니라 장부에 있다**(결제 1건 → 회계 약 50행, 초당 수백
  대 수천), 그리고 **Design to Duty**(설계한 사람이 온콜로 지킨다). 반복 습관을 business_model 에
  적었다: **판정 기준을 미리 정해 둔다**(20배 규칙 · *"새벽 4시에 이해되는 코드"* · 핵심이냐
  주변부냐) · **거절의 근거가 사라진 뒤에도 자체 구현은 남는다**(Kafka 를 안 쓴 이유가 exactly-once
  미지원이었는데 지금은 사내 논쟁 중) · **재조정이 싼 설계를 고른다**(라운드로빈 샤딩 · 무상태 엣지 —
  클라우드에 있지 않아 값이 더 크다) · **책임을 문서가 아니라 구조에 심는다.** 검증 경고 0건.
  ⚠️ **정확한 TPS·행 수·클러스터 규모·팀 규모를 공개하지 않는다** — 균형이 어디쯤인지 알 수 없다.

- **Zalando** (EU, 커머스, 2026-08-22) — 도메인 2개 · 기능 2개(내부 트래픽 라우팅 · 상품·오퍼 서빙).
  **28번째 회사.** 축은 **섞여 있던 것을 갈라내는 것** — 변화 속도가 다른 상품/오퍼, 엣지/내부 팬아웃,
  부하 신호의 '빠른 것/느린 것'. 그리고 **갈라낸 뒤 남는 값이 매번 캐시로 온다**(회사가 남긴 경고:
  *"캐시 지역성과 트래픽 격리는 반대 방향으로 잡아당긴다… 아니면 한 비용을 다른 비용으로 바꾸는
  것일 뿐이다"*). 셋째로 **접은 것과 되돌린 것을 적는다** — AZ 친화를 온콜 건강 때문에 끄고
  *"비용을 회수하는지는 아직 답하지 못한 질문"* 이라 남겼고, **2017년에 스스로 고른 이벤트 주도를
  2025년에 읽기 경로에서 되돌렸다.** 검증 경고 0건.
  ⚠️ PODS 글은 **버린 대안을 밝히지 않는다.** 패션 특유의 축(사이즈·반품·시즌) 자료는 못 찾았다.

- **Grafana Labs** (US, SaaS, 2026-08-22) — 도메인 2개 · 기능 2개(시계열 수집·저장 · 질의 실행).
  **27번째 회사.** 축은 **자기가 고른 설계를 이름 붙여 부정하는 것** — *"복제 계수 3은 비싸다"*,
  인제스터가 *"사실상 분산된 단일 장애점"* 이었다는 문장이 남이 아니라 자기 글에 있다.
  반복 습관을 business_model 에 적었다: **좋아지지 않은 것을 좋아졌다고 하지 않고**(확장성이
  나아진 게 아니라고 명시 · 고객 질의의 60%만 샤딩 · 병렬화가 아래 부하를 늘린다는 경고),
  **켜져 있다는 이유만으로 값을 내던 것을 찾아낸다**(안 쓰는 TSDB 격리를 끄자 인제스터 p99 -90%).
  그리고 **이 정직함이 성격이 아니라 구조에서 나올 수 있다**고 봤다(추정) — 남의 온프렘에서도
  돌아야 하면 되는 것과 안 되는 것을 정확히 적어야 한다. 검증 경고 0건.
  ⚠️ `grafana.com/blog/tags/engineering/` 는 **404**. 안 읽은 글: `a-year-in-mimir`,
  `maintainers-tell-all`, Loki·Tempo(도메인으로 안 열었다).

- **Canva** (AU, SaaS, 2026-08-21) — 도메인 2개 · 기능 2개(세션·인증 게이트웨이 · **인쇄 주문
  라우팅**). **호주 첫 회사**(validate.py 의 COUNTRIES 에 `AU` 를 추가했다). Figma 와 갈라지는
  지점은 편집기가 아니라 **인쇄** — 소프트웨어가 끝나는 자리에서 시작하는 물리 공급망이 있다.
  반복 패턴을 business_model 에 적었다: **실시간 경로에서 관계형 DB 를 지운다**(S3 이진 청크 ·
  Redis 샤딩 그래프), **확장 가능하게 만들기보다 확장할 필요를 없애기**, **운영해야 할 것을
  늘리지 않는 쪽을 고른다**(Redis 를 버린 이유가 *"클러스터를 우리가 운영해야 한다"*). 검증 경고 0건.
  ⚠️ **`인쇄 주문 라우팅` 은 1차 자료가 한 편뿐이다** — 두 번째 글을 못 찾았고
  `docs/print-partnerships` 는 '신규 신청 안 받음' 안내뿐이라 내용이 없다. open_questions 에 적었다.
  ⚠️ **동시 편집·렌더링 축은 자료를 확인하지 않아 도메인으로 열지 않았다.** 안 읽은 글:
  `snowpipe-streaming`, `reverse-image-search`, `scaling-to-count-billions`, `infrastructure-is-distribution`.

- **Spotify** (EU, 스트리밍, 2026-08-21) — 도메인 4개 · 기능 4개(데이터 레이크 조회 · 데이터
  플랫폼 · **실험 플랫폼** · 콘텐츠 수집·트랜스코딩). **유럽 첫 회사.** 축이 예상과 달랐다 —
  추천이 아니라 **데이터**다. IR 이 이유를 준다: FY2025 매출 17,186백만 유로 중 **프리미엄 89%,
  광고 11%(게다가 1% 감소)** 라, 광고로 사는 회사와 달리 **데이터가 제품이 아니라 원가 쪽에** 있다.
  **`실험 플랫폼` 은 25곳 통틀어 처음 연 도메인**이고 이 엔진에서 가장 겸손한 숫자가 여기서 나왔다
  (A/B 의 12%만 출시, 출시의 42%가 롤백, 그걸 잡은 eval 은 0개). 반복 패턴을 business_model 에
  적었다 — **아낀 것의 값이 다른 자리로 청구된다**(레이아웃 · 변경 가능성 · 가시성 · 이차 지표).
  검증 경고 0건. ⚠️ **추천 알고리즘 자료가 없어 그 도메인은 열지 못했다.** 오디오 전송은
  글이 있으나(CDN 2020 · BBR 2018) 너무 오래돼 열지 않았다 — 최신 자료가 나오면 열 자리다.

- **ByteDance** (CN, 소셜, 2026-08-21) — 도메인 5개 중 **3개**에 기능 4개(추천 학습·서빙 /
  GPU 자원 배분·서빙 2개 / 대규모 학습 인프라). **중국 첫 회사이자 1차 자료가 동료 심사 논문인
  첫 회사.** 축은 **피드가 먼저인 추천** — 사용자가 검색하지 않으니 모델이 '지금'을 따라잡아야
  한다. 반복 습관 넷을 business_model 에 적었다: **하드웨어 지표를 믿지 않는다 · 감수할 손실을
  숫자로 계산한다 · 버린 대안을 표로 남긴다 · 경험적으로 고른 값을 경험적이라고 적는다.**
  검증 경고 0건. ⚠️ **비상장이라 매출은 전부 보도·추정**이고, **`로컬 저장 엔진`·`그래프·분석
  데이터` 두 도메인은 자료가 없어서가 아니라 이 환경에서 VLDB PDF 를 읽을 수 없어서 못 팠다**
  (open_questions 에 그렇게 적어 두었다). PDF 를 읽을 수 있는 환경이 생기면 바로 팔 수 있다.

- **LY Corporation (라인야후)** (JP, 메시징, 2026-08-21) — 도메인 3개 · 기능 3개(스트리밍
  파이프라인 · 암호·기기 신뢰 · 데이터 레이크 통합). **일본 첫 회사.** 이 회사의 축은 합병이다 —
  LINE 과 Yahoo! JAPAN 이 각자 키운 시스템을 물려받아 **같은 일을 하는 물건이 두 벌** 있고,
  그래서 글이 '무엇을 새로 지었나'보다 **'서로 다른 역사를 가진 둘을 어떻게 잇는가'**를 다룬다.
  반복 패턴 넷을 business_model 에 적었다 — 옮기기 전에 선 긋기 · 합치지 않고 나란히 두기 ·
  완벽 대신 확률로 좁히기 · **엄격함이 공격자보다 정상 사용자를 먼저 자른다.**
  IR 이 열려 매출을 confirmed 로 넣었다(FY2026/03 · 커머스가 광고보다 크다). 검증 경고 0건.
  ⚠️ **Letter Sealing 은 원문이 열려도 키 교환을 밝히지 않아 기능으로 팔지 못했다** —
  도메인 `tech` 에만 남겼다. 아직 안 읽은 글: Flava DBaaS, 캐시 스탬피드(req-shield), 음성 품질.

- **GitHub** (US, 개발자 플랫폼, 2026-08-21) — 도메인 4개 · 기능 4개(코드 검색 · Git 저장·복제 ·
  데이터 계층 · CI 실행). **남의 코드를 맡고, 실행하고, 검색해 준다** — 셋 다 규모의 성질이
  달라서 원가가 고객 수가 아니라 **고객이 밀어 넣는 양**에 비례한다. **'쪼개는 기준을 데이터의
  성질에서 가져온다'**(블롭 ID · 함께 쓰이는 테이블 · 저장소 단위)와 **'옮기기 전에 선부터
  긋는다'**(schema-domains.yml + 린터, 체크섬)가 이 회사의 두 축이다. **Vitess 네 번째 사례**인데
  하나에 전부 걸지 않고 자체 write-cutover 를 따로 만들어 도구 두 벌을 들고 갔다.
  검증 경고 0건. ⚠️ Microsoft 산하라 **단독 재무가 공시되지 않아** 수익원 셋을 전부 `inferred` 로 뒀다.

- **Dropbox** (US, 저장 인프라, 2026-08-21) — 도메인 4개 · 기능 4개(저장 인프라 · 파일 동기화 ·
  전송 효율 · 검색). **21곳 중 유일하게 물리 저장 장치를 직접 굴린다** — 2013년 여름에 시작해
  2016년 500PB 를 S3 에서 자기 하드웨어로 옮겼고, **그 결정이 지금도 손익계산서에 잡힌다**
  (FY2025 매출총이익률 82.5%→80.1%, 원인은 '데이터센터 갱신 주기'의 감가상각).
  **'일부러 시시한 것을 고른다'**(Paxos·DHT 대신 샤딩된 MySQL — 이유는 '복잡함은 대개
  신뢰성의 반대다'와 '엔지니어가 여섯 명도 안 됐다')와 **'되돌릴 수 없는 변환을 남의 데이터에
  하려면 결정성을 요구한다'**(Lepton — seccomp + 저장 전 비트 비교)가 이 회사의 두 축이다.
  재작성 판단 체크리스트를 회사가 그대로 공개한 것(Nucleus, 4년)이 비교 문서 재료로 크다.
  검증 경고 0건.

- **Notion** (US, SaaS 문서, 2026-08-21) — 도메인 4개 · 기능 4개(블록 데이터 모델 · 저장·샤딩 ·
  동시 편집·실시간 · 검색·AI). **'전부 블록이다'라는 하나의 결정이 아래 모든 계층의 문제를 정한다.**
  구조의 자유가 권한의 모호함이 되어 유연함을 되돌린 기록, 논리 480 을 안 바꿔서 무중단을
  만든 재분배, 기술적으로 가능한 부분 로딩을 일부러 안 만든 오프라인, 2년에 걸쳐 네 번
  갈아엎어 비용을 90% 넘게 줄인 벡터 검색. **Figma 와 CRDT 에서 정면으로 갈린다.** 경고 0건.

- **Datadog** (US, SaaS 관측, 2026-08-21) — 도메인 4개 · 기능 4개(저장·멀티테넌시 · 수집 ·
  실시간 시계열 · 질의·대시보드). **남의 시스템을 보는 것이 제품**이라 원가가 고객의 사정에
  달려 있다 — 고객에게 사고가 나면 로그가 폭증하는데 하필 그때 화면이 가장 필요하다.
  **가장 값이 필요한 순간에 가장 비싸진다.** 그리고 받은 데이터가 곧 청구서라 중복이
  금액의 문제가 된다. 저장 엔진을 다섯 번 갈아엎은 이력이 남아 있다. 검증 경고 0건.

- **Cloudflare** (US, 인프라, 2026-08-21) — 도메인 4개 · 기능 4개(엣지 저장 · 엣지 네트워크 ·
  엣지 컴퓨트 · 보안·차단). **인프라 자체가 제품인 첫 회사**라 장애가 자기 서비스가 아니라
  남의 서비스를 멈춘다. **되돌릴 길은 쓰지 않으면 썩는다**(Workers KV 이중화를 하나로 줄였다가
  2시간 장애, 되돌리려니 인프라가 사라져 있었다)와 **고칠 수 없는 것을 비싸게 만든다**(Spectre —
  타이밍 차이를 없애는 대신 잴 도구를 뺐다)가 이 회사의 두 축이다. 검증 경고 0건.

- **Shopify** (CA, 커머스, 2026-08-21) — 도메인 4개 · 기능 4개(멀티테넌시·격리 · 회복탄력성·
  용량 계획 · 체크아웃·결제 · 스토어프론트 렌더링). **남의 매출의 일부를 받는 구조**라 가용성이
  자기 서비스가 아니라 남의 매출의 문제가 된다(머천트 솔루션 88.04억 대 구독 27.52억).
  **'격리의 단위가 곧 전환의 단위'**(pod 이동·리전 페일오버·pod 단위 점진 전환)와 **'미리 한계를
  찾아 두고 되돌릴 길을 열어 둔다'**(스케일 테스트·섀도 모드·Verifier·성수기 변경 동결)가
  반복된다. 검증 경고 0건. **큐의 마지막 회사였다.**
- **Discord** (US, 메시징, 2026-08-21) — 도메인 4개 · 기능 4개(메시지 저장·조회 · 실시간 전달·
  프레즌스 · 음성·영상 · 커뮤니티 운영·신뢰). **지난 대화가 사라지지 않고 사람이 한곳에 몰린다**는
  두 성질이 네 도메인을 전부 정한다. **'몰리는 것을 한 곳에서 합친다'**(요청 병합 · Manifold ·
  길드당 음성 서버 1대)와 **'터진 뒤 끊는 대신 들어가기 전에 센다'**(Semaphore · 침묵 억제 ·
  헬스체크 · 게시 전 차단)가 각각 반복된다. 검증 경고 0건.
  **수익 구성은 `미확인`** — 비상장이라 공시가 없고 1차 출처를 못 찾아 비워 뒀다.
- **YouTube** (US, 스트리밍, 2026-08-21) — 도메인 4개 · 기능 4개(업로드·트랜스코딩 ·
  저작권·콘텐츠 식별 · 추천·발견 · 전송·재생). **카탈로그를 회사가 고르지 않는다**는 사실이
  네 도메인을 전부 다시 정의한다 — 참조 없는 화질 판정(MOS), 지우는 대신 값을 매기는 저작권,
  성과의 정의를 두 번 바꾼 추천, 미리 채우지 않는 엣지 캐시. **'기계가 판정할 수 없는 것을
  시스템 밖에 놓는다'와 '무엇을 성과라고 부를지부터 다시 정한다'가 각각 두 번씩 반복**된다.
  검증 경고 0건. 논문 세 편은 **초록만 읽고 썼고 그 사실을 세 군데에 명시**했다.
- **Netflix** (US, 스트리밍, 2026-08-21) — 도메인 4개 · 기능 4개(인코딩·전송 · 콘텐츠 전송망 ·
  추천·발견 · 재생·적응 스트리밍). 추천이나 검색이 아니라 **비트를 실어 나르는 일 자체가 원가**인
  회사라, 기술의 무게가 '무엇을 보여줄까'보다 '어떻게 보낼까'에 실린다. **평균에 맞춘 하나의 답을
  버리는 모양이 세 번 반복**되고(타이틀마다 다른 래더 · 회원마다 다른 이미지 · 세션마다 다른 화질),
  세 번 모두 그것을 가능하게 한 것은 우아함이 아니라 **규모와 예측 가능성**이었다. 검증 경고 0건.
  재생 도메인의 자료는 2017·2018년 글이고 **비트레이트 선택 알고리즘 자체는 공개돼 있지 않다** —
  범위 주의를 달고 open_questions 로 남겼다.
- **Instagram** (US, 소셜, Meta 산하, 2026-08-21) — 도메인 4개 · 기능 4개(추천 퍼널 · 알림 ·
  광고 랭킹 · 콘텐츠 무결성). 다룰 콘텐츠의 자릿수가 달라서 '무엇을 위에 놓을까'가 아니라
  '어떻게 하면 전부를 정밀하게 보지 않아도 되게 할까'에서 시작한다. **'사용자 쪽을 떼어
  캐시한다'는 반복 패턴**이 두 도메인에서 같은 대가와 함께 나타난다. 검증 경고 0건.
  무결성 자료는 2019년 발표이고 Facebook 계정 쪽에 치우쳐 있어 범위 주의를 달았다.
- **Uber** (US, 모빌리티, 2026-08-21) — 도메인 3개 · 기능 3개(지리 인덱싱 · 도착 예측 ·
  실시간 매칭·배차). 파는 것이 물건도 화면도 아니라 '지금 여기'라는 순간이고, 수요와 공급이 둘 다
  움직인다. 그래서 기술이 공간과 시간을 다룰 수 있는 단위로 쪼개는 일에서 시작한다. 검증 경고 0건.
  `가격·수급 조절` 은 1차 자료를 못 찾아 도메인을 세우지 않고 open_questions 로 남겼다.
- **Stripe** (US, 핀테크, 2026-08-21) — **해외 첫 회사.** 도메인 5개 · 기능 6개(결제 API·개발자
  제품 2개 · 자금 기록·검증 · 리스크 · 데이터 인프라 · 매출 운영). 고객이 사용자가 아니라
  개발자라 제품이 화면이 아니라 API 의 계약이다. 여섯 기능 중 셋이 '되돌릴 수 있게 만들기'로
  수렴한다. 검증 경고 0건. `결제 처리·결제수단` 은 공개 엔지니어링 자료가 없어 도메인을 세우지
  않고 open_questions 로 남겼다.
- **무신사** (커머스, 2026-08-21) — 도메인 3개 · 기능 3개(상품 이해·속성 · 개인화·추천 ·
  검색·랭킹). 파는 물건이 패션이라 같은 대상을 브랜드마다 다르게 부르고, 그래서 추천·검색
  이야기가 모델이 아니라 분류 체계에서 시작한다. 검증 경고 0건. `입점 브랜드·파트너` 는 공개
  엔지니어링 자료가 없어 도메인을 세우지 않고 open_questions 로 남겼다.
- **쿠팡** (커머스/물류, 2026-08-21) — 도메인 5개 · 기능 5개(라스트마일·물류센터·검색·주문
  배송약속·마켓플레이스). 광고도 수수료도 아닌 물건값으로 버는 회사라 물류 비용이 곧 이익률이고,
  같은 눈으로 엔지니어링 반복 비용도 본다. 검증 경고 0건. 남은 구멍은 **재고 배치 알고리즘**과
  **배송일 계산 규칙** — 둘 다 이 회사의 심장인데 공개된 것은 주변 도구뿐이다.
- **당근** (로컬 커머스, 2026-08-21) — 도메인 5개 · 기능 5개(중고거래 검색·피드 노출·거래 신뢰·
  신원 인증·로컬 광고). 개인 간 거래에서 수수료를 받지 않고 수익을 전부 광고에서 걷는 구조가
  도메인 지도에 그대로 드러난다. 검증 경고 0건. `동네 인증` 은 자료에 맞춰 `신원 인증` 으로
  경계를 옮겼고, GPS 위치 판정 축은 `미확인` 으로 남겼다.
- **배달의민족** (커머스/물류, 2026-08-21) — 도메인 5개 · 기능 5개(배차·가게 노출·B마트 물류·
  주문 접수·정산). 수익원 3개가 모두 기능과 이어진다. 검증 경고 0건.
- **네이버** (검색, 2026-08-21) — 도메인 8개 · 기능 8개. 검색 축(질의 이해·문서 색인·
  랭킹·매칭·커머스 데이터·지면 구성)에 콘텐츠 유통·결제·페이·클라우드 인프라까지.
  수익원 5개가 모두 기능과 이어진다. 검증 경고 0건.
- **토스** (핀테크, 2026-08-20) — 도메인 4개 · 기능 5개. 기능마다 그림 3장(흐름·상태·실패)과
  개발 당시 생각, 결정 6~8개. 도메인마다 기술 4개와 그 기술이 못 하는 것. 검증 경고 0건.
  남은 구멍은 toss.json 의 open_questions 에 있다.

## 큐에 넣을 때 규칙

- 괄호 안은 `(국가, 카테고리)` — 국내는 국가를 생략한다.
- 뒤의 한 줄은 **그 회사에서 가장 먼저 팔 기능**이다. 회사의 대표 기능이자 공개 자료가
  가장 많은 것을 고른다(첫 사이클이 막히면 그 회사 전체가 막힌다).
- 공개 자료(기술블로그·컨퍼런스 발표·논문)가 거의 없는 회사는 넣지 않는다. 추론만으로
  채운 페이지는 이 사이트의 신뢰도를 통째로 깎는다.
