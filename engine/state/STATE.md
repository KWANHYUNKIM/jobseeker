# 진행 상황

엔진은 실행 사이에 기억이 없다. **다음 실행이 이어받을 맥락만** 여기에 남긴다.

> 이 파일은 매 사이클 통째로 읽힌다. 그래서 **자란다면 잘못 쓰고 있는 것이다.**
> 사이클 기록은 `LOG.md` 로 간다(엔진은 그 파일을 읽지 않는다). 여기 남기는 것은
> "다음 실행이 모르면 헛수고할 것"뿐이다. 각 절의 규칙은 절마다 적어 뒀다.

## 지금 파는 중

*(덮어쓴다. 이어붙이지 않는다.)*

**아무 회사도 파는 중이 아니다 — ByteDance 가 완주해 24곳이 전부 done 이다.**
다음 사이클은 `--gaps` 가 '사다리를 더 내려간다'를 내놓을 것이고, **큐 맨 위(Spotify)를 새로 연다.**

> **Spotify 를 열 때 알아야 할 것** — `engineering.atspotify.com` 은 **목록만 확인했고 본문은
> 미확인**이다. **팔기 전에 본문을 하나 열어 확인할 것**(후보: 'Indexing the Data Lake for Online
> Point Queries', 2026-07). 최근 글이 LLM·데이터 플랫폼에 쏠려 있어 추천·스트리밍 축은 Netflix·
> YouTube 와 겹칠 위험이 있다 — **오디오와 팟캐스트의 차이**(길이·소비 맥락·라이선스)를 축으로
> 잡는다. **본문이 안 열리면 미루고 Canva 나 Grafana Labs 로 넘어간다**(둘 다 본문 확인 완료).

> **🚫 재시도 안 함 (유효):** ByteDance 의 LavaStore·ByteGraph·ByteHTAP 은 **VLDB PDF** 라 못 읽는다.
> WebFetch 가 두 번째 호출에서 "바이너리 PDF 스트림"이라 답했고 **첫 호출 요약은 수치를 지어낸
> 것**이었다(전부 '30-40%' 같은 범위). 로컬에 poppler·pypdf·pdftotext 전무.
> **교훈: WebFetch 요약의 수치가 전부 '범위'로 나오면 같은 URL 을 한 번 더 불러 본다.**
> ✅ 반면 **arXiv 는 잘 읽힌다** — `arxiv.org/html/<id>v1` 또는 `ar5iv.labs.arxiv.org/html/<id>`.
> `arxiv.org/abs/<id>` 는 초록만 준다. 논문 축의 회사는 이 경로로 연다.

> **ByteDance 에서 나온 것 — 네 논문에 걸친 습관 넷.** ① **하드웨어 지표를 믿지 않는다**
> (decode GPU 사용률이 거짓말한다 · 마이크로벤치마크에 안 보이는 느린 기계 · GPU 99%가 60% 미만인
> 것은 게으름이 아니라 구조) ② **감수할 손실을 숫자로 계산한다**(10일마다 15,000명의 하루치 ·
> 온라인 감속 10ms) ③ **버린 대안을 표로 남긴다** ④ **경험적으로 고른 값을 경험적이라고 적는다.**

> **한 회사 안에 대비되는 짝이 셋** — Monolith(작은 갱신이 끝없이) ↔ MegaScale(한 판을 수 주),
> MegaScale(학습이 만 대를 오래) ↔ HeteroScale(추론이 수만 대를 시시각각),
> MuxFlow(남는 자리에 밀어 넣는다) ↔ HeteroScale(자리 자체를 늘렸다 줄인다).
> **네 논문 중 어느 것도 서로를 인용하지 않는다** — 연결은 전부 이 사이트의 해석이다.

> **비교 문서 후보 여섯 — 이제 ①과 ⑥이 재료가 찼다.** ① **완벽한 탐지를 포기하고 확률로 좁히는
> 자리**(LY 어테스테이션 · Discord 안전 · 유튜브 Content ID · 토스 이상거래). ⑥ **무엇을 보고
> 늘릴 것인가 — 신호 고르기**(ByteDance decode TPS · MuxFlow SM 클럭 · MegaScale CUDA 이벤트 ·
> 다른 회사에 같은 축이 있는지 확인 필요). 그 밖에 ② 틀려도 되는 일 vs 틀리면 안 되는 일
> ③ 양 끝 대신 축을 바꾸는 수 ④ 작은 파일 문제 ⑤ 합병으로 시스템이 두 벌이 된 회사.

**큐 잔량 3/3.** Spotify → Canva → Grafana Labs.

마지막 사이클: 152 (2026-08-21) — ByteDance MuxFlow. **ByteDance 완주, 24곳 전부 done.**

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
