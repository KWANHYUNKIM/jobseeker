# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**없다 — Figma 완주(2026-08-21, 사이클 101).** 도메인 4개 · 기능 4개:
`multiplayer-doc` · `livegraph-subscription` · `webgpu-renderer` · `horizontal-sharding`.
완주 기준 셋을 다 확인했다 — 모든 도메인에 기능 1개 이상, 고아 기능 없음, 수익원 연결.

**완주 14개 · 보류 1개(카카오, `hold_reason` 참조) · 큐 비어 있음.**
진행 중인 회사가 없으므로 다음 사이클부터 사다리는 **보강**으로 내려간다 —
`validate.py --gaps` 가 내놓는 69건(research 67 · tech 2)이 맨 위다.

마지막 사이클: 101 (2026-08-21) — Figma 데이터 저장·확장.

## 다음 선택지

*(사다리는 PROMPT.md 2단계가 정한다. 여기는 그 사다리가 여러 개를 물어올 때의 판단 근거다.)*

1. **보강 — research 67건.** `--gaps` 가 알파벳 순으로 baemin 부터 짚는다. 한 사이클에
   기능 하나씩 논문·난제를 채운다. **자료를 새로 뒤지지 않아도 되는 것이 많다** —
   이미 쓴 결정과 도메인 tech 에 무엇을 딛고 섰는지가 대개 드러나 있다.
2. **보강 — 문자열 엔티티 14건 정규화.** discord·figma·netflix·shopify·youtube 의
   `domain_model.entities` 가 `"이름 — 설명"` 문자열이다. 화면은 양쪽을 읽지만 형식이
   둘이면 다음에 쓰는 사람이 어느 쪽이 맞는지 모른다. **기계적인 작업이라 한 사이클에
   여러 개를 몰아서 해도 된다.**
3. **비교 문서 '충돌을 해결하는가, 충돌이 안 생기게 만드는가'** — Figma(속성 단위 LWW ·
   분수 인덱싱) · Shopify(판매 단위당 1행 + SKIP LOCKED) · 토스(계좌 락 + 멱등 키) ·
   Discord(요청 병합) · Stripe(멱등 키). **Figma 가 완주해서 이제 쓸 수 있다.**
4. **비교 문서 '몰리는 요청을 어디서 합치는가'** — 아직 안 쓴 마지막 옛 축.
   Figma LiveGraph 의 읽기 관통 캐시·확률적 필터가 여기 붙는다.
5. **비교 문서 '되돌릴 수 있는 것을 먼저 한다'** — 101 에서 선명해진 새 축.
   Figma 논리→물리 샤딩 · Figma WebGPU 동적 폴백 · Shopify 섀도 모드와 pod 단위 전환 ·
   토스 카나리 자동 롤백. **한 회사 안에서만 두 번 반복된 것이 눈에 띈다.**

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
