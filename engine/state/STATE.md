# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

**Snap (US · 소셜/카메라·AR) — 48번째. 도메인 2개 · 기능 3개. 큐 잔량 0/3.**

**269 에서 사용자가 직접 지시했다** — Part 2 `Code Search` 를 읽고 도메인 ① 의 두 번째
기능을 썼다: `agentic-code-search`(똑똑한 색인 대신 똑똑한 반복), **결정 8개**.
**3부작이 셋 다 읽혀 닫혔다.**

### 🔴 269 의 발견 ① — 설계의 출처가 다른 회사 제품이다

Code Search 는 아키텍처의 근거로 **Claude Code 가 실제로 어떻게 동작하는지**를 든다 —
*"Claude Code doesn't query a vector store. It runs grep. It runs it many times… The model
itself decides what to search for, evaluates results, and iterates. **The retrieval system
is dumb. The intelligence is in the loop.**"* 그리고 물었다: *"What if remote agents could
grep across all of Snap's code, the way Claude Code greps a local checkout?"*
**이 사이트에서 남의 제품의 동작 방식을 자기 인프라 설계의 근거로 대놓고 적은 사례는 여기가
처음이다.**

### 🔴 269 의 발견 ② — RAG 를 버린 이유가 일곱이다

정확도 우선(*"a confident wrong answer"*) · 벡터 DB 는 상태를 가진 시스템이라 운영 표면이
*"roughly doubled… for marginal user-facing benefit"* · 임베딩이 GPU 를 태운다 · 사람도
에이전트도 정확 일치를 더 자주 원한다 · 정규식은 벡터로 **표현 자체가 안 된다** ·
*"RAG flattens that into a single non-iterative retrieval step"* · **그리고 가장 값나가는
이유** — *"a stronger model means better search with nothing for us to change. RAG can't
ride that curve; its ceiling is the retriever, not the reasoner."*
**대가도 적는다** — 키워드 없는 모호한 질문에서는 *"takes seconds, not milliseconds"*.

### 🔴 269 의 발견 ③ — Part 2 가 Part 1 의 지표에 단서를 더한다

CodePal 이 '병합 전에 잡았다' 고 말할 수 있는 이유가 *"true only because reviews run on
open PRs, **not because anything is build-verified**."* **267 의 오탐 0% 는 같은 글 안에서
*"not on live traffic"* 으로 좁혔는데 이 단서는 다음 편에 있다** — **이 회사는 범위를
밝히되 항상 같은 글에서 밝히지는 않는다.** `open_questions` 에 적었다.

### 3부작이 셋 다 확인됐다

Part 2 가 셋을 잇는 자리다 — Part 1(CodePal)이 *"The first production consumer of code
search"* 였고, Part 3(Casper)은 *"lean on code search to move across all of Snap's code at
a scale no engineer could by hand"* 한다. **CyberAgent·Wayfair·컬리에서 관찰한 '글끼리
서로를 언급하지 않는다' 의 정반대를 세 번 다 확인했다.**

### 다음 사이클 — 닫을지 더 팔지 정한다

**두 도메인이 다 찼고 기능이 셋이다.** `--gaps` 는 [진행 중 확장]을 안 낼 것이다.
회사를 갈아타지 않는다는 규칙이 위이므로 **미독 3편 중 하나를 더 팔지, Snap 을 `done` 으로
닫을지 먼저 정한다.**

