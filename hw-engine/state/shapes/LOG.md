# 3D 모양 레인 — 기록

회차마다 한 단락: 무엇을 어떤 공식 자료로 적었나 · 실물과 아직 다른 점(렌더러 요청은 REQUESTS.md 로).

## 2026-11-23 · 1회차(사람이 지시한 세션) — 기본 조합의 대표 제품 4개

- 적은 것: XFX Swift RX 9070 XT(gpu-rx-9070-xt) · DAVEN D7 Mesh 세븐팬(case-atx-mid) · DEEPCOOL AG400 G2(cooler-air-single) ·
  ASUS TUF B850M-PLUS WIFI7(mb-b850). 모두 제조사 공식 제품 페이지의 사진(보기만)과 사양표. 다나와는 가격·링크만 쓰는 규칙이라 모양 근거로 쓰지 않았다.
- AG400 G2 의 공식 크기 125×92×152 가 노트에만 있어 models 칸(width_mm·depth_mm)으로 옮겼다.
- 사진과 견줘 렌더러를 고친 것: 팬 날개 수·허브 로고·RGB 고리(사진의 무지개 팬) / 메시 앞판이 멀리서 꽉 막혀 보이던 것(알파 시험 → 반투명) /
  케이스 철판을 금속 반사 → 분체 도장 무광(사진처럼 안이 검다) / 유리를 어두운 유리로 / 그래픽카드 히트파이프를 핀 안으로(옆에는 핀만) /
  트레이 뚫린 구멍·CPU 뒷면 구멍·덮개 타공 옆면·가로 막대 발·슬롯 옆 타공 띠 / 보드 큰 I/O 덮개·M.2 x16 아래·CPU 보조전원 8+8·노란 포인트 /
  쿨러 직접 접촉 베이스·계단 핀·공식 깊이 / 부품을 누르면 카메라가 그 부품으로 다가간다.
- 실물과 아직 다른 점: 그래픽카드 옆 'RADEON' 글자·브랜드 로고 글자는 그리지 않는다(글자 렌더러 없음). 보드의 작은 부품(콘덴서·칩·단자 모양)은 대략.
  쿨러 날개 모양은 일반형. 팬 LED 는 빛만 있고 주변을 비추지 않는다.

## 2026-11-23 · 2회차(무인) — 그래픽카드 인기순 앞 5개

- 적은 것: GALAX RTX 5080 1-Click OC 3X(medium — 공식 표 3×92mm·2.5슬롯·백플레이트·ARGB, 공식 사진 정면·측면 4장으로 날개 7장·반투명 ARGB 팬·검정 쉬라우드에 은색 회로 무늬) ·
  Palit RTX 5090 GameRock(medium — 공식 표 3.5슬롯·16핀, 공식 사진 1장으로 검정 쉬라우드 + 연두·금·보라로 바뀌는 Chameleon ARGB 판, 팬엔 불빛 없음) ·
  COLORFUL RTX 5060 Ti Gaming DUO 16G · RTX 5050 Gaming DUO · iGame RTX 5060 Ti Ultra DUO OC(셋 다 low — 공식 페이지 Feature Highlights 문구의 색·'Hollowed Backboard' 만).
  사진은 WebFetch 가 세션 임시 폴더에 받은 것을 화면으로 보기만 했다(저장소에 두지 않음). 다나와는 쓰지 않았다.
- 막힌 것: COLORFUL 공식 이미지 서버(`/en/content/upload/Images/…`)가 403, 스펙 탭은 JS 로 불러와 텍스트로 안 온다 — 우회하지 않았다. 그래서 COLORFUL 셋은 팬 지름·슬롯·보조전원 자리가 비었다(렌더러가 models 의 팬 2개·8핀 1개로 그린다).
  GALAX 의 16핀 자리·백플레이트 뚫린 범위, Palit 의 팬 지름·날개·백플레이트·플로스루는 사진 각도로 안 보여 비웠다.
- 실물과 아직 다른 점: GameRock 의 곡선 발광 판·GALAX 의 옆면 발광 띠는 accent 한 색으로만 보인다. Palit 은 fans 를 못 적어 models 의 팬 수(null)로 그린다. REQUESTS 에 [3D 렌더러] 3줄·[hw-models] 1줄(low 항목 재방문, 팬 개수만 적는 칸, 발광 판, Palit 팬 수).

## 2026-11-23 · 3회차(무인) — 그래픽카드 인기순 다음 4개

- 적은 것(모두 medium, 공식 제품 페이지 문구 + 공식 사진을 화면으로 보기만): Palit RTX 5050 StormX(사양 탭 2슬롯, 정면 사진으로 팬 1개·검정 홈 무늬 — 지름·날개·백플레이트는 자료에 없어 fan_count 만) ·
  Palit RTX 5060 Ti Dual 8GB(문구 95mm 팬 2개·2슬롯·백플레이트·subtle RGB, 사진의 윗면 'DUAL' 옆 녹색 줄을 옆 발광 띠로 판독) ·
  GALAX RTX 5060 Ti 1-Click OC V2 8GB(국내 BLACK OC V2 — 표 2×92mm, 날개 7장, 뒷면 사진으로 백플레이트 끝 절반이 뚫린 플로스루와 PCB 끝(약 55%) 보조전원 자리) ·
  GALAX RTX 5060 Ti 1-Click OC 16GB(국내 BLACK OC — V2 와 같은 앞판, 뒷면 사진을 못 찾아 플로스루·전원 자리는 비움). 다나와는 쓰지 않았다.
- 막힌 것: MSI RTX 5060 VENTUS 2X OC V1 — msi.com 403(우회 안 함), 데이터시트 PDF 는 이 PC 에 읽을 도구가 없어 건너뛰었다(REQUESTS [hw-models]).
- 실물과 아직 다른 점: GALAX 두 장의 팬은 흰색으로만 빛나는데 형식에 흰 단색이 없어 불빛 없이 그려진다(REQUESTS [3D 렌더러]). GALAX 쉬라우드의 탄소·회로 무늬와 Palit 의 굽이치는 홈은 무늬 없이 단색.
  Palit Dual 의 녹색 띠는 켜진 사진이 아니라 판독이라 실제 RGB 띠 자리·색과 다를 수 있다. StormX 의 팬 지름은 렌더러가 카드 길이로 정한다.
