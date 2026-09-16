# 회사 전용 공고 포스터 — 자동화 절차서

공고 한 건을 **그 회사가 직접 만든 것처럼 보이는** 인스타 한 장(1080×1350)으로 만든다.
AI(또는 병렬 작업자)에게 이 문서를 그대로 주고 돌린다. 공고 전문을 한 장에 담는 틀·렌더러
사용법은 [ONEPAGE.md](ONEPAGE.md), 나노바나나로 다듬는 법은 [NANOBANANA.md](NANOBANANA.md).

```bash
cd design-lab
python -m poster.carousel <공고키> --one --frame brand      # → out/<공고키>/brand_ig_portrait.jpg
```

---

## 0. 이 절차가 이렇게 된 이유 (2026-09-15, 6개 회사로 네 번 고쳤다)

| 판 | 무엇을 했나 | 사용자 판정 |
|---|---|---|
| v0 | 회사 색 + 제품 모양 장식 SVG + 수치 카드 | "너무 AI 스럽다" |
| v1 | 웹 CSS 에서 색·글꼴을 뽑아 레퍼런스 틀에 칠함 / 웹·앱 화면에서 포인트 | "포인트가 없다, 이전과 똑같다" |
| v2 | 실제 전용 서체 조사 + 공식 자료 픽셀 색 + 실제 브랜드 이미지 | 롯데카드·배민만 **크게 좋아짐**, 나머지 넷은 "크게 달라진 게 없다" |
| v3 | 사람들이 그 회사로 기억하는 **대표 물건(시그니처) 하나**를 판의 중심에 | "**훨씬 더 좋아졌다**" |

배운 것:

1. **색·글꼴·웹 UI 는 회사를 구별하지 못한다.** 흰 바탕 + Pretendard + 강조색 하나는 거의 모든 회사다. 웹 버튼 색은 브랜드 색이 아니다(롯데카드 보라 ≠ LOCA BI 웜그레이).
2. **서체·색을 '진짜'로 바꿔도 뼈대가 웹 UI 면 인상은 안 바뀐다.** (토스·컬리·카카오뱅크·무신사 v2)
3. **판을 바꾸는 건 대표 물건이다.** 롯데카드 = LOCA 네 창문 + 동판화 맨해튼 지도, 배민 = '송파구에서 일을 더 잘하는 11가지 방법' 포스터 + 사명 붓글씨. 이게 판의 얼굴이 된 회사만 좋아졌다.
4. **흉내보다 원본.** 손으로 그린 지도 SVG·서체로 흉내 낸 붓글씨보다 회사가 만든 원본 이미지를 넣은 판이 낫다.

---

## 1. 순서 — 건너뛰지 않는다

| # | 단계 | 산출물 |
|---|---|---|
| 1 | 공고 전문 가져오기 | `poster.jobsource.get(key)["full"]` |
| 2 | **대표 물건(시그니처) 찾기** ← 가장 중요 | `brands/<회사>.json` 의 `signature` |
| 3 | 보조 포인트 2개 이하 | `points` |
| 4 | 실제 서체 조사 → 무료면 그대로, 전용이면 비교해 대체 | `ui.fonts_research`, `ui.embed_fonts`, `out/<키>/v*_font_specimen.jpg` |
| 5 | 공식 자료 픽셀로 색 | `ui.palette_v*`, `out/<키>/v*_palette.jpg` |
| 6 | 실제 이미지 모으기·자르기 | `assets/companies/<회사>/sources/`, `v*/`, `images` |
| 7 | 전용 판 `poster/templates/brand_<slug>.html` | 렌더 결과 |
| 8 | 눈으로 검증·반복, 이전 판과 나란히 | `out/<키>/v*_v*.jpg` |
| 9 | 나노바나나 묶음 + 기록 | `out/<키>/nanobanana/`, `out/<키>/RECORD_v*.md` |

### 1) 공고 전문

- `jobsource.get(key)["full"]` — tasks(소제목 묶음) / qualifications / preferences / benefits({label,text}).
- 가능하면 대시보드(5173 `/jobs/<키>`) 텍스트와 줄 단위 대조. 병렬 작업이라 브라우저를 못 쓰면 원본 필드와 대조하고 기록에 적는다.
- 원문 오탈자도 그대로 둔다(컬리 '보유이 있는 분').