- **⚠️ 미독 3편** — `/spatial_intelligence`(LLM 공간 지능 측정, 2026-06-17) ·
  `/specs_experiences`(2026-08-20) · `/spectacles_supabase`(Snap Cloud, Supabase 기반
  백엔드 — *"building compelling experiences for AR glasses often demands more than what
  runs on-device"*). **앞의 둘은 도메인 ②(Specs/AR)의 두 번째 기능 재료가 될 수 있다.**
- **닫는다면 `business_model` 에 적을 패턴 가설 셋** — ① **자기 지표의 범위를 밝힌다**
  (CodePal 오탐 0% 의 held-out 단서 · GNSS 의 "못 잰다" · Code Search 의 build-verified
  단서) ② **묶음마다 글끼리 잇는 방식이 다르다**(AI 도구 3부작은 서로를 부르는데 Specs 둘은
  단절) ③ **같은 연작 안에서도 대가의 밀도가 크게 다르다**(CodePal 다섯 줄 · Code Search
  일곱 이유 vs **Casper 0줄**).
- **⚠️ 블로그 8쪽 중 1쪽만 봤다**(JS 페이지네이션, 운영 사실 ⑬). **다만 `WebSearch` 에
  `allowed_domains: eng.snap.com` 을 걸면 목록 밖 글을 찾을 수 있다**(268 에서 `/eyeconnect`
  를 그렇게 찾았다) — **운영 사실로 굳는다.**
- **⚠️ 매출 실액·DAU 미확인.** IR 홈에 MAU **971백만** · 총매출 **19% 성장**(Q2 2026) 뿐.
  **IR 보도자료 목록에서 링크를 눌러 들어간다** — URL 추측은 두 번 404(운영 사실 ⑰).

### 다음 회사 — 큐가 0 이다

Snap 을 닫으면 **곧바로 후보 조사이고 한국 밖에서** 찾는다(한국 회사가 아홉).
**📌 Grab 보강 후보** — 이미 `done` 이지만 2026 새 글: **Palana 2부작**(06-19/21) ·
Agent platform Part 1(07-24) · **Iceberg(07-10)** · **Counter Service 저장소 이전(07-03)**
— 뒤 둘은 기존 `iceberg-lake` · `counter-service` 의 후속. **안 열어 본 후보(한국 밖)** —
Sea/Shopee(다른 주소?) · GoTo/Tokopedia · Traveloka · Plaid · Adevinta · Skyscanner ·
Carousell · VNG.

**빈 자리** — 라틴아메리카 0(접었다·재시도 금지) · **게임 1**(Roblox) · 아프리카 1 ·
인도 1 · 여행 1. 동남아는 Grab.
**`hold_reason` 두 곳** — LinkedIn `랭킹 모델을…`, kakao `동기화·다중 기기`.

**비교 문서 재료** — `관측에 값을 무엇으로 치르는가`(여덟) · `기한을 무엇으로 정하는가`(여섯)
· **⭐ `기계가 그렇다는데` 에 Snap 이 두 답을 준다**(`code-review-agent` 와
`agentic-code-search` — **후자는 '모델이 좋아지면 내 것도 좋아진다' 는 새로운 논거다**) ·
`되돌릴 수 있는 것을 먼저 한다` 보강 · **⭐ `무엇을 좋다고 부를 것인가`/`재 보고 나서` 에
Snap 이 세 재료를 준다** — **자를 못 구해 "못 잰다" 고 적은 사례(GNSS)는 이 사이트에
처음이고**, 잴 수 있는 쪽(EyeConnect)에서는 세 자리 수치를 내며, **범위를 밝히되 다른 편에서
밝히는 경우(Code Search → CodePal)도 있다.**

## 다음 선택지

*(사다리는 PROMPT.md 2단계가 정한다. 여기는 그 사다리가 여러 개를 물어올 때의 판단 근거다.)*

1. **GitHub 코드 검색(Blackbird)** — 사다리가 지금 가리키는 곳.
2. **research 14건 감사** — 3-2 균일함이 남아 있다. STYLE.md 7번이 새 규칙("셋을 넘었다면
   하나는 거의 확실히 장식이다")으로 바뀌었으니 그 기준으로 덜어낼 수 있다.
   **공개 사이트에 나가기 전에 하는 편이 낫다.**
3. **비교 문서 '틀렸다는 것을 어떻게 알아차리는가'** — **새 축.** Moniepoint `traceable-truth`(판단의 출처를
   남겨 되짚는다) · Yelp `revenue-correctness`(월 1회 청구서가 확인 주기를 정한다) ·
   Doximity `clinical-ai-trust`(의사 1.1만 명의 검토를 제품 안에). **셋 다 '정확도를 올린다' 가 아니라
   '틀렸을 때 드러나게 만든다' 쪽으로 갔다.** 재료가 셋이다.
4. **비교 문서 '무엇을 잃기로 정했는가'** — **새 축.** Moniepoint `critical-path`(*"약간의 완전성을
   훨씬 큰 신뢰와 맞바꿨다"*) · Doximity `cdc-overlap`(겹침은 받고 간극은 못 받는다) ·
   Yelp `partition-access`(놓친 접근은 '안 쓰임' 쪽으로 기운다). **셋 다 오차의 방향을 한쪽으로
   몰아 놓았다** — 그게 이 축의 핵심이다. 재료가 셋이다.
4. **비교 문서 '미루되 미룬 것이 안 보이게 한다'** — **새 축.** Doximity `cdc-overlap`(base+delta 뷰가
   미룬 병합을 감춘다) · Careem `cost-leaks`(삭제가 즉시가 아니라 예약이라 언두 로그가 쌓였다) ·
   PlanetScale `concurrency-limits`. **미루는 설계의 값이 어디서 드러나는가**가 축이다. 재료가 셋이다.
4. **비교 문서 '재 보고 고른다'** — Careem `cost-leaks` · Zerodha `log-storage` · Yelp `partition-access` ·
   **Doximity `prod-profiling`**. 앞의 셋은 *'무엇을 고를지'* 를 재는 이야기이고, **Doximity 는 결이 다르다** —
   **재는 행위 자체가 답을 바꾸는 쪽**이다(계측형은 싼 것을 비싸 보이게, 프로파일링은 타이밍을 바꾸고
   데이터까지 남긴다). **비교 문서에서 이 차이를 축으로 쓸 수 있다.** 재료가 넷이다.
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
| `tech.kakao.com` | ❌ **지금은 못 읽는다.** 목록은 최근 3편만 렌더링되고 본문은 WebFetch 로 안 열리는데, **브라우저가 탭을 못 만든다**(228). 사이클 235 에서 확인 |
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
| `technology.doximity.com` | ✅ 목록·본문 모두 열린다. 약 92편이 한 페이지에 '더 보기' 로 이어진다(분류 링크 없음) |
| `engineering.moniepoint.com` | ✅ 목록·본문·분류 모두 열린다. **작다 — 전부 8편 남짓**이고 `payments`·`data` 분류는 비어 있다 |
| **IR 보도자료(Q4 Inc 계열)** | ✅ **브라우저 `get_page_text` 로 전문이 온다** — `investors.<회사>.com/news/news-details/<연도>/<제목>/default.aspx`. WebFetch 는 빈 껍데기만 준다. Doximity 에서 표까지 통째로 받았다(사이클 211) |
| `press.doximity.com` · `sec.gov/Archives` | ❌ 앞은 본문이 비고, 뒤는 WebFetch 403 |
| `engineering.ifood.com.br` · `engineering.rappi.com` · `careersatdoordash.com/engineering-blog` · `unrealengine.com/en-US/tech-blog` | ❌ 403 |
| `tech.target.com` · `techlab.bol.com/en` | ✅ 목록·본문 모두 열린다. Target 은 **한 페이지 15편 × 7페이지(약 100편)** 이고 분류 링크가 있다. bol.com 은 **최신 글이 2024-11** 이라 멈췄을 수 있다 |
| `corporate.target.com` 보도자료·소개 | ✅ **WebFetch 로 실적 표까지 온다** — 브라우저가 필요 없었다(사이클 219). `investors.target.com` 은 **브라우저 권한이 막혀 있어** 시도하지 않는다 |
| `www.backblaze.com/blog` | ⚠️ 열리지만 **데이터·홍보 성격** — Drive Stats 수치는 넘치는데 **의사결정과 대가가 없다** |
| `engineering.grab.com` | ✅ **목록·본문·분류 모두 열린다**(사이클 225). **약 240편**(24페이지 × 10), 분류는 `/categories/<engineering\|data-science\|design\|product\|security>/` 로 편수까지 나온다 |
| `engineering.atspotify.com` | ✅ **목록·본문 모두 열린다**(사이클 225). 글 주소는 `/YYYY/M/<slug>` 형식이고 목록은 '더 보기' 로 이어진다 |
| `blog.cloudflare.com` | ⚠️ **열리지만 제품 발표가 섞여 있다** — 연 글(`task-based-oauth-consent`)이 마케팅이었다. **심층 글을 골라야 한다** |
| `supercell.com/en/blog/` · `blog.cred.club` | ❌ 앞은 **404**, 뒤는 `cred.club` 으로 **301**(블로그가 없어진 듯) |
| `engineering.dena.com/en/` | ❌ **영문 블로그가 2020-12 에서 멈췄다**(238). 일본어 쪽은 미확인 |
| `www.honeycomb.io/blog` · `www.fastly.com/blog` | ⚠️ 살아 있지만 **제품 마케팅**(238). Temporal 과 같은 부류 — **개발자 대상 제품 회사의 블로그는 영업 채널이다** |
| `techlife.cookpad.com` | ⚠️ 살아 있고 기술 블로그가 맞지만 **얇다**(최신 2026-05-12, 홈에 3편). 전부 일본어. 두 편 이상 묶이는 주제가 안 보인다(238) |
| 한국 게임사(Krafton·Nexon·NCSOFT) | ❌ **엔지니어링 블로그를 못 찾았다**(238). 검색 결과가 전부 사업·AI 제휴 뉴스다 |
| `aboutwayfair.com/careers/tech-blog` | ✅ **목록·본문·태그 편수 모두 열린다**. **태그별 목록이 URL 로 열린다** — `?tag=<이름>&p=<쪽>`(240). 최신 2026-07-17, Data Science 90 · ML/AI 68 · CV 10 |
| `aboutwayfair.com/category/company-news/...` | ✅ **실적 보도자료가 WebFetch 로 열린다**(240) — 브라우저가 필요 없었다. `investor.wayfair.com` 은 시도하지 않았다 |
| `developers.cyberagent.co.jp/blog/` | ⚠️ **목록은 열리고 활발한데**(최신 2026-08-26, ABEMA 125편) **연 글이 얇았다**(239). 영어 글도 섞여 있다 |
| `www.reddit.com` | ❌ **Claude Code 가 아예 못 가져온다**(도메인 차단, 239) |
| `linkedin.com/blog/engineering` | ⚠️ **글 본문은 URL 을 알면 열리는데 목록·분류 페이지는 안 열린다.** WebFetch 는 내비게이션만 주고(`/artificial-intelligence`·`/infrastructure`·`/search` 전부), **브라우저도 탭을 못 만들었다**(No tab available, 사이클 228). `/talent` 만 12편이 떴는데 대부분 경력 이야기다 — **글 편수를 셀 수 없다** |
| `about.gitlab.com/blog/categories/engineering/` | ⚠️ **열리지만 날짜가 본문에 안 실리고 제품 홍보가 섞여 있다** — 넣으려면 심층 글을 먼저 확인해야 한다 |
| `etsy.com/codeascraft` · `tech.groww.in` · `unity.com/blog` · `zillow.com/tech` | ❌ 전부 **403** |
| `blog.wise.com` | ❌ **DNS 없음** |
| `engineering.bolt.eu` | ❌ `bolt.eu/en/careers/...` 로 **301** — 블로그가 아니라 채용 페이지다 |
| `blog.sentry.io/categories/engineering/` | ❌ **404**(다른 경로가 있을 수는 있다) |
| `temporal.io/blog` | ⚠️ 열리지만 **제품 마케팅** — 에이전트·파트너십 위주 |
| `blog.booking.com` | ⚠️ **엔지니어링 블로그가 맞는데 최근 항목이 전부 유튜브 영상 링크다** — 축어를 인용할 본문이 없다 |
| `engineering.fb.com` | ✅ 열린다(최신 2026-08-24). **다만 목록에 `Instagram (Meta)` 가 이미 있어 중복 위험으로 넣지 않았다** |
| `tech.olacabs.com` | ❌ **연결 거부**(ECONNREFUSED) |
| `blog.phonepe.com` | ❌ `medium.com/phonepe` 로 **302** — Medium 은 막혀 있다 |
| `techlab.bol.com/en/blog/` | ⏸️ 열리지만 **글이 2024-11-07 에서 멈췄다**(2026 항목은 경력 팟캐스트다) |
| `tech.ocado.com` · `engineering.quintoandar.com.br` · `tech.mercadolibre.com` | ❌ DNS 자체가 없다 |
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

### 큐에 넣기 전에 이미 판 회사인지 본다 — 사이클 226 에서 데였다

사이클 225 가 후보 조사로 넣은 **두 곳이 다 이미 `done` 인 회사**였다(Grab · Spotify).
넣지 않은 Cloudflare 도 이미 있었다. **블로그가 좋다는 것과 이 사이트에 없다는 것은 다른 문제다.**

```
python3 -c "import json;print(sorted(e['name_en'] for e in json.load(open('jd-viewer/public/reveng/index.json'))['companies']))"
ls jd-viewer/public/reveng/companies/          # 파일을 쓰기 전에 한 번 더
```

**지리 공백도 목록으로 다시 센다.** 225 는 *"동남아 0곳"* 이라고 적었는데 **Grab 이 그 동남아였다.**
기억으로 세면 틀린다.

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

### 한 편으로 도메인을 판단하지 않는다 (사이클 209·210, 212~214 에서 재확인)

**'읽는 사이클'** — 기능을 쓰지 않고 본문만 읽는 사이클 — **이 두 번 연속 값을 했다.**
Yelp 의 광고 매출 도메인은 한 편만 읽었을 때 *"버린 대안이 없다"* 였는데, 같은 도메인의 두 편을
더 읽으니 **버린 대안이 다섯 개** 나왔다. 제자리 이관 도메인도 두 번째 글을 읽고서야 축이 잡혔다
(같은 회사가 정반대 답을 냈다는 것은 한 편만 봐서는 안 보인다).

- **도메인을 열 때는 글 수를 세고 한 편을 열어 보되, 기능을 쓸 때는 그 도메인의 글을 두 편 이상 읽는다.**
- 읽어 보고 재료가 없으면 그때 `hold_reason` 을 붙인다 — **읽기 전에 붙이지 않는다.**
- **후보 글이 빗나갈 수 있다.** 사이클 213 에서 첫 후보(`Modularizing Rails Monoliths`)는 수치도 대가도
  없어 결정으로 못 썼고 다음 후보로 옮겨야 했다. **한 편 열어 보고 아니면 다음 것을 연다.**
- 실제 성적: Yelp 광고 매출(0 → 5개) · Doximity 임상 AI(**0 → 6개**) · Doximity 데이터(+1) ·
  Mercari 국경(보류 후보였는데 기능이 나왔다). **한 편만 보고 '자료가 없다' 고 판단한 적이 한 번도 맞지 않았다.**

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

- **Cygames** `tech.cygames.co.jp` — **두 방법으로 두 번 다 실패했다**(252 WebFetch · 253 브라우저 `get_page_text`). 둘 다 *"본문 없음"* 이고 `/archives/` 는 404 다. **게임 자리(Roblox 하나뿐)를 메울 유일한 실마리였지만 접는다.** 새 단서(다른 도메인의 목록 주소)가 없으면 다시 열지 않는다.

- **Gojek** `www.gojek.io/blog` — **429 가 세 번**(246 에 두 번 · 253 에 한 번). 시간을 두고 다시 두드렸는데도 같았다. **일시적 제한이 아닌 것으로 보인다.** 동남아 두 번째 자리 후보였다.

- **Cookpad** `techlife.cookpad.com` — **두 번 열어 두 번 다 얇았다**(238 · 246). 최신 글이 **2026-05-12** 이고 홈에 보이는 세 편이 *iOS Liquid Glass 대응 · RubyKaigi 부스 소개 · RuboCop 캐시* 라 **두 편 이상 묶이는 시스템 주제가 없다.** 페이지가 안 열리는 게 아니라 **팔 것이 없다.** 새 단서(설계 결정을 다루는 구체적인 글 주소)가 없으면 다시 열지 않는다.

*(두 번 찾아 두 번 다 없었던 것. 새 단서 — 회사의 새 글·새 발표 — 가 생기기 전엔 다시
꺼내지 않는다. 같은 벽을 반복해 들이받는 루프는 아무것도 만들지 않는다.)*

| 대상 | 무엇을 못 찾았나 | 확인한 사이클 |
|---|---|---|
| 카카오 | 동기화·다중 기기 (도메인 6/7 에서 멈춤, 완주 보류) | 028 에서 두 번째 확인 |
| Netflix `adaptive-playback` | 비트레이트 선택 알고리즘 자체(무엇을 보고 언제 전환하는지) | 자료가 2017·2018년 글뿐 |
