# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**아무도 안 판다 — Yelp(39번째)를 사이클 210 에서 done 으로 닫았다.** 도메인 3개가 전부 채워졌다.

> **`revenue-correctness` 의 축 — 틀림이 조용하고, 확인할 기회를 엔지니어가 정할 수 없다.**
> 레거시 빌링은 **결제와 청구서가 1:1** 이라 결제가 최근 청구서에만 붙었고, 미납 이월(`Invoice Obviation`)과
> 겹쳐 *"매출이 잘못된 매출 기간에 기록"* 됐다. **화면은 멀쩡한데 장부가 틀린다.**
> 그리고 회사가 직접 적는다 — *"자동 테스트에만 의존할 수 없었다"*,
> **"고객은 보통 월 1회만 청구서를 받으므로 정확성을 검증할 기회가 제한적이다."**
> 그래서 이 도메인의 설계가 전부 **미리 확인하는 쪽**으로 기운다 — 재실행하면 같은 값(프로덕션 DB 직접 읽기를
> 버렸다), 바꾸기 전에 과거로 돌려 보기(백테스팅).

> **📌 '읽는 사이클' 이 두 번 연속 값을 했다.** 209 에서 PostgreSQL→MySQL 글을, 210 에서
> Revenue Automation 두 편을 처음 읽었고, **둘 다 그 글에서만 나오는 버린 대안이 있었다.**
> 백테스팅 글 한 편만 봤을 때는 *"버린 대안이 없다"* 였는데, 두 편을 더 읽으니 **다섯 개**가 나왔다
> (패치 · 기성 제품 · MySQL 배치 · dbt · 스트림 처리). **한 편으로 도메인을 판단하지 않는다.**

> **📌 다음 사이클 — `--gaps` 는 [신규] 를 가리킨다. `## 대기` 맨 위인 Doximity 를 연다**(40번째).
> 사다리에서 **신규(6순위)가 비교 문서(8순위)보다 위**라, 비교 문서 재료가 찼어도 그쪽이 먼저다.
> Doximity 는 1차 자료 확인 완료 — `technology.doximity.com`, 읽은 CDC 글에 **버린 대안 넷**
> (Debezium 스냅샷 · 토픽 1:1 · 즉시 병합 · binlog 만 보기)과 수치(**95% 8분 · 99% 13분**)가 있다.
> **의료가 이 사이트에 0곳이고**, 사용자가 개인도 가맹점도 아닌 **면허 있는 전문가**라 축이 다르다.

> **📌 비교 문서 두 축이 다 찼다 — 큐가 비면 바로 쓸 수 있다.**
> **'재 보고 고른다'(3)** — Careem `cost-leaks` · Zerodha `log-storage` · Yelp `partition-access`.
> **'되돌릴 수 있는 것을 먼저 한다'(4)** — Figma · Shopify 섀도 모드 · 토스 카나리 · Yelp `in-place-swap`
> (**같은 회사가 두 답을 낸 사례**라 이쪽에서 가장 단단하다).

**큐 2/3** — Doximity(US · 의료) · Moniepoint(NG · 핀테크). **⚠️ 라틴아메리카·물류 전문은 여전히 0곳.**

마지막 사이클: 210 (2026-08-27) — Yelp 틀렸다는 걸 알아차릴 기회가 드물다 + 회사 완주.

## 다음 선택지

*(사다리는 PROMPT.md 2단계가 정한다. 여기는 그 사다리가 여러 개를 물어올 때의 판단 근거다.)*

