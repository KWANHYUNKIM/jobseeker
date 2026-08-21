# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**LY Corporation (라인야후) — 23번째 회사, 일본 첫 회사.** 사이클 146 에서 열었다.
프로파일 + 도메인 3개 + 기능 1개(`kafka-e2ee`)까지 갔다. **다음 사이클은 `--gaps` 가
'기능이 없는 도메인'을 가리킬 것이다 — 남은 둘은 `메시지 암호화`와 `데이터 레이크 통합`.**

> **⚠️ URL 함정 — 이번에 실물로 확인했다.** WebFetch 로 `techblog.lycorp.co.jp/en/` 목록을
> 읽으면 링크 호스트를 **`www.lycorp.co.jp`** 로 바꿔서 내놓는다. 그대로 쓰면 404 다.
> **경로는 맞으니 호스트만 `techblog.` 로 고쳐 쓴다.** IR 쪽은 반대로 `www.lycorp.co.jp` 가 맞다.

> **다음 기능 후보 — 이미 본문을 확보했다.**
> ① **데이터 레이크 통합**: `techverse2026-184` (1EB+ HDFS 두 벌 잇기 — ViewFS vs RBF,
> 테이블 단위 권한 vs 경로 단위 권한, 버린 안이 명시돼 있다. **두 번째 글로
> `migration-from-hive-to-trino-and-spark` 가 있다**).
> ② **메시지 암호화**: `pqc-to-protect-data-in-the-age-of-quantum-computers` 는 계획 단계라
> 기능 하나를 채우기엔 얇다. **Letter Sealing 원문은 구 `engineering.linecorp.com` 에 있고
> 접근을 아직 확인하지 않았다** — 열리면 이 도메인의 첫 기능이 되고, 안 열리면 ①을 먼저 판다.
> ③ 그 밖에 확인된 제목: `line-device-attestation-1/2`, `req-saver-for-thundering-herd-problem-in-cache`,
> `techverse2026-231`(Flava DBaaS), `how-to-measure-voice-quality-in-line-app`.

> **이 회사의 축 — 합병.** LINE 과 Yahoo! JAPAN 이 각자 십수 년 키운 시스템을 물려받아
> **같은 일을 하는 물건이 두 벌** 있다. 그래서 글이 '무엇을 새로 지었나'보다
> **'서로 다른 역사를 가진 둘을 어떻게 잇는가'**를 다룬다 — 다른 22곳에 없던 결이다.
> IR 은 열린다(`www.lycorp.co.jp/en/ir/finance/highlight.html`, HTML). **커머스가 광고보다 크다**
> (FY2026/03 · 백만 엔: Commerce 857,897 · Media 734,545 · Strategic 445,775 · 합계 2,036,366).

> **새 축 — '크기와 격리가 같은 손잡이의 양 끝이다.'** 소비자마다 키를 주면 헤더가 소비자
> 수만큼 불어나고, 하나로 모으면 그 키가 새는 순간 과거와 미래가 함께 열린다. LY 는 **공유
> KEK 으로 물러서고 격리를 시간(회전)으로 옮겼다.** GitHub 의 '일회용인데 빨라야 한다'와
> 같은 모양이라 — **양 끝 중 하나를 고르는 대신 축을 바꿔 버리는** 수 — 비교 문서 후보다.

**큐 잔량 2/3.** ByteDance → Spotify. 다음 신규 사이클 전에 후보를 하나 채워야 한다.

마지막 사이클: 146 (2026-08-21) — LY Corporation 개설 + Kafka E2EE.

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
