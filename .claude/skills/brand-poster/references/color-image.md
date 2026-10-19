# 판 만들기 — 색과 이미지

5~6단계. 검사: images-600kb. 원래 `design-lab/brand-poster 스킬` 였던 것을 절 번호 그대로 옮겼다.

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
