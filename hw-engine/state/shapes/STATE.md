# 3D 모양 레인 — 상태

- 시작: 2026-11-23. 형식 `jd-viewer/src/features/hardware/utils/shapes.ts`, 절차 `hw-engine/3D.md` 6절.
- 남은 일: `python -X utf8 hw-engine/validate.py --gaps` 의 12번(시작 때 249/249 제품, 2026-11-23 2회차 뒤 240/249, 3회차 뒤 236/249, 4회차 뒤 231/249, 5회차 뒤 226/249, 6회차 뒤 221/249, 7회차 뒤 216/249, 8회차 뒤 212/249, 9회차 뒤 208/249, 10회차 뒤 203/249, 11회차 뒤 199/249, 12회차 뒤 194/249, 13회차 뒤 189/249).
- MSI 는 msi.com 이 403 이라 데이터시트 PDF(storage-asset.msi.com)를 Read 로 연다 — 글과 정면·뒷면 사진이 같이 보인다(4회차에 풀림).
- 사진 보는 법: web-fetch 로 이미지 주소를 받으면 세션 임시 폴더(tool-results)에 남고 그 파일을 Read 로 연다(저장소에 두지 않는다). ASUS 갤러리(`/gallery/`)·Gainward 갤러리(`&tab=gy`)·GALAX 페이지는 사진 주소가 글로 보인다. Palit 갤러리는 스크립트로 불러와 대표 사진 한 장만 보인다. ASUS 그래픽카드 갤러리는 대부분 404 — 모델 `image.url`(대표 정면)만 볼 수 있다. 대신 ASUS 제품 소개 페이지 본문의 `dlcdnwebimgs.asus.com/files/media/<id>/v1/img/...` 사진(kv·cooling·software·intro/pd-back 등)은 web-fetch 가 주소를 글로 보여 줘 비스듬한 사진·백플레이트까지 볼 수 있다(10회차).
- 다음 회차 맨 앞: `--gaps` 12번 순서대로 — 맨 앞 COLORFUL 6개(Gaming DUO 셋·iGame Ultra W 셋)는 공식 이미지 403 이라 넘긴다(8회차에도 403). COLORFUL Battle AX 5070 Ti SFF·iGame 5060 Ti Ultra DUO OC 8G(403)·ZOTAC 5050 Twin Edge OC White(468)도 넘긴다. COLORFUL iGame 5080 Ultra W OC·Ultra OC V2 도 같은 이유로 넘긴다. 그 뒤는 인기순위 없는(999) 제품들 — COLORFUL Battle AX 5050·5060 Ti(403 이면 넘긴다), INNO3D 5060 Ti 16G 까지 됨, 다음은 PNY 5060 Ti EPIC-X RGB OC Triple Fan · GALAX 5060 Ti WHITE OC 8GB · MANLI 5060 Polar Fox OC · PNY 5060 OC Dual Fan … — `--gaps` 12번 순서(전체 목록은 validate 의 shapes_gaps 와 같은 순서로 세면 보인다 — 출력은 앞 8개만).
- 이엠텍(emtekinc.co.kr) 상세 이미지는 세로 2만 px 짜리 한 장이라 Read 가 줄여 보인다 — PIL 로 세션 임시 폴더에 잘라 본다(11회차).
- PDF 보는 법(윈도우): pdftoppm 이 없어 Read 가 PDF 를 못 연다 — `python -I -X utf8` 로 PyMuPDF(`import pymupdf`)를 써 글을 뽑고 쪽 그림을 세션 임시 폴더에 그려 Read 로 본다.
- 다시 볼 것(confidence low — 사진을 못 봄): COLORFUL 3개(gpu-rtx-5060-ti-16 ×2 · gpu-rtx-5050). 공식 이미지 서버 403.
- ZOTAC: zotac.com 제품 페이지·브로슈어 PDF 둘 다 HTTP 468(봇 차단) — 우회하지 않는다. ZOTAC 제품은 넘긴다.
- 렌더러: L1(규격·치수 절차 모델) 됨, L2(제품 모양 사양) 연결 됨, L3(Blender GLB)·L4(재질) 계획.
