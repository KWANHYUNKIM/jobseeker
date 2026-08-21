# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**진행 중인 회사가 없다.** 사이클 194 는 비교 문서였다 — **`누가 바뀌어야 하는가`**(22번째 문서).

> **다음 사이클은 `## 대기` 맨 위 — TigerBeetle 을 연다.** 36번째이고 **하드웨어에 가장 가까운 회사**다.
> 자료는 `tigerbeetle.com/blog`(본문 확인 완료). 가장 먼저 팔 것은 **정적 메모리 할당**
> (`a-database-without-dynamic-memory`: 연결 수·메시지 크기·메시지당 질의 수를 **시작/컴파일 시점에 고정**하고
> 총 메모리를 곱셈과 덧셈으로 계산한다. 이유가 성능만이 아니다 — *"정적 할당은 과부하를 쉽게 다루게 해 준다.
> 객체와 배열 크기가 고정이면 잘못 설정된 클라이언트가 보내도 끝없이 자라는 버퍼가 없다."*
> 계정·이체 메시지 **128바이트**, 메시지당 기본 최대 질의 **8,191개**).
> 다른 글: `a-trillion-transactions`(**확장의 일곱 단계**, **OLTP 수평 샤딩을 명시적으로 거절** —
> 캐시 지역성 상실·암달의 법칙·*"연 100만 달러"*, 128 TiB 복구 추정 **2.9시간**/인덱스 포함 **약 6시간**) ·
> `a-tale-of-four-fuzzers` · `protocol-aware-deterministic-simulation-testing` · `tracking-time-without-clock` ·
> `three-clocks-are-better-than-one` · `the-write-last-read-first-rule`.
> ⚠️ **비상장·소규모라 사업 수치가 거의 없다** — business_model 은 얇게 잡고 기술에 무게를 둘 것.
> 국가는 **`기타`**(설립지가 분명치 않으면 억지로 정하지 말 것), 카테고리는 **`SaaS`**.

> **이번에 쓴 문서 — `누가 바뀌어야 하는가`.** 거절 이유가 성능이 아니었던 다섯을 엮었다.
> 가장 센 증거는 Zerodha 가 **가장 빠른 EBS(400ms)를 떨어뜨리고 4~5초짜리 S3 를 고른 것**이다.
> 이유를 **네 모양**으로 갈랐다 — ① 내 스키마·질의를 고쳐야 한다(Citus·Federation, **성능 얘기가 아예 없다**)
> ② 내 실행 구조에 안 맞는다(EBS 공유 불가 / 큰 L2 는 **아무것도 안 바뀌어서** 탈락)
> ③ **절반만 된다**(Allegro FaaS — 배포 방식이 두 벌) ④ **거기 없다**(FSx 가 ap-south-1 에 없음).
> 그리고 **trivago 가 같은 Federation 을 고객향에서는 쓰고 사내에서는 안 쓴다** — **거절은 도구의 속성이
> 아니라 자리의 속성**이라는 대목을 따로 세웠다.

> **다음 비교 문서 후보 — ㉑ '터진 뒤 끊는 대신 들어가기 전에 센다'.** 재료:
> PlanetScale `concurrency-limits`(트랜잭션 풀 상한 — **올리면 더 나빠진다**) ·
> Discord(이미 STATE '되풀이되는 설계 축'에 Semaphore·침묵 억제로 적혀 있다 — **어느 기능인지 확인 필요**) ·
> trivago `kafka-consumers`(KEDA lag) · Vinted `log-storage`(Vector 애그리게이터 — 활성 파트 폭발).
> **쓰기 전에 `domains/index.json` 으로 겹침을 검산할 것.**

**큐 2/3** — TigerBeetle · Careem(AE — 중동 첫 회사). **TigerBeetle 을 열면 1/3 이 되니 완주 뒤 후보 조사.**

마지막 사이클: 194 (2026-08-22) — 비교 문서 `누가 바뀌어야 하는가`.

## 다음 선택지

