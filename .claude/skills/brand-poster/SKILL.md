---
name: brand-poster
description: Use when making or revising a company-specific job poster board (회사 전용 판, brand_<slug>.html, brands/<회사>.json) in design-lab, when a poster "looks AI-made", "looks the same as before", or all company boards look alike, or when `poster.collection gaps` lists companies without a board.
---

# 회사 전용 판 — 그 회사가 직접 만든 것처럼

공고 한 건을 **로고를 가려도 그 회사인 줄 아는** 인스타 한 장(1080×1350)으로 만든다.
`cd design-lab && python -m poster.post <공고키>` → `out/<공고키>/_post/01_표지.jpg · 02_본문.jpg` (+ `_preview.jpg`)

## 철칙

**판을 바꾸는 건 대표 물건(시그니처) 하나다.** 색·글꼴·웹 UI 는 회사를 구별하지 못한다 — 네 번 고쳐서 배웠다
(`references/history.md`). 시그니처와 그 매체를 정하기 전에 판을 그리지 않는다.

## 순서 — 건너뛰지 않는다

| # | 단계 | 산출물 | 됐다는 기준 |
|---|---|---|---|
| 1 | 공고 전문 가져오기 | `poster.jobsource.get(key)["full"]` | 원문 그대로(오탈자도) |
| 2 | **대표 물건(시그니처) 하나** ← 가장 중요 | `signature` (id · evidence · alternatives) | `evals.brand` signature-* |
| 3 | **매체 고르기** — 시그니처가 부르는 바탕·글 양·손 | `signature.medium` | medium-chosen · medium-unique |
| 4 | **표지와 본문 나누기** — 표지는 시그니처가 판 전체 + 공고에서 고른 한 줄, 전문은 본문 장 | 판의 기본 갈래 = 표지, `full` 갈래 = 본문 | cover-not-full |
| 5 | 보조 포인트 2개 이하 | `points` (나머지는 `points_set_aside`) | points-max-2 |
| 6 | 서체와 글자 세우기 | `ui.fonts_research` · `ui.embed_fonts` · `ui.type_plan` | 라이선스 근거 |
| 7 | 공식 자료 픽셀로 색 | `palette` · `ui.palette_v*` | 출처 |
| 8 | 원본 이미지 모으기·자르기 | `assets/companies/<회사>/` · `ui.images` | images-600kb |
| 9 | 판 `poster/templates/brand_<slug>.html` — 표지·본문 두 갈래 | `python -m poster.post <공고키>` → `out/<키>/_post/` | 본문 ≥16px · 넘침 없음 |
| 10 | 눈으로 검증 — 이전 판과 나란히, 사용자 판정 | `out/<키>/v*_v*.jpg` · `references/records.md` 에 판정 | 판정 '좋다' |

`python -m evals.brand <회사>` 에 실패가 하나라도 있으면 9단계(렌더)로 가지 않는다.
렌더는 한 번에 한 장 — 메모리를 보며(이 PC 16GB, 다른 앱과 같이 쓴다).

| 단계 | 읽을 것 |
|---|---|
| 1~5 공고·시그니처·매체·표지·보조 | `references/signature.md` |
| 6 서체·글자 세우기 | `references/type.md` |
| 7~8 색·이미지 | `references/color-image.md` |
| 9~10 판·검증·나노바나나 | `references/frame.md` · `references/nanobanana.md` |
| 지금까지의 판정(배울 거리) | `references/records.md` · `references/history.md` |
| 다음 회사·병렬 | `references/parallel.md` |

## 배우는 법 (TDD)

사용자 판정이 곧 시험이다. '별로' 가 나오면 → 그 이유를 실패하는 검사로 만든다
(`tests/test_brand_checks.py` 에 RED → `evals/brand.py` 에 GREEN) → 지금 회사들에 돌려 걸리는 곳을 본다 →
`references/records.md` 에 판정을 이어 적는다. 검사로 못 보는 것(인상·분위기)은 아래 멈춤 신호에 한 줄.

## 멈춤 신호

- "회사 색과 서체를 진짜로 바꿨으니 됐다" → v2 가 그걸로 '크게 달라진 게 없다' 를 받았다. 시그니처는?
- "포인트를 더 넣으면 풍성해진다" → 둘을 넘으면 장식이다(`points-max-2`).
- "로고 모양을 SVG 로 다시 그리자" / "붓글씨를 서체로 흉내 내자" → 흉내보다 원본(0절 4번). 원본 이미지를 잘라 넣는다.
- "레이아웃을 바꾸면 다른 판이다" → 다섯 판이 본문은 똑같았다. 다른 건 매체다(`medium-unique`).
- "공고 문장을 다듬자" → 한 글자도 안 고친다. 오탈자도 그대로.
- "규칙·검사·스킬을 고쳤으니 나아졌다" → 2026-10-19 판정 "skills 를 바꿔도 디자인은 똑같이 나오네". 판을 다시 찍어
  이전 판과 나란히 보여 주기 전에는 아무것도 나아지지 않았다.
- "표지 갈래만 넣으면 된다" → 본문이 18px 아래면 `post.py` 가 `full-a`·`full-b` 반쪽을 부른다. 판이 그 이름을 모르면
  표지를 두 번 그린다(컬리 v4). 갈래는 `V.startsWith('full')` 로 가르고 반쪽(a = 주요업무·자격요건, b = 우대사항·복지)을 넣는다.
- "바로 다시 찍자" → 먼저 지금 렌더를 `brand_v<n>_ig_portrait.jpg` 로 보존한다. 같은 날 올리브영 v2 를 찍다가
  v1 을 덮어써서 비교 그림의 '예전' 칸에 새 판이 들어갔다.

## 핑계와 반박

| 핑계 | 반박 |
|---|---|
| 웹사이트 버튼 색이 브랜드 색이다 | 롯데카드 웹 보라 ≠ LOCA BI 웜그레이. 공식 가이드 > 원본 에셋 픽셀 > CSS |
| CDN 에 서체가 있으니 써도 된다 | CDN 이 서빙한다고 라이선스가 아니다(Toss Product Sans) |
| 시그니처 후보는 하나 골랐으니 됐다 | 탈락 후보와 이유를 안 남기면 다음 사람이 같은 걸 또 판다 |
| 전문이 다 들어가야 공고다 | `text_load: full` 이면 13px 문서가 된다. 표지와 본문을 나눈다(2-1절) |
| 시간이 없으니 검증은 다음에 | 이전 판과 나란히 안 보면 '똑같다' 를 또 받는다(8절) |
