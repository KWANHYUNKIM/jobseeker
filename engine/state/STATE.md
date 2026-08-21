# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**아무 회사도 파는 중이 아니다 — 25곳이 전부 done 이다.** 사이클 157 은 회사가 아니라
**비교 문서**를 썼다(사다리 마지막 칸). **다음 사이클은 26번째 회사 Canva 를 새로 연다.**

> **Canva 를 열 때 알아야 할 것** — `canva.dev/blog/engineering`, **본문 확인 완료**.
> 첫 기능은 `session-revocations-at-scale`: 세션 **수억 개**를 초당 **수십만 요청** 아래서 폐기한다.
> **Redis 를 "내구성 보장이 부족하다"며 버리고** S3 이진 청크(30분 파티션)로 갔고, ZooKeeper
> 리더 선출만 믿지 않고 **조건부 PUT** 을 겹쳤다(*"노드가 쓰기 직전 임의로 멈출 수 있다"*).
> 메모리 **87.5% 절감**, 게이트웨이 파드당 폐기 **100만 건 이상**, 쓰기 초당 **2,000건 이상**.
> 다른 축의 글: `the-science-of-routing-print-orders`(인쇄 주문을 **물리 공급망**으로 라우팅 —
> 이 엔진에 없는 축), `canva-incident-report-api-gateway-outage`, `snowpipe-streaming`.
> **호주 회사이니 index.json `countries` 맵에 AU 가 있는지 확인**할 것(없으면 추가하거나 '기타').

> **⚠️ 비교 문서를 쓸 때 배운 것 — 먼저 기존 16개 문서의 축을 확인한다.** 이번에 후보 셋 중
> 둘이 **이미 있는 문서와 겹쳤다.** '완벽한 탐지를 포기하고 확률로 좁히는 자리'는
> `기계가 판정할 수 없는 것을 어디에 두는가`(youtube·discord·instagram·kakao·daangn)와,
> '대리 지표의 함정'은 `무엇을 좋다고 부를 것인가`(netflix·youtube·musinsa·uber·instagram)와
> 겹친다. **그래서 남은 축(신호 고르기)을 골랐고, 겹치는 회사·기능은 빼서 새 문서에 다시 쓰지
> 않았다**(netflix `per-title-encoding` 은 이미 쓰였으므로 제외).

> **이번에 쓴 문서: `잘못된 자를 어떻게 알아채는가`** (배민 `rider-dispatch` · Instagram
> `notification-diversity` · ByteDance `heteroscale`·`megascale` · Spotify `llm-evals-vs-experiments`).
> **기존 15개 문서가 전부 초기 회사들만 다루고 있었는데, 새 회사(ByteDance·Spotify)가 처음으로
> 비교 문서에 들어갔다.** 축: 재고 있던 숫자가 재려던 것이 아니었을 때 무엇이 그것을 드러냈는가.
> 다섯 중 넷이 **'틀린 값'이 아니라 '맞는데 다른 것을 재는 값'** 이었고, **바꾼 자가 언제나
> 더 비쌌다**(직선거리는 공짜, 실거리는 분당 20만 경로) — 틀린 자가 널리 쓰이는 이유다.

> **아직 안 쓴 비교 축 (재료 확인 필요)** — ② 틀려도 되는 일 vs 틀리면 안 되는 일
> (ByteDance 추천 ↔ 토스·스트라이프 원장). ③ 양 끝 대신 축을 바꾸는 수(LY 공유 KEK · GitHub
> 일회용 러너 · Dropbox SSD 캐시 · Spotify RAP). ④ 데이터 레이크의 작은 파일 문제(LY 뿐 —
> 다른 회사 확인 필요). ⑤ 합병·인수로 시스템이 두 벌이 된 회사(LY 뿐 — Spotify 가 Podz 를
> 인수해 다시 지은 사례가 있으니 **둘이 될 수 있다**). **③이 가장 재료가 많다(4곳).**

**큐 잔량 3/3.** Canva → Grafana Labs → Zalando.

마지막 사이클: 157 (2026-08-21) — 비교 문서 `wrong-yardstick`. 문서 16개가 됐다.

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
