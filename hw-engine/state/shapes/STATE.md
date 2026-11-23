# 3D 모양 레인 — 상태

- 시작: 2026-11-23. 형식 `jd-viewer/src/features/hardware/utils/shapes.ts`, 절차 `hw-engine/3D.md` 6절.
- 남은 일: `python -X utf8 hw-engine/validate.py --gaps` 의 12번(시작 때 249/249 제품, 2026-11-23 2회차 뒤 240/249, 3회차 뒤 236/249, 4회차 뒤 231/249, 5회차 뒤 226/249).
- MSI 는 msi.com 이 403 이라 데이터시트 PDF(storage-asset.msi.com)를 Read 로 연다 — 글과 정면·뒷면 사진이 같이 보인다(4회차에 풀림).
- 사진 보는 법: web-fetch 로 이미지 주소를 받으면 세션 임시 폴더(tool-results)에 남고 그 파일을 Read 로 연다(저장소에 두지 않는다). ASUS 갤러리(`/gallery/`)·Gainward 갤러리(`&tab=gy`)·GALAX 페이지는 사진 주소가 글로 보인다. Palit 갤러리는 스크립트로 불러와 대표 사진 한 장만 보인다.
- 다음 회차 맨 앞: `--gaps` 12번 순서대로(COLORFUL 5060 Ti Gaming DUO V2, ASUS DUAL 5060 Ti 8G, MSI VENTUS 2X OC 5060 …).
- 다시 볼 것(confidence low — 사진을 못 봄): COLORFUL 3개(gpu-rtx-5060-ti-16 ×2 · gpu-rtx-5050). 공식 이미지 서버 403.
- 렌더러: L1(규격·치수 절차 모델) 됨, L2(제품 모양 사양) 연결 됨, L3(Blender GLB)·L4(재질) 계획.
