# 레퍼런스 리드로잉 — JPG → Figma

수집한 캡처를 **Figma 레이어로 다시 그린다.** 픽셀을 베끼는 게 아니라 텍스트는
텍스트로, 도형은 도형으로 되살려 만질 수 있게 만드는 작업이다.

## 왜 SVG 인가

Figma MCP 는 Starter 플랜에서 **월 20콜**이라 22건을 API 로 그릴 수 없다. Figma 는
SVG 를 임포트할 때 `<text>` 를 진짜 텍스트 레이어로, 도형을 벡터로, `id` 를 레이어
이름으로 풀어 준다 — 결과가 같고 쿼터를 안 쓴다.

## 쓰는 법

```bash
P=../catch_capture/.venv/bin/python

# 1) 배경을 벡터로 뜬다 (사진 → 격자 중앙값 색의 방사형 그라디언트 타원)
$P figma/analyze.py refs/instagram/crops/<파일>.jpg --cols 8 --rows 10 > /tmp/mesh.json

# 2) specs/<id>.json 을 만든다 — 배경 mesh + 손으로 적은 텍스트 레이어(fit 상자 포함)

# 3) 원본 캡처에 맞춰 크기·자간·위치를 자동 보정 (+ 서체 후보 고르기)
$P figma/calibrate.py <id> --pick-font
$P figma/calibrate.py <id> --verify      # 남은 오차(px)

# 4) SVG 로 뽑는다
$P figma/redraw.py <id>          # out/<id>.svg  — 원본 | 재구성 나란히
$P figma/redraw.py --all         # 전부 + out/board.svg (한 번에 임포트용)
```

Figma 에서 **File → Import**(또는 SVG 파일을 캔버스로 끌어다 놓기).

## 어디까지 같은가

| | 상태 |
|---|---|
| 배치·크기·자간 | 원본 잉크 상자에 맞춰 자동 보정. 남는 오차 대개 3px 안쪽 |
| 텍스트 | 진짜 텍스트 레이어. 내용·색·크기 전부 수정 가능 |
| 색 | 원본 픽셀에서 직접 샘플링 |
| **서체** | **확정 불가.** JPG 로는 알 수 없어 후보 11종 중 자간·획굵기 오차가 가장 작은 것을 고른다. `spec.font_note` 에 근거를 남긴다 |
| **사진·일러스트** | **원본 소스가 없다.** 격자 중앙값 색으로 흐린 근사만 만든다 |
| 해상도 | 인스타 캡처가 1080 이하 + JPEG 압축이라 미세 그라디언트는 근사치 |

`out/<id>_대조.png` 로 원본과 나란히 확인한다.

## 스펙 형식

```jsonc
{
  "id": "hire-03",
  "source": "refs/instagram/crops/....jpg",   // 대조용 원본
  "canvas": {"w": 1080, "h": 1350},
  "layers": [
    {"type": "rect",    "name": "바탕", "x":0, "y":0, "w":1080, "h":1350, "fill": "#04101d"},
    {"type": "ellipse", "name": "배경 1-1", "cx":.., "cy":.., "rx":.., "ry":..,
     "gradient": {"type":"radial", "stops":[{"at":0,"color":"#0667ae","opacity":1}, ...]}},
    {"type": "text",    "name": "직군 1 — Graphic", "text": "Graphic",
     "x":.., "y":.., "size":.., "tracking":.., "font": "Noto Serif", "fill": "#ffffff",
     "fit": {"x":92, "y":289, "w":660, "h":139}}   // 원본에서 잰 잉크 상자 = 보정 목표
  ]
}
```

`fit` 만 정확히 재 놓으면 크기·자간·좌표는 `calibrate.py` 가 알아서 맞춘다.
사람이 할 일은 **원본에서 글자 상자를 재고 문장을 옮겨 적는 것**뿐이다.

## 남은 것

- 22건 중 `hire-03` 만 완료. 나머지 21건
- `refs/instagram/crops/` 에 크롭이 14건뿐 — hire-07~web-03 은 아직 원본 캡처만 있다
- 한글 서체 후보가 없다(지금 후보는 라틴 세리프 11종). 국문 포스터는 본고딕·프리텐다드 계열을 받아 둬야 한다
