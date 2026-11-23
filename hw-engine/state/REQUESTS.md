# 형식 변경 요청

루프 레인(`hw-engine`·`hw-models`)은 형식 파일을 고치지 않는다 — `schema.json` · `validate.py` · `PROMPT.md` ·
뷰어 코드(`jd-viewer/src/`). 바꿔야 할 게 보이면 여기 한 줄 적고 다음 일감으로 넘어간다.
사람이 지시한 세션이 모아서 처리하고, 처리한 줄은 지운다.

형식: `- YYYY-MM-DD [레인] 무엇을 왜 — 어느 파일`

- 2026-09-30 (hw-datacenter): datacenter.json 에 행마다 `rechecked`(YYYY-MM-DD) 필드를 두고 --gaps 10번이 as_of 대신 max(as_of, rechecked) 로 나이를 재게 해 달라. 슈퍼컴퓨터(El Capitan·Frontier·Aurora 등)와 ByteDance·Tencent 2024 구매 추정처럼 '다시 찾아봤지만 새 공개 숫자가 없는' 행이 영영 일감으로 남는다.
- 2026-09-30 (hw-datacenter): notes.json 에도 `rechecked` 필드를 두고 --gaps 11번이 max(as_of, rechecked) 로 나이를 재게 해 달라. llama.cpp 점수판처럼 계속 갱신되는 글은 '측정 날짜'와 '다시 확인한 날짜'가 달라 as_of 하나로는 둘을 가르지 못한다(이번엔 원문과 같은 값을 확인한 3건만 as_of 를 옮기고 본문에 적었다).
- 2026-11-14 (hw-engine): validate.py 가 시작부터 FileNotFoundError 로 죽는다 — `VIEWER_LIB` 가 옛 경로 `jd-viewer/src/lib/hardware.ts` 를 본다. 뷰어 폴더 규칙 정리로 `jd-viewer/src/features/hardware/utils/hardware.ts` 로 옮겨졌다(SPEC_COLUMNS 가 거기 있다). 이번 회차는 경로만 바꿔 끼운 임시 래퍼로 돌렸다 — `hw-engine/validate.py` 19행.
- 2026-11-14 (hw-engine): 다나와 새 마크업(RSC) 파서가 오픈마켓·해외구매 매물까지 받는다 — pcode 가 숫자가 아닌 `TH201_…`·`EE128_…`·`EE715_…`·`EE309_…`·`ED907_…`·`TSA34_…` 꼴이고 이름에 '해외구매' 가 없어 ALWAYS_NOT 을 통과한다(옛 HTML 은 숫자 pcode 만 줬다). 11-11 이후 섞인 매물 13개가 대부분 이것이다(5700X3D 는 30건 전부, 990 PRO 1TB 는 24건 중 22건). 숫자 pcode(가격비교 상품)만 쓰고 없을 때만 오픈마켓으로 물러서거나, RSC 상품에 오픈마켓 표지가 있으면 그걸로 거르고, ALWAYS_NOT 에 `[해외]` 를 더해 달라. 부품 쪽 `not` 으로는 이름이 멀쩡한 해외 매물(7900 XTX · 5300G · 9900X3D)을 못 가른다 — `catch_capture/crawlers/crawl_hardware.py` `_parse_rsc`·`ALWAYS_NOT`.
- 2026-11-23 (hw-3d) [3D 렌더러] --gaps 12번이 shapes 에 항목만 있으면 '됨'으로 친다 — 사진을 못 봐 색·문구만 적은 confidence low 항목(COLORFUL 3개, 공식 이미지 서버 403)이 다시 일감으로 올라오지 않는다. low 는 끝에 '다시 볼 것'으로 따로 세어 달라 — `hw-engine/validate.py` shapes_gaps.
- 2026-11-23 (hw-3d) [3D 렌더러] 팬 지름을 모르면 GPU shapes 에 fans 를 못 적어 팬 개수(사진으로 센 3개)도 전할 길이 없다 — `fan_count`(지름 없이 개수만) 칸이 있으면 렌더러가 길이로 지름을 나누게 해 달라(Palit 5090 GameRock) — `shapes.ts` GpuShape · `validate.py` SHAPE_KEYS · `three/world.ts`.
- 2026-11-23 (hw-3d) [3D 렌더러] Palit GameRock 의 팬을 감싼 곡선 ARGB 판(Chameleon Panel, 보는 각도로 색이 바뀜)·GALAX 1-Click OC 의 앞·옆 두 면 발광 띠는 accent 색 한 칸으로만 그려진다 — 쉬라우드 발광 패널 모양이 없다 — `three/parts.ts` buildGpu.
- 2026-11-23 (hw-3d) [hw-models] Palit RTX 5090 GameRock(palit-rtx5090-gamerock) `fans` 가 null — 공식 사진에 팬 3개, 지름은 공식 자료에 없다 — `jd-viewer/public/hardware/models/gpu-rtx-5090.json`.
- 2026-11-23 (사람 세션) 반영: 위 [3D 렌더러] 3줄 — `--gaps` 12번 끝에 '다시 볼 것(confidence low)' 수·목록 · GpuShape `fan_count`(지름 없이 개수만, 렌더러가 길이로 나눈다) · GpuShape `light: side|front|both`(옆 모서리 발광 띠 / 팬을 감싼 발광 고리, 색은 accent). 곡선 판의 정확한 모양·보는 각도로 색이 바뀌는 효과는 아직 없다.
- 2026-11-23 (hw-3d) [3D 렌더러] 흰 단색 팬 LED 를 적을 칸이 없다 — fan_light 가 none/rgb/argb 뿐이고 rgb 를 주면 무지개 고리로 그려진다. GALAX 5060 Ti 1-Click OC(16GB·V2)는 켜진 공식 사진에서 팬이 흰색으로만 빛난다. `fan_light: 'white'`(또는 단색 + 색 칸)를 두고 고리를 그 색으로 칠해 달라 — `shapes.ts` ShapeBase · `validate.py` · `three/parts.ts` rgbRing.
- 2026-11-23 (hw-3d) [3D 렌더러] ASUS ROG Astral RTX 5090(쿼드 팬)은 앞면 팬 3개 + 백플레이트 끝 쪽 뒷면 팬 1개(플로스루 자리)인데 GpuShape 에 뒷면 팬 칸이 없다 — `rear_fans`(개수) 같은 칸과 백플레이트 쪽 팬 그리기. 끝 팬만 크고 무지개 고리가 그 팬에만 있는 것도 지금은 fan_light 하나로 모든 팬에 칠해진다 — `shapes.ts` GpuShape · `validate.py` SHAPE_KEYS · `three/parts.ts` buildGpu.
- 2026-11-23 (hw-3d) [3D 렌더러] BTF 그래픽카드(ASUS ROG Astral RTX 5090 BTF OC)는 보조전원을 윗면 16핀이 아니라 PCIe 손가락 옆 GC-HPWR 골드핑거(정면 사진에서 브래킷부터 약 56%)로 받는다 — GpuShape `power.type` 에 `'gc-hpwr'`(아랫면 골드핑거, 선 없음)를 두고 그때는 윗면 단자·전원선을 그리지 않게 해 달라. 지금은 power 를 비워 렌더러가 models 의 16핀을 윗면에 그린다 — `shapes.ts` GpuShape · `validate.py` · `three/parts.ts` buildGpu · 선 정리.
- 2026-11-23 (hw-3d) [3D 렌더러] 빛나는 글자(로고)를 적을 칸이 없다 — XFX Swift RX 9070 XT White 는 조명이 윗 모서리의 흰 XFX 로고 하나뿐인데(공식 'White XFX Logo') marks 는 색만 있어 빛나지 않는다. marks 에 `glow: true` 를 두고 그 글자를 발광 재질로 써 달라 — `shapes.ts` ShapeBase.marks · `validate.py` · `three/parts.ts` 글자.
- 2026-11-23 (hw-3d) [hw-models] ASUS T1 Edition RTX 5060 Ti OC 8GB(asus-t1-rtx5060ti-o8g) `fans` 가 2 인데 공식 한국 페이지 문구('3개의 Axial-tech 팬')와 정면 사진 모두 팬 3개다 — `jd-viewer/public/hardware/models/gpu-rtx-5060-ti-8.json`.
- 2026-11-23 (hw-3d) [hw-models] Palit RTX 5090 GameRock OC(palit-rtx5090-gamerock-oc) `fans` 가 null — 공식 대표 사진에 팬 3개(비OC GameRock 줄과 같다) — `jd-viewer/public/hardware/models/gpu-rtx-5090.json`.
- 2026-11-23 (hw-3d) [3D 렌더러] 백플레이트의 발광 로고를 그릴 수 없다 — ASUS TUF RTX 5060 Ti 는 백플레이트 가운데 TUF 로고·줄무늬가 노랗게 빛난다(공식 사진). 위 marks `glow` 요청에 where=backplate 도 포함해 달라 — `shapes.ts` ShapeBase.marks · `three/parts.ts` 글자.