### 2) 대표 물건(시그니처) — 판의 얼굴

**질문: "로고를 가려도 이 회사인 줄 아는 물건이 뭔가?"**

찾아볼 곳(웹 UI 는 여기 없다):

| 종류 | 예 (실제로 고른 것) |
|---|---|
| BI 의 구조 | 롯데카드 LOCA 네 창문 + 나침반 별 |
| 사내 문화물 | 배민 '11가지 방법' 포스터 |
| 캠페인·광고 키 비주얼 | 토스 10주년 '10 to 100' 숫자 조합 |
| 서비스의 상징 장면 | 컬리 샛별배송 — 새벽 고속도로의 보라 트럭 |
| 대표 상품 실물 | 카카오뱅크 세로형 체크카드 |
| 회사 이름·기원 | 무신사 '무진장 신발 사진이 많은 곳' 2001 픽셀 도시 키 비주얼 |
| 그 밖 | 포장·배송차·매장, 사명 레터링, 책·컨퍼런스 키 비주얼, 이모지·전용 그래픽 |

고르는 기준 — 넷 다 맞아야 한다:

1. **알아본다** — 회사 밖 사람도 그 회사로 안다(보도·후기에 반복 등장).
2. **공식이다** — 회사가 직접 만들었거나 공식 채널에 있다. 근거 URL 필수.
3. **쓸 수 있다** — 로고 변형·캐릭터(카카오프렌즈 등)·실존 인물 사진이 중심이면 탈락. 로고 규정이 있으면 따른다.
4. **공고와 이어진다** — 억지로 붙이지 않는다. 좋은 예: 토스 '10 to 100' ↔ 경력 '2-10년', 카카오뱅크 흰 커스텀 카드의 새김 문구 ↔ '경력 5년 이상', 배민 취소선 고침 ↔ 원문 '월요일 오전은 쉬고 1시부터 코웍'.

**하나만 고른다.** 탈락한 후보와 이유를 반드시 남긴다 — 다음 사람이 같은 걸 또 파지 않게.

```json
"signature": {
  "id": "10-to-100",
  "what": "눈에 보이는 말로 — 검정 정사각 숫자 · 검정 원 'to' · 검정 상자 숫자",
  "evidence": ["공식 URL + 그 페이지의 문장", "보도 URL"],
  "why_recognizable": "왜 이 회사로 알아보나",
  "how_used": "판에서 어디에 어떻게 — 구조/머리/이미지",
  "not_used": "원본에서 일부러 뺀 것(로고 모양 입자 등)",
  "alternatives": [{"what": "후보", "why_not": "탈락 이유"}]
}
```

### 3) 보조 포인트 — 2개 이하

`points[]` 형식 `{id, what, evidence, meaning, use, avoid}`. 웹·앱 화면에서 온 것은 **보조로만**.
장치를 더 넣으면 다시 장식이 된다.

### 4) 서체 — 실제로 쓰는 것을 찾는다

찾는 순서:

1. **공식 가이드·BI 페이지** 문구(서체명, '산세리프를 볼드하게 변형' 같은 설명).
2. **웹 @font-face** — 회사·채용·스토어 사이트 CSS 와 계산된 스타일(`getComputedStyle`), 폰트 파일 경로.
3. **PDF 에 박힌 서체명** — pymupdf `page.get_fonts()`. 윤곽선 변환(Type3/outline)이면 이름이 없다.
4. **글자 모양 대조** — 공식 이미지에서 글자를 흑백으로 떠서 후보를 같은 글자·크기로 찍고 겹침(IoU)·폭 비율 비교. 수치는 자간에 민감하니 **최종 판단은 눈으로**.
5. 회사가 **무료 공개한 서체**(배민 12종, 카카오 큰글씨/작은글씨 등)는 쓰였다는 근거가 있을 때만.

라이선스:

- **CDN 이 서빙한다고 라이선스가 아니다.** (Toss Product Sans, 무신사 CDN)
- 쓸 수 있는 것: SIL OFL, 회사가 상업 사용을 명시한 무료 서체(배민 문구 '포스터·광고·로고 사용 가능, 파일 판매 금지'), 토스페이스(저작권 표시 조건).
- 전용 서체면 **비교 이미지**(`v*_font_specimen.jpg`)를 만든다 — 원본 글자(사이트에 로드된 웹폰트로 찍은 비교용 캡처) vs 무료 후보 4~6개, 같은 문장·숫자(예: `DevOps Engineer 2–10년`, `12,345원`, `(4/7) 99.9%`).

이번에 나온 답:

| 회사 | 실제 | 판에 쓴 것 | 근거 |
|---|---|---|---|
| 롯데카드 | 로고는 레터링, 웹 Noto Sans KR | Noto Sans KR + Montserrat 800(LOCA 머리글자) + EB Garamond 스몰캡 | 공식 이미지 글자 겹침 비교 |
| 배민 | WORK체 미배포 | 배민 한나체 Pro + Pretendard + 연성체 | 공식 11종 같은 문장 비교 |
| 토스 | Toss Product Sans(전용) | Wanted Sans + 토스페이스 | toss.im TPS 렌더 vs 후보 5 |
| 컬리 | 웹 Pretendard | Pretendard(+ 박스 라벨 Montserrat) | 사이트 폰트 토큰 |
| 카카오뱅크 | 가이드 PDF 가 Pretendard 조판 | Pretendard, 가이드 굵기 규칙 | 가이드 글자 겹침 1위 |
| 무신사 | 스토어·회사·채용 Pretendard | Pretendard + Inter Tight 900 + 갈무리11(픽셀) | 서체 파일 경로 + BI 사진 비교 |

`ui.embed_fonts` — 굵기별 파일 목록을 받는다(woff2/ttf/otf, 렌더러가 data: URI 로 넣음):

```json
"embed_fonts": {
  "Wanted Sans": [{"src": "assets/companies/토스/fonts/WantedSans-Bold.woff2", "weight": 700}],
  "BM HANNA Pro": "assets/companies/우아한형제들/fonts/BMHANNAPro.ttf"
}
```

### 5) 색 — 공식 자료 픽셀

우선순위: **공식 가이드 표기(Pantone/CMYK/HEX)** > **원본 에셋 픽셀**(로고·앱 아이콘 PNG, 카드 플레이트, 캠페인 이미지) > 디자인 시스템 CSS 토큰 > 그 밖 CSS.

- JPG 기사 캡처는 압축으로 색이 틀어진다(배민 2.0 칩 JPG `#6DEBD5` ↔ 원본 `#0CEFD3`). PNG·원본으로 확인.
- 색마다 `{hex, name, source, use}`. **쓰지 않은 색도 이유와 함께** 남긴다(할인 빨강, 상품별 색, 옛 CI 색, 웹 버튼 색).
- 견본 이미지 `v*_palette.jpg`.

### 6) 이미지 — 원본을 판에 넣는다

- 시그니처의 **실제 이미지**를 넣는다. 원본이 있으면 손으로 다시 그리지 않는다.
- 로고·캐릭터·다른 회사 로고(카드사 마크 등)가 초점이 되지 않게 자른다. 못 자르면 기록에 적는다(컬리 트럭 로고).
- `assets/companies/<회사>/v*/` 에 잘라 저장(장당 600KB 이하), 브랜드 JSON:

```json
"images": {"map": "assets/companies/롯데카드/v2/map_manhattan_star.jpg"},
"images_note": {"map": "어느 원본의 어느 영역을 왜 잘랐나 + 권리 메모"}
```

- 판에서는 `D.brand_images.map` (data: URI).
- 원본 수집물은 `sources/<NN_출처>/` + `manifest.json`(url·alt·크기) + `_sheets/*.jpg`. 옆 광고·무관 이미지는 뺀다.

### 7) 전용 판 `brand_<slug>.html`

