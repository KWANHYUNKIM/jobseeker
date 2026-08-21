# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**Mercari — 38번째 회사.** 사이클 203 까지 프로파일 + **도메인 3개** + **기능 1개**(`asset-exchange`).

> **`asset-exchange` 의 축 — 자리가 이름을 바꾸면 두 벌을 영원히 같이 고쳐야 한다.**
> 같은 잔액이 **출발지일 때 `PaymentMethod`, 도착지일 때 `UserBalanceItem`** 이었고,
> 회사의 표현으로 *"단지 다른 자리에 나타난다는 이유로 같은 것이 코드에서 두 메커니즘으로 갈린다."*
> 답은 **`Value` 하나로 합치고, 이동을 `Exchange` 하나로 세우는 것** — 그리고 **Authorize / Capture** 두 단계.
> ⚠️ **이 글에는 대가가 하나도 적혀 있지 않다.** 결정 7개 중 **여섯 개의 tradeoff 가 이 사이트의 해석**이고,
> 본문에 그렇게 표시했다. **회사가 직접 적은 대가는 '범위' 하나뿐**이다(크게 잡으면 만드는 일이 고통스럽고,
> 작게 잡으면 추상이 가치를 잃는다).

> **눈에 걸린 것 셋** — ① **기술 부채가 회계로 샜다**(*"경리 팀이 특정 자금 이동이 어떤 API 를 썼는지까지
> 알아야 할 수도 있다"*). 코드가 지저분한 것은 개발자가 참지만 **이것은 참는 것으로 끝나지 않는다.**
> ② **되돌림이 역방향이 아니다** — 카드는 도착지가 될 수 없는데 환불은 되므로 `ExchangeReversal` 이 따로 있다.
> ③ **분기를 없앤 게 아니라 확장점 뒤로 옮겼다**(Hook / Step / Decision). 대신 **Step 은 보상을 함께 쓰도록 강제**한다.

> **다음 사이클** — 도메인 **`비밀번호를 없앤 다음에 남는 문제`** 의 기능 하나.
> 재료 둘은 **같은 이야기의 앞뒤**다: `20251106 phishing-resistant-accounts-with-passkey`(패스키를 등록하면
> 비밀번호·SMS OTP 를 **아예 막는다**, 복구는 **마이넘버 카드 자가 신원확인**, **2025-09 기준 1,090만 개 =
> MAU 의 약 절반**, 로그인 중 **패스키 31.6% · 비밀번호 44.3%**) → `20260730 risk-based-authentication`
> (**약 1,300만 명**, 피싱 금전 피해 사실상 0인데도 **순수 강제를 거절**하고 **네 단계 스펙트럼 + 전환마다 위험 평가**,
> **세션 자세 vs 계정 자세를 의도적으로 비대칭 가중**). **회사가 여덟 달 만에 자기 입장을 바꾼 기록**이라
> `thinking` 과 상태 전이 그림의 재료가 좋다. 세 번째 글(`Tales of OIDC & OAuth Security`)은 제목만 봤다.

> **그다음** — `국내용으로 만든 것을 국경 밖으로` 는 **다섯 편 모두 본문 미독**이다. **기능을 열기 전에 읽는다.**

> **📌 Mercari 를 완주하면 반드시 후보 조사 사이클을 넣는다 — 큐 잔량 1/3(Yelp 뿐).**
> 사다리상 in_progress(2순위)가 큐 미달(7순위)을 이기므로 **닫히는 순간까지 미뤄진다.**
> 여전히 빈 곳: **라틴아메리카 0곳 · 아프리카 0곳**, 게임은 Roblox 하나, 의료·바이오 0곳, 물류 전문 0곳.

**큐 1/3** — Yelp(US).

마지막 사이클: 203 (2026-08-22) — Mercari 자산의 이동을 하나로(Exchange 추상).

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
| `engineering.mercari.com/en/blog/` 의 '더 보기' | ❌ `/en/blog/page/2/` 는 404. **분류별 목록 `/en/blog/category/<backend\|security\|infrastructure\|ai\|client-side\|development\|organization\|qa\|research-advanced-tech>/` 로 우회한다**(각 10편) |
| **IR 데이터시트 (CSV/Excel)** | ✅ **PDF 보다 먼저 이것을 찾는다.** 일본 상장사는 `pdf.irpocket.com/...csv` 로 분기별 수치를 통째로 준다 — CMap 을 풀 필요가 없다 |
| `engineering.klarna.com` · `engineering.razorpay.com` · `blog.flipkart.tech` | ❌ 403 |
| `zerodha.tech` · `planetscale.com/blog` · `clickhouse.com/blog` | ✅ 목록·본문 모두 열린다 (사이클 180 에서 확인) |
| `tigerbeetle.com/blog` · `engineering.careem.com` | ✅ 목록·본문 모두 열린다 (사이클 189 에서 확인) |
| `engineeringblog.yelp.com` · `engineering.mercari.com` | ✅ 목록·본문 모두 열린다 (사이클 199 에서 확인) |
| `www.cockroachlabs.com/blog` | ⚠️ 열리지만 **첫 페이지가 제품 마케팅 위주** — 심층 글을 따로 찾아야 한다 |
| `www.factorio.com/blog` | ⚠️ 열리지만 **최근 글이 게임플레이 위주** — 이 엔진에 안 맞는다 |
| `www.scylladb.com/blog` | ❌ 403 |
| `engineering.flutterwave.com` · `blog.mercadolibre.com` | ❌ DNS 자체가 없다 |
| `flexport.engineering` | ❌ 응답 없음 |
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
