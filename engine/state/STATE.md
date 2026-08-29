# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

**PayFit(EU · SaaS) `in_progress` — 도메인 1개 · 기능 1개.** 355 에서 첫 기능
**`name-it-before-you-cut`(자르기 전에 이름부터 맞춘다)** 를 썼다.
**결정 7개 · 그림 3장 · 생각 4개 · 난제 2건 · 연결 0건**(첫 기능이라 이을 곳이 없다).

**⑭ `--gaps` 가 [확장] payfit 을 정확히 지목했다.**

**재료** — `PayFit on the Domain-Driven Design Journey`(2023-06-02). **2/3**(대가 있음 ·
수치 약함 · **버린 대안 없음**). **⚠️ 버린 대안이 없는 글인데 결정이 7개 섰다** — 갈림길을
글 안에서 찾아 세우고 **버린 쪽은 '지금까지 그랬던 것' 으로 잡았다**(기술 층 편성 · 엔지니어끼리
모델링 · 급여 명세를 내부 상세로 두기 · 한 이름으로 계속 쓰기 · 전면 재작성 · 중앙 통제 ·
코드로만 남기기). **대가 칸은 일곱 다 찼다.**

**⭐ ⑫ 가 다섯 번째로 값을 냈다 — 재독이 넷을 더 냈다**
- **북클럽이 엔지니어끼리**(대부분 개별 기여자에 매니저 몇) **시작해 제품·디자인·도메인
  전문가로 넓어졌고, 그것이 읽는 것에서 하는 것으로 넘어간 계기였다.**
- **워크숍 참가자가 영업·고객지원·제품·디자인·엔지니어링이고 여러 나라에서 왔다.**
- **⭐⭐ 급여 명세는 전에 *"considered as an internal implementation detail"* 이었다.**
  **무엇을 '내부 상세' 라고 부르는 순간 그것은 경계 밖이 된다**(이 사이트의 정리 — 난제로 세웠다).
  **이름이 볼 수 있는 것의 범위를 정한다.**
- **급여 기간의 근거가 나라다** — *"Usually, this is one month but some countries allow
  shorter periods too, for example one week"*.

**⚠️ 확인한 빈칸** — **코드나 시스템이 어떻게 됐는지가 없다.** 서비스가 나뉘었는지, 저장소가
갈렸는지, API 가 생겼는지 안 나오고 **바뀐 것은 다이어그램과 팀 구조다.** 그리고 **무엇이
안 됐는지에 대한 말이 없다** — 글은 축하조로 끝나고 `Architecture Modernization` 책에 실렸다는
것으로 맺는다. **2년을 썼는데 성과 수치가 하나도 없다.**

**⭐⭐ 난제 둘이 이 기능의 값이다**
- **이름이 경계를 정하는데 이름이 틀렸다는 것은 나중에야 안다** — 신호가 코드가 아니라
  **대화의 어긋남**으로 오고, 그 신호는 느리고 흐리다.
- **모델을 다시 그은 성과를 무엇으로 재는가** — 같은 기간에 사람도 제품도 조직도 바뀌어
  인과를 못 가른다. **그래서 이런 프로젝트는 대개 숫자를 못 적는다.**

---

**다음 사이클 — 두 편 규칙을 채운다.**
- **⭐ 1순위 — JetLang 본문을 찾는다.** **이 회사의 기반인데 한 줄 설명만 확인했다** —
  *"a low-code platform, to abstract the labour law into code"*. **노동법이 어떻게 실행 가능한
  코드가 되는지, 누가 쓰는지, 나라를 늘릴 때 무엇을 하는지가 전부 미확인이다.**
  **⚠️ ⑰ 주소를 추측하지 않는다. ⑱ WebSearch + allowed_domains 로 먼저 찾고**, 블로그에
  없으면 **컨퍼런스 발표·채용 페이지까지** 본다(**1차 자료가 아니면 그렇게 밝힌다**).
  **⭐ 규칙을 코드로 만드는 도메인은 이 사이트에 없는 결이다** — 서면 새 도메인을 연다.
  **⭐ 그리고 355 의 재료와 이어진다** — 급여 기간이 나라마다 다르다는 사실이 JetLang 이
  존재하는 이유일 가능성이 있다(**추정**).
- **2순위** — `Exploring our tech architecture vision`(2024-01-24, **⚠️ 비전 글이라 일반론일
  위험** — 336·353 의 전례) · `Our Data Assistant Adventure @ PayFit`(2024-04-17) ·
  `AI at PayFit`(2024-07-08) · `An introduction to load testing and k6`(2022-07-13).
