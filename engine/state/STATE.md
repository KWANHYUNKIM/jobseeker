# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**아무 회사도 진행 중이 아니다.** PlanetScale 을 사이클 193 에서 **done 으로 닫았다**(35번째, 도메인 3 · 기능 3).

> **⚠️ 다음 사이클은 비교 문서다 — 회사를 열지 않는다.** 쓸 것은 **⑳ '거절한 이유가 성능이 아니었다'**.
> **기능 겹침을 검산해 뒀다** — 아래 다섯은 `domains/index.json` 의 어떤 문서에도 아직 안 쓰였다:
> `console-warehouse`(Zerodha — **Citus**: *"모든 샤딩 테이블에 새 참조 ID 컬럼을 추가한다. 수백 개의
> 질의를 다시 써야 하는 그 길로 가고 싶지 않았다"*) · `contract-notes`(Zerodha — **EBS** 가 400ms 로
> 가장 빠른데 **40대가 공유 못 해서** 4~5초짜리 S3 를 골랐다, **FSx** 는 **ap-south-1 리전에 없어서**) ·
> `internal-graphql-gateway`(trivago — **Federation**: 상류가 GraphQL 을 채택하고 스키마를 조율해야 해서) ·
> `independent-deploys`(Allegro — **FaaS**: 왕복 비용 + *"의존성 100%에 적용할 수 없다"*) ·
> `dc-network`(Vinted — **큰 L2 + MLAG**: *"대역폭이 늘고 가용성이 조금 좋아지지만"* 경계는 그대로 /
> **서브넷 안 나눈 EVPN**: 서버 주소를 모든 스위치에 알려야 해서).
> **논지: 다섯이 전부 '그걸 쓰면 우리 쪽이 바뀌어야 한다'로 모인다.** 새 주장은 만들지 말고 confirmed 만 엮되,
> **각자가 그 대신 감수한 것**(직접 샤딩·느린 저장소·번역 층·프로세스 안 격리 포기·라우팅 지식 요구)과
> **이 사이트에 아직 없는 것**을 반드시 넣는다. 다른 문서는 **제목으로만** 가리킨다(SPA 라 상대 링크가 깨진다).
> ㉑ '터진 뒤 끊는 대신 들어가기 전에 센다'는 그다음 후보다(PlanetScale `concurrency-limits` ·
> Discord · trivago `kafka-consumers` · Vinted `log-storage`).

> **PlanetScale 에서 확인한 회사 축 — 남의 것을 맡으면 남의 실수도 맡는다.**
> 고객의 15분짜리 트랜잭션이 시스템을 무너뜨렸고(막을 권한이 없어 **번짐만** 막았다), 고객 코드가 남긴
> 세션 상태가 **아무 잘못 없는 다른 요청**을 깨뜨렸으며(씻어 주고 알려 준다), 백업은 아예 방향을 뒤집어
> **고객이 실수해도 되돌릴 수 있게** 만들어 둔다. **고칠 권한이 없는 것은 고객 쪽만이 아니다** —
> CSN 스냅숏은 *"10년 넘게 논의됐고 패치도 있지만 어느 것도 머지되지 않았다."*
> **그래서 이 회사에서는 글을 쓰는 것 자체가 대응 수단이 된다.**

> **🔑 상한을 두고 정반대 교훈 둘이 한 회사 안에 있다** — 트랜잭션 풀은 **올리면 더 나빠지고**(역압이 사라진다)
> 서브xid 캐시는 **올려도 소용없다**(미룰 뿐). **우리가 만든 상한과 업스트림이 정한 상한의 차이**로 보인다.

**큐 2/3** — TigerBeetle(기타 — 하드웨어에 가장 가까운 후보) · Careem(AE — 중동 첫 회사).

마지막 사이클: 193 (2026-08-22) — PlanetScale 고객의 실수를 감당하기 + 완주.

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