- 뼈대: `/*__FONTS__*/` `/*__DATA__*/` `/*__FRAME_JS__*/` + `Frame.init()` / `Frame.fit()` (예: `brand_toss.html`, `brand_baemin.html`). 브랜드 JSON 의 `"frame": "brand_<slug>.html"`.
- **시그니처가 판의 얼굴**(머리 전체 또는 구조). 보조는 거들기만.
- 공고 글은 **한 글자도 바꾸지 않는다.** 섹션 제목도 원문 대괄호가 있으면 그것(토스 해요체).
- **경력은 크게**, 시그니처와 엮을 수 있으면 엮는다.
- 지어낸 카피 금지. 회사가 쓴 문장(슬로건·캠페인 문구·채용 사이트 문장)은 그대로 인용 가능.
- 금지: 장식 SVG, 강조 막대 수치 카드, 색 사각 불릿, 브랜드가 안 쓰는 알약 칩, 흐린 드롭섀도, 로고 다시 그리기.

`Frame.fit` 함정 (실제로 걸린 것):

- 일부러 밖으로 삐져나오게 둔 장식(잘린 큰 글자 등)은 넘침 판정에서 뺀다 — 안 빼면 글자가 10px 까지 줄어든다(컬리).
- `main` 의 아래 padding 이 넘침으로 계산된다 — 여백은 바깥 요소로(카카오뱅크).
- 남는 자리를 채우는 사진 칸은 판정에서 빼고 최소 높이만 본다(카카오뱅크).
- 두 단 나누기는 **섹션 순서를 지킨 모든 조합** + 단 폭 비율 후보(1 / 1.15 / 1.3) 를 넣는다. grid 는 `minmax(0,1fr)`(무신사).
- 머리가 커지면 본문이 12~14px 로 떨어진다 — 첫 렌더가 16px 아래면 머리부터 줄인다(모든 회사가 한 번씩 걸림).
- 한 글자 줄넘김은 `text-wrap: pretty`.

### 8) 검증 — 눈으로, 이전 판과 나란히

완료 기준:

- [ ] 로고를 가려도 그 회사로 보인다(시그니처가 얼굴)
- [ ] **이전 판과 확실히 다르다** — `v(n-1)_v(n).jpg` 로 나란히 본다
- [ ] 본문 ≥ 16px(CLI 는 18px 아래면 경고만), 넘침·잘림·겹침 없음
- [ ] 읽는 순서 주요업무 → 자격요건 → 우대사항 → 복지
- [ ] 원문 전 줄 대조, 경력 표기 정확
- [ ] 로고 변형·캐릭터·유료 서체 없음
- [ ] 권리 메모: 넣은 회사 이미지마다 '공개 게시 전 사용 허락 확인'

### 9) 나노바나나 묶음 + 기록

- `out/<키>/nanobanana/` — 1번 = 최신 렌더, 역할당 한 장, `PROMPT.md`(A 전체 / B 배경만 / C 고치기 / 확인 목록). 이전 묶음은 `_v*/` 로. 형식은 NANOBANANA.md.
- `out/<키>/RECORD_v*.md` — 판정 → 시그니처(근거·대안) → 보조 → 서체(라이선스·선택 이유) → 색 → 이미지 → 처음 판 문제와 수정 → 남은 것·권리. 끝나면 ONEPAGE.md '기록' 에 합친다.
- 새 판을 만들기 전에 현재 렌더를 `brand_v*_ig_portrait.jpg` 로 보존한다.

---

## 1-1. 다음에 만들 회사는 묶음이 알려 준다

묶음(카테고리) 게시물은 **전용 판이 있는 회사만** 넣는다(`poster/collection.py`). 그래서 다음에
어느 회사 판을 만들어야 하는지는 묶음이 알려 준다 — 채우려는 카테고리로 물어보면 된다.

```bash
cd design-lab
python -m poster.collection gaps newgrad          # 신입 묶음에서 전용 판이 없어 빠지는 회사
python -m poster.collection gaps role --value backend
```

회사 규모 → 모집중 공고 수 순으로 나온다. 위에서부터 이 절차(아래 2절의 작업자 지시문)로 만들면
그 카테고리가 채워진다.

## 2. 병렬로 돌리기

여러 회사를 한 번에 할 때는 회사마다 작업자 하나. **파일 소유권을 나눈다.**