- **3순위 — 닫는다.** 도메인 하나에 기능 하나가 있어 완주 기준은 이미 찬다.
- **⚠️ 엔지니어링 태그가 여덟 편뿐이고 최신이 2024-07-08 이다.**

**⚠️ 큐 0/3 — PayFit 을 완주하면 곧바로 후보 조사다.**
**후보 조사 누적 스물세 곳 중 아홉.** **⚠️ 요약만 보고 판정하면 과대평가가 난다**(354 의 정정) —
**다음 후보 조사부터는 '무엇이 없는지' 까지 물어 판정한다.**

**⭐⭐ 비교 문서 재료 다섯**(회사를 파는 중에는 손대지 않는다):
① **freee 대 SmartHR 대 PayFit — 같은 문제, 세 가지 답.** 셋 다 급여·인사 SaaS 이고 **제품이
늘며 경계가 무너진** 같은 문제인데, freee 는 **떼어냈고**(4년, 후회 명시), SmartHR 은 **규칙으로
긋다 안 되어 프로세스로 나눴고**, PayFit 은 **이름부터 다시 정했다**(2년, 성과 수치 없음).
**⭐ 355 에서 PayFit 쪽 재료가 굵어졌다.**
② **`미루되 미룬 것이 안 보이게 한다`** 에 SmartHR 두 사례.
③ **bol 이 ②의 셋째 사례.**
④ **`되돌릴 수 없는 것이 어디에 있는가` 에 bol.**

**분포** — 60곳(**US 22 · KR 9 · EU 9 · JP 7 · IN 3** · 기타 3 · CN 2 · CA·AU·SG·AE·NG 각 1) ·
비교 문서 32편 · **운영 사실 55개.**

**⚠️ 나르지 않는다** — 낡은 메모(314·317·325·348·349) · 두 방향 규칙(298·305·318·321·354) ·
주소가 열리는지도 확인한다(327·328) · 인용문에 다른 문자가 섞인다(330) ·
**한 글에 없다고 회사에 없는 것이 아니다**(331→332) · **도메인 이름이 좁으면 다음 재료가
안 들어온다**(334→335) · **자기 문서 인용도 우리말은 굵게**(337) · **같은 프로젝트라도 각도가
다르면 다른 기능이다**(339→340) · **같은 회사의 같은 아픔이라도 층이 다르면 다른 도메인이다**
(341) · **확인 안 된 인용을 지어내지 않는다**(341·342) · **읽은 글을 미독 목록에 남기지
않는다**(342·345) · **세 편을 열고 하나도 안 쓰는 사이클이 정상이다**(343·353) ·
**`domain_map`·`diagrams` 는 객체다**(344) · **`features_done` 을 같이 올린다**(345) ·
**두 도메인이 같은 문제에 정반대로 답하면 `connections` 에 적는다**(346) ·
**`-c "…"` 안에 백틱 금지**(347) · **프로파일의 '아직 한 편만 읽었다' 류 문장은 닫을 때
다시 본다**(348) · **URL 끝에 16진수 해시가 붙으면 Medium 커스텀 도메인이다**(349) ·
**`category`·`country` 는 허용값 집합이 있다**(350) · **같은 글을 세 번째 읽어도 새 사실이
나온다**(351) · **글을 열 때 '무엇이 없는지' 를 함께 묻는다**(352) · **실제로 실행하지 않은
평가는 구현 층이 없어 기능으로 못 쓴다**(353) · **요약만 보고 판정하면 과대평가가 난다**(354) ·
**⭐ 새로: 버린 대안이 없는 글에서도 결정을 세울 수 있다 — 갈림길을 글 안에서 찾고 버린 쪽을
'지금까지 그랬던 것' 으로 잡는다. 다만 그렇게 세운 대안은 이 사이트의 것이라고 밝힌다**(355).

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

**⑱ 블로그 페이지네이션을 못 뚫어도 `WebSearch` 에 `allowed_domains` 를 걸면 목록 밖 글을
찾을 수 있다.** 268 에서 `eng.snap.com` 의 `?page=2` 가 1쪽과 같은 것을 돌려주고 `/blog/2`
는 404 였는데, `WebSearch(allowed_domains=["eng.snap.com"])` 로 `/eyeconnect` ·
`/spectacles_supabase` 를 찾아냈다. **목록이 JS 로 도는 사이트에서 먼저 시도할 것.**