1. **GitHub 코드 검색(Blackbird)** — 사다리가 지금 가리키는 곳.
2. **research 14건 감사** — 3-2 균일함이 남아 있다. STYLE.md 7번이 새 규칙("셋을 넘었다면
   하나는 거의 확실히 장식이다")으로 바뀌었으니 그 기준으로 덜어낼 수 있다.
   **공개 사이트에 나가기 전에 하는 편이 낫다.**
3. **비교 문서 '재 보고 고른다'** — Careem `cost-leaks` · Zerodha `log-storage` · Yelp `partition-access`.
   **셋 다 값을 재는 방법을 먼저 만들고 그다음에 골랐다.** 재료가 셋이라 지금 쓸 수 있다.
4. **비교 문서 '되돌릴 수 있는 것을 먼저 한다'** — Figma 논리→물리 샤딩 · WebGPU 동적 폴백 ·
   Shopify 섀도 모드 · 토스 카나리 자동 롤백 · **Yelp `in-place-swap`**(같은 회사가 두 답을 냈다 —
   Cassandra 는 되돌릴 길을 팔았고, PostgreSQL→MySQL 은 사서 1년을 썼다). **재료가 넷이라 지금 쓸 수 있다.**
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
| `technology.doximity.com` · `engineering.moniepoint.com` | ✅ 목록·본문 모두 열린다 (사이클 206 에서 확인) |
| `engineeringblog.yelp.com/page/N/` | ⚠️ **끝 슬래시가 없으면 http 로 301** 된다. 분류·태그 링크가 없어 페이지 번호로만 넘긴다(43페이지) |
| `www.yelp-ir.com` 의 실적·보도자료 | ⚠️ 첫 화면 지표는 오는데 **하위 페이지는 JS 렌더링이라 본문이 안 온다** — 브라우저가 필요하다 |
| `engineering.ifood.com.br` | ❌ 403 |
| `blog.wildlifestudios.com` | ❌ DNS 자체가 없다 (주소를 잘못 알고 있었다) |
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

### 한 편으로 도메인을 판단하지 않는다 (사이클 209·210)

**'읽는 사이클'** — 기능을 쓰지 않고 본문만 읽는 사이클 — **이 두 번 연속 값을 했다.**
Yelp 의 광고 매출 도메인은 한 편만 읽었을 때 *"버린 대안이 없다"* 였는데, 같은 도메인의 두 편을
더 읽으니 **버린 대안이 다섯 개** 나왔다. 제자리 이관 도메인도 두 번째 글을 읽고서야 축이 잡혔다
(같은 회사가 정반대 답을 냈다는 것은 한 편만 봐서는 안 보인다).

- **도메인을 열 때는 글 수를 세고 한 편을 열어 보되, 기능을 쓸 때는 그 도메인의 글을 두 편 이상 읽는다.**
- 읽어 보고 재료가 없으면 그때 `hold_reason` 을 붙인다 — **읽기 전에 붙이지 않는다.**

### 화면 도해를 쓰기 시작했다 (사이클 204~)

기능마다 `ui`, 회사마다 `ui_map` — **사용자가 보는 화면을 놓고 그 위의 번호에 설명을 건다.**
형식은 STYLE.md '화면 도해' 절과 schema.json 에 있고 validate.py 가 검사한다. 지금까지 붙인 곳:
**토스**(회사 지도 + `instant-transfer`) · **Mercari**(`credential-spectrum` · `expand-without-forking`).

- **핀은 `decisions` 하나에 대응시킨다.** 버린 대안이 없는 핀은 설명이 아니라 캡션이라 빼는 게 낫다.
- **인프라·아키텍처 기능에도 화면이 있다** — 그 변경이 사용자에게 드러나는 자리를 찾으면 된다
  (예: 국경을 넘는 일은 '해외 구매자가 보는 상품 화면'의 재고·통화·구매 버튼으로 드러난다).
- **회사 `ui_map` 이 있으면 뷰어가 mermaid 도메인 지도를 접는다.** 아직 토스에만 있다.

### 도판에서 걸린 것

- **`stateDiagram-v2` 의 `note` 는 뷰어 팔레트를 안 따른다** — 머메이드 기본값인 **주황 상자**로 떠서
  '종이 위의 잉크' 양식에서 혼자 튄다(사이클 204 에서 확인). 뷰어의 `plate()` 가 노트를 안 덮는 것으로
  보인다. **고쳐지기 전까지 note 를 아껴 쓰고**, 할 말은 상태 설명 줄(`상태 : <b>제목</b><br/>설명`)에 넣는다.

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