| 작업자가 고쳐도 되는 것 | 건드리면 안 되는 것(메인만) |
|---|---|
| `brands/<그 회사>.json` | `ONEPAGE.md` `BRAND_RESEARCH.md` `NANOBANANA.md` `README.md` |
| `poster/templates/brand_<그 회사>.html` | `poster/carousel.py` `poster/templates/_frame.js` |
| `assets/companies/<그 회사>/` | 다른 회사 파일 |
| `out/<그 공고키>/` | git 커밋 |

- 공유 브라우저(claude-in-chrome)는 작업자끼리 탭이 엉킨다 → 작업자는 WebSearch/WebFetch/curl + Playwright 헤드리스(`poster.render._page_maker`)로 캡처.
- 렌더러 변경이 필요하면 작업자는 고치지 말고 보고만 → 메인이 반영.
- 메인이 할 일: 결과 판을 **직접 열어 확인**, 비교 시트(`out/brand_compare_*.jpg`), 기록 합치기.

작업자 지시문 틀(회사·공고키·후보만 바꾼다):

```
You are a fork. Make v<N> of the <회사> brand poster (job <공고키>). Read design-lab/BRAND_RESEARCH.md and follow it in order.
Existing files to read first: brands/<회사>.json, poster/templates/brand_<slug>.html, out/<공고키>/RECORD*.md. Keep the current render as brand_v<N-1>_ig_portrait.jpg.
1. Find the ONE signature artifact (section 2). Candidates to check: <후보 목록>. Record evidence URLs, alternatives with reasons.
2. Fonts (section 4): actual fonts + licenses; specimen image if proprietary.
3. Colors (section 5): official/pixel-sampled palette with sources; swatch image.
4. Images (section 6): put real signature imagery into the poster via "images".
5. Template + render: cd design-lab && python -m poster.carousel <공고키> --one --frame brand; look at the jpg and iterate until section 8 checklist passes and it clearly differs from v<N-1>.
6. v<N-1>_v<N>.jpg, nanobanana pack, RECORD_v<N>.md.
HARD RULES: only touch the files listed as yours in section "병렬로 돌리기". No mcp__claude-in-chrome tools. No git commits. Label unverified claims.
Final report (short): signature + evidence, alternatives, fonts/colors/images, body px, paths, remaining issues, rights.
```

---

## 3. 지금까지의 결과 (2026-09-15)

| 회사 · 공고 | 판 | 시그니처 | 비교 |
|---|---|---|---|
| 롯데카드 · wanted-370751 | v2 | LOCA 네 창문 + 회사소개 동판화 맨해튼 지도·스카이라인 | `out/wanted-370751/v1_v2.jpg` |
| 우아한형제들 · wanted-366409 | v2 | '11가지 방법' 포스터 구조 + 사명 붓글씨·워드마크 원본 | `out/wanted-366409/v1_v2.jpg` |
| 토스 · wanted-335070 | v3 | 10주년 '10 to 100' 숫자 조합 → `2 · to · 10` + 토스페이스 | `out/wanted-335070/v2_v3.jpg` |
| 컬리 · wanted-340803 | v3 | 샛별배송 — 새벽 트럭 사진 + '샛별이 뜰 때가 가장 신선할 때' + 배송 안내 모듈 | `out/wanted-340803/v2_v3.jpg` |
| 카카오뱅크 · wanted-359731 | v3 | 세로형 체크카드(공식 검정·노랑 + '경력 5년 이상' 새긴 흰 카드) | `out/wanted-359731/v2_v3.jpg` |
| 무신사 · wanted-375793 | v3 | '무진장 신발 사진이 많은 곳' 2001 픽셀 도시 키 비주얼 | `out/wanted-375793/v2_v3.jpg` |

전체: `out/brand_compare_6_latest.jpg`, 네 회사 v2→v3: `out/brand_compare_4_v2_v3.jpg`.

남은 과제: 카카오뱅크는 머리만 바뀌고 본문 구조는 v2 그대로 / 토스 왼쪽 단 여백 / 무신사 윤곽 글자가 회색으로 보임 / 컬리 트럭 사진 속 로고.
**모든 판에 회사 이미지·캠페인 비주얼이 들어 있다 — 인스타 공개 게시 전 회사별 사용 허락 확인.**