## 재시도 안 함

- **bol 의 `Database Setup So Easy, Your Cat Could Do It`**(2024-08-02, 353) — **튜토리얼이다.** 도커와 Flyway 로 로컬 데이터베이스를 띄우는 법이고 **버린 대안 0 · 대가 0 · 의미 있는 수치 0.**
- **bol 의 `shifting left and shifting right: Canary Releases`**(2024-05-22, 353) — **소개글이다.** Argo Rollouts 로 단계적 릴리스와 자동 되돌림을 한다는 것까지만 적고 **트래픽 비율·감시 지표·되돌림 기준·대가·수치가 전부 없다.** ⚠️ **짝인 `our Vision` 편도 같은 결일 가능성이 높다**(추정).

- **Personio**(EU · HR SaaS, 349) — 엔지니어링 글이 **`medium.com/inside-personio` 로 Medium 호스팅**이다. **Medium 전반이 이미 막힌 곳**이라 접는다. ⚠️ **HR 축이라 아까운 후보였다** — `www.personio.com/blog` 은 HR 마케팅 블로그다.
- **Deezer**(EU · 음악, 349) — `deezer.io` 가 자체 도메인처럼 보이지만 **URL 이 `/slug-11d3084cfd70` 형태의 Medium 커스텀 도메인**이다. 같은 이유로 접는다.

- **freee 의 QA 축**(343) — 분류가 95편으로 큰데 **두 편을 열어 두 편 다 수치가 하나도 없고 버린 대안도 없었다**(`QA活動について` 2023-12-21 · `CIの仕組みと課題` 2024-12-20). 대가는 적지만(테스트가 병목 · 시나리오 비대 · 실패 원인 판별 어려움) **재료로는 기준 미달이다.** 어드벤트 캘린더 연재라 결이 비슷할 것으로 보인다(**추정**) — 재방문 때도 이 축부터 열지 않는다.
- **freee 의 `安全なデータベース削除オペレーションの自動化事例`**(343) — Step Functions 와 Lambda 로 여섯 단계 삭제를 자동화한 이야기인데 **버린 대안 0 · 수치 0.**

- **Zoho**(IN · SaaS, 318) — **엔지니어링 블로그가 없다.** 검색이 제품·마케팅 페이지만 돌려준다.
- **Ola**(IN · 모빌리티, 318) — `blog.olacabs.com` 은 홍보 블로그다. 유일한 기술 글(Ola Maps, 2024-07-07)이 **발표문 성격이고 버린 대안 0 · 설계 대가 0**.

- **SoundCloud** — 311. `soundcloud.com/blog` 은 뉴스룸이고 `developers.soundcloud.com` 은 API 문서다. **엔지니어링 블로그가 없다.**
- **Kuaishou (快手)** — 311 검색. **전용 엔지니어링 블로그가 없다** — 오픈소스 저장소와 IR 블로그뿐. **Xiaohongshu 에 이어 중국 기업 두 번째 사례다.**
- **GetYourGuide** — 311. `inside.getyourguide.com` 이 채용 블로그로 리다이렉트되고, 기술 글 한 편을 열어 보니 **버린 대안 0 · 수치 0** 이었다.

- **Xiaohongshu (小红书)** — 305 검색. **전용 엔지니어링 블로그가 없다** — 3자 정리 글만 나온다. 중국 기업이 WeChat 공식계정을 쓰는 탓으로 보인다(추정).
- **HelloFresh** — `engineering.hellofresh.com` **403**(305).

- **`tech.meituan.com` 의 옛 글** — 2022~2025년 5월 글이 **전부 404** 다(300 에서 다섯 개 확인). 태그 목록(`/tags/...`)도 404. **살아 있는 것은 2025년 10월 이후로 보인다** — 홈(`/`)에서 직접 얻은 href 만 쓴다. **검색 결과가 주는 옛 주소를 믿지 않는다.**

- **Sea / Shopee** — `shopee` 는 DNS 없음, 298 에서 Sea Group 쪽 엔지니어링 블로그를 검색했으나 **1차 자료 주소 자체가 없다**(두 번째 실패).
- **VNG (베트남)** — 298 검색. **엔지니어링 블로그가 없다** — 회사 소개·채용 페이지뿐이다.
- **Tokopedia / GoTo** — 공식 블로그가 `medium.com/tokopedia-engineering` 로 **Medium 호스팅**이다.
- **Meesho** — `www.meesho.io/blog` **403**(298).
- **Rakuten** — `engineering.rakuten.today` 는 열리지만 **최신 글이 2023-10 이고 대부분 2021년**이라 사실상 멈췄다(298).
- **Dream11** — `tech.dream11.in` 은 열리지만 **최신 2024-10**, 본문을 열어 보니 **버린 대안 0 · 대가 0** 이라 기준 미달(298).