*(사다리는 PROMPT.md 2단계가 정한다. 여기는 그 사다리가 여러 개를 물어올 때의 판단 근거다.)*

1. **GitHub 코드 검색(Blackbird)** — 사다리가 지금 가리키는 곳.
2. **research 14건 감사** — 3-2 균일함이 남아 있다. STYLE.md 7번이 새 규칙("셋을 넘었다면
   하나는 거의 확실히 장식이다")으로 바뀌었으니 그 기준으로 덜어낼 수 있다.
   **공개 사이트에 나가기 전에 하는 편이 낫다.**
3. **비교 문서 '되돌릴 수 있는 것을 먼저 한다'** — Figma 논리→물리 샤딩 · WebGPU 동적 폴백 ·
   Shopify 섀도 모드 · 토스 카나리 자동 롤백. Notion 을 판 뒤면 재분배 사례가 하나 더 붙는다.
4. **비교 문서 '충돌을 해결하는가, 충돌이 안 생기게 만드는가'** — Figma·Shopify·토스·Discord·Stripe.
5. **보강 — 문자열 엔티티 14건 정규화.** 기계적인 작업이라 몰아서 해도 된다.

## 배운 것

*(다음 사이클이 모르면 헛수고할 것만. 사이클 요약을 쌓는 곳이 아니다.)*

### 자료 접근 지도

한 번 막힌 경로를 다음 사이클이 또 두드리지 않게 한다.

| 출처 | 접근 |
|---|---|
| `techblog.woowahan.com` | ✅ WebFetch 로 본문이 온다 (가장 쉬움) |
| `navercorp.com` · `kakaocorp.com` 뉴스룸 | ✅ WebFetch 가능 |
| `docs.stripe.com` | ✅ WebFetch 로 잘 읽힘. 1급 출처로 쓴다 |
| `engineering.fb.com` | ✅ 1차 출처이고 WebFetch 로 잘 읽힘 |
| `figma.com/blog` · `investor.figma.com` | ✅ 둘 다 WebFetch 로 읽힘 (IR 본문까지 온다) |
| `tech.kakao.com` | ⚠️ 브라우저(claude-in-chrome)로만 본문이 읽힌다 |
| `medium.com` | ⚠️ WebFetch 403. 브라우저로 열면 읽힌다 |
| `netflixtechblog.com` | ⚠️ WebFetch 403. 브라우저 navigate → `get_page_text` |
| `stripe.dev/blog/*` | ⚠️ JS 렌더링. 브라우저 navigate → `get_page_text` 필요 |
| `stripe.com/blog/*` | ⚠️ `stripe.dev` 로 301. WebFetch 는 리다이렉트를 안 따라간다 |
| `deview.naver.com` · `blog.naver.com` · `d2.naver.com` | ❌ fetch 불가 |
| `tech.trivago.com` · `vinted.engineering` · `engineering.mercari.com` | ✅ 자체 도메인 정적 블로그 — 목록·본문 모두 열린다 |
| `engineering.klarna.com` · `engineering.razorpay.com` · `blog.flipkart.tech` | ❌ 403 |
| `zerodha.tech` · `planetscale.com/blog` · `clickhouse.com/blog` | ✅ 목록·본문 모두 열린다 (사이클 180 에서 확인) |
| `tigerbeetle.com/blog` · `engineering.careem.com` | ✅ 목록·본문 모두 열린다 (사이클 189 에서 확인) |
| `blog.paystack.com` | ❌ 403 |
| `technology.riotgames.com` | ❌ **뉴스 검색 페이지로 301** — 기술 블로그가 없어진 것으로 보인다 |
| `engineering.leboncoin.fr` · `tech.showmax.com` | ❌ DNS 자체가 없다 (주소를 잘못 알고 있었다) |
| **PDF (IR 자료 등)** | ✅ **읽을 수 있다.** WebFetch 가 *"decode 할 수 없다"* 고 답해도 **바이너리를 `tool-results/` 에 저장해 준다** — 그 파일을 아래 방법으로 직접 푼다 |

### 되풀이되는 설계 축

여러 회사에서 같은 모양이 반복해서 나온 것들. 비교 문서의 씨앗이자, 새 회사를 팔 때
"여기도 같은 문제가 있나"를 먼저 물어볼 목록이다.

- **충돌을 해결하는가, 충돌이 안 생기게 만드는가** — Figma 속성 단위 LWW·분수 인덱싱 /
  Shopify 판매 단위당 1행 / 토스 계좌 락 / Discord 요청 병합 / Stripe 멱등 키.
- **몰리는 것을 한 곳에서 합친다** — Discord 요청 병합·Manifold·길드당 음성 서버 1대.
- **터진 뒤 끊는 대신 들어가기 전에 센다** — Discord Semaphore·침묵 억제.
- **격리의 단위가 곧 전환의 단위** — Shopify pod 이동·리전 페일오버·pod 단위 점진 전환.
- **분포에 맞춘 설계는 분포 밖에서 정확히 실패한다** — Slack 여러 샤드 순회가 보통
  사용자에겐 잘 돌고 수백 워크스페이스에선 무너져 50개로 자른 것 / Discord 대형 길드.
- **미리 한계를 찾아 두고 되돌릴 길을 열어 둔다** — Shopify 스케일 테스트·섀도 모드·
  Verifier·성수기 변경 동결 / 토스 카나리 자동 롤백.

### PDF 를 직접 읽는 법 — 사이클 176 에서 뚫었다

WebFetch 가 PDF 를 못 읽는다고 답해도 **응답 끝에 로컬 저장 경로를 알려 준다.** 그 파일에
poppler·pypdf 없이 순수 파이썬으로 접근할 수 있다. Allegro IR 발표자료(4.2MB)에서 실제로
매출·GMV·테이크레이트를 전부 뽑았다.

1. `re.finditer(rb'stream\r?\n', d)` 로 스트림을 찾아 `zlib.decompress` — 실패하는 것은 건너뛴다.
2. `beginbfchar`/`beginbfrange` 가 있는 스트림에서 **ToUnicode CMap** 을 만든다.
3. 본문 스트림(`Tj`/`TJ` 포함)에서 텍스트를 뽑는다. 두 형태가 있다 —
   `<hex>` 형과 **2바이트 코드를 리터럴 문자열 `(...)` 에 담은 형**(팔진 이스케이프를 풀어야 한다).
4. 코드를 CMap 으로 옮긴다.

> ⚠️ **CMap 을 문서 전체에서 하나로 합치면 폰트가 섞여 글자가 밀린다**(TITLE 이 SHSKD 로 나온다).
> 페이지 대부분이 멀쩡하면 그대로 쓰되, **밀린 페이지는 버린다.** 그리고 **자간이 낱글자로
> 벌어져 나오는 경우가 있다**(`A l l e g r o`) — 수치는 붙어 나오므로 읽는 데는 지장이 없다.

### 서술 관례

- 공개 자료가 **범위를 한정해서만** 말하는 경우(알고리즘 자체는 비공개 등), `business.why`
  맨 앞에 **범위 주의**를 단다. 선례: 카카오 `taxi-dispatch`, Netflix `adaptive-playback`.

## 재시도 안 함

*(두 번 찾아 두 번 다 없었던 것. 새 단서 — 회사의 새 글·새 발표 — 가 생기기 전엔 다시
꺼내지 않는다. 같은 벽을 반복해 들이받는 루프는 아무것도 만들지 않는다.)*

| 대상 | 무엇을 못 찾았나 | 확인한 사이클 |
|---|---|---|
| 카카오 | 동기화·다중 기기 (도메인 6/7 에서 멈춤, 완주 보류) | 028 에서 두 번째 확인 |
| Netflix `adaptive-playback` | 비트레이트 선택 알고리즘 자체(무엇을 보고 언제 전환하는지) | 자료가 2017·2018년 글뿐 |
