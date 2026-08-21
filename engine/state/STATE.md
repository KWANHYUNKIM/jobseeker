# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**LY Corporation (라인야후) — 도메인 3개 중 2개에 기능이 있다.** 사이클 147 에서
`hdfs-bridge`(데이터 레이크 통합)를 채웠다. **남은 하나는 `메시지 암호화`인데, 지금은 팔 수 없다.**

> **⚠️ Letter Sealing 을 열어 봤고, 얇았다 — 다시 시도하지 말 것.**
> `engineering.linecorp.com/en/blog/the-next-step-for-even-safer-messaging-letter-sealing/` 는
> **열리기는 한다.** 하지만 **키 교환 방식을 밝히지 않고**(세션 키를 어떤 프로토콜로 맞추는지),
> 다중 기기 키 동기화도 다루지 않는다. 확인된 것은 그룹 초기 50명 제한, 키를 기기에만 둔다,
> iOS 9.3.1 VoIP 알림 이후에야 알림에서 복호화 가능 — **도메인 `tech` 에는 넣었지만 기능 하나를
> 채우기에는 모자란다.** PQC 글도 계획 단계다. **다른 글을 찾거나(예: `line-device-attestation-1/2`
> 로 인증 축을 열거나) LY 를 여기서 done 으로 닫는 판단이 다음 사이클의 몫이다.**

> **남은 후보 (목록에서 제목만 확인, 본문 미확인):** `line-device-attestation-1/2`,
> `req-saver-for-thundering-herd-problem-in-cache`, `techverse2026-231`(Flava DBaaS),
> `how-to-measure-voice-quality-in-line-app`, `techverse2026-86`(OpenTofu·ChatOps).

> **⚠️ URL 함정 (그대로 유효):** WebFetch 로 `techblog.lycorp.co.jp/en/` 목록을 읽으면 링크
> 호스트를 **`www.lycorp.co.jp`** 로 바꿔 내놓는다 — 경로는 맞으니 호스트만 `techblog.` 로 고친다.
> IR 은 반대로 `www.lycorp.co.jp/en/ir/finance/highlight.html` 이 맞다(HTML, 잘 열린다).

> **이번에 나온 것 — 두 글이 각자 다른 쪽에서 같은 벽에 부딪혔다.** HDFS 통합 글은
> **네임노드 힙** 쪽에서, Hive→Trino 글은 **Spark 출력** 쪽에서 **'작은 파일이 너무 많다'** 를 만난다.
> HDFS 의 한계는 데이터 양이 아니라 **파일 개수**라서, **빨라지려고 병렬로 쪼갠 것이 저장 계층의
> 한계를 당긴다.** 둘 다 근본 해결이 아니라 **주기적 병합으로 눌러 둔다.**

> **비교 문서 후보가 셋으로 늘었다** — ① LY 공유 KEK(크기 vs 격리) · GitHub 일회용 러너(격리 vs
> 속도) · Dropbox SSD 캐시 제거: **양 끝 중 하나를 고르는 대신 축을 바꿔 버리는** 수.
> ② 데이터 레이크 위의 **작은 파일 문제**(LY · 다른 회사에도 있는지 확인 필요).
> ③ **합병·인수로 시스템이 두 벌이 된 회사**가 LY 뿐인지 — 있으면 좋은 축이다.

**큐 잔량 3/3 — 채웠다.** Canva 를 후보에서 대기로 올렸다(본문 확인). ByteDance → Spotify → Canva.

마지막 사이클: 147 (2026-08-21) — LY 데이터 레이크 통합 + Canva 큐 승격.

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