- **Lyft** — `eng.lyft.com` 이 **Medium 커스텀 도메인**이다(글 URL 에 `?gi=` 가 붙고 `/feed`
  가 *"Lyft Engineering - Medium"* 이다). 자체 호스팅 경로가 따로 없다.
- **Trendyol · Hepsiburada** — 둘 다 **Medium**(`medium.com/hepsiburadatech` 등). 자체
  기술블로그 도메인이 안 나온다.

**⑲ 후보를 올리기 전에 `index.json` 의 완료 목록과 대조한다.** 273 에서 trivago 를 새
후보로 올렸는데 **2026-08-22 에 이미 `done` 이었다**(기능 2개, 근거로 삼은 글까지 이미
소스에 있었다). 282 에서 새 프로파일을 쓰다 **회사 파일을 덮어썼고 index 중복 assert 로
알아채 `git checkout` 으로 복구했다.** 한 줄로 확인한다:
`python3 -c "import json;d=json.load(open('jd-viewer/public/reveng/index.json',encoding='utf-8'));print(sorted(e['slug'] for e in d['companies']))"`
**블로그 주소가 아니라 회사 단위로 본다.**


- **Plaid** — `plaid.com/blog/...` 가 전부 **`engineering.plaid.com`(Medium 커스텀 도메인)
  으로 301** 되고 그쪽은 **403**. 내용은 좋아 보였는데(Aurora MySQL → TiDB, **12k writes/sec**
  병목, 우회 설계에 **연 2 엔지니어-년**) **본문을 못 받는다.**
- **Zepto** — `blog.zepto.com` **403**.
- **Skyscanner · Traveloka · Carousell · Expedia Group** — 전부 **Medium 호스팅**.
  (Medium 호스팅 전반은 이미 막힌 곳이다.)
- **아프리카 — 두 번째로 빈손.** Jumia · Chipper Cash · Yoco · Safaricom 을 찾았으나
  **엔지니어링 블로그 자체가 없다**(팟캐스트·업계 뉴스만). Paystack·Flutterwave 에 이어
  둘째다 — **새 단서 없이는 다시 찾지 않는다.**

- **Cygames** `tech.cygames.co.jp` — **두 방법으로 두 번 다 실패했다**(252 WebFetch · 253 브라우저 `get_page_text`). 둘 다 *"본문 없음"* 이고 `/archives/` 는 404 다. **게임 자리(Roblox 하나뿐)를 메울 유일한 실마리였지만 접는다.** 새 단서(다른 도메인의 목록 주소)가 없으면 다시 열지 않는다.

- **Gojek** `www.gojek.io/blog` — **429 가 세 번**(246 에 두 번 · 253 에 한 번). 시간을 두고 다시 두드렸는데도 같았다. **일시적 제한이 아닌 것으로 보인다.** 동남아 두 번째 자리 후보였다.

- **Cookpad** `techlife.cookpad.com` — **두 번 열어 두 번 다 얇았다**(238 · 246). 최신 글이 **2026-05-12** 이고 홈에 보이는 세 편이 *iOS Liquid Glass 대응 · RubyKaigi 부스 소개 · RuboCop 캐시* 라 **두 편 이상 묶이는 시스템 주제가 없다.** 페이지가 안 열리는 게 아니라 **팔 것이 없다.** 새 단서(설계 결정을 다루는 구체적인 글 주소)가 없으면 다시 열지 않는다.

*(두 번 찾아 두 번 다 없었던 것. 새 단서 — 회사의 새 글·새 발표 — 가 생기기 전엔 다시
꺼내지 않는다. 같은 벽을 반복해 들이받는 루프는 아무것도 만들지 않는다.)*

| 대상 | 무엇을 못 찾았나 | 확인한 사이클 |
|---|---|---|
| 카카오 | 동기화·다중 기기 (도메인 6/7 에서 멈춤, 완주 보류) | 028 에서 두 번째 확인 |
| Netflix `adaptive-playback` | 비트레이트 선택 알고리즘 자체(무엇을 보고 언제 전환하는지) | 자료가 2017·2018년 글뿐 |
