# 형식 변경 요청

루프 레인(`hw-engine`·`hw-models`)은 형식 파일을 고치지 않는다 — `schema.json` · `validate.py` · `PROMPT.md` ·
뷰어 코드(`jd-viewer/src/`). 바꿔야 할 게 보이면 여기 한 줄 적고 다음 일감으로 넘어간다.
사람이 지시한 세션이 모아서 처리하고, 처리한 줄은 지운다.

형식: `- YYYY-MM-DD [레인] 무엇을 왜 — 어느 파일`

- 2026-09-30 (hw-datacenter): datacenter.json 에 행마다 `rechecked`(YYYY-MM-DD) 필드를 두고 --gaps 10번이 as_of 대신 max(as_of, rechecked) 로 나이를 재게 해 달라. 슈퍼컴퓨터(El Capitan·Frontier·Aurora 등)와 ByteDance·Tencent 2024 구매 추정처럼 '다시 찾아봤지만 새 공개 숫자가 없는' 행이 영영 일감으로 남는다.
- 2026-09-30 (hw-datacenter): notes.json 에도 `rechecked` 필드를 두고 --gaps 11번이 max(as_of, rechecked) 로 나이를 재게 해 달라. llama.cpp 점수판처럼 계속 갱신되는 글은 '측정 날짜'와 '다시 확인한 날짜'가 달라 as_of 하나로는 둘을 가르지 못한다(이번엔 원문과 같은 값을 확인한 3건만 as_of 를 옮기고 본문에 적었다).
- 2026-11-14 (hw-engine): validate.py 가 시작부터 FileNotFoundError 로 죽는다 — `VIEWER_LIB` 가 옛 경로 `jd-viewer/src/lib/hardware.ts` 를 본다. 뷰어 폴더 규칙 정리로 `jd-viewer/src/features/hardware/utils/hardware.ts` 로 옮겨졌다(SPEC_COLUMNS 가 거기 있다). 이번 회차는 경로만 바꿔 끼운 임시 래퍼로 돌렸다 — `hw-engine/validate.py` 19행.
- 2026-11-14 (hw-engine): 다나와 새 마크업(RSC) 파서가 오픈마켓·해외구매 매물까지 받는다 — pcode 가 숫자가 아닌 `TH201_…`·`EE128_…`·`EE715_…`·`EE309_…`·`ED907_…`·`TSA34_…` 꼴이고 이름에 '해외구매' 가 없어 ALWAYS_NOT 을 통과한다(옛 HTML 은 숫자 pcode 만 줬다). 11-11 이후 섞인 매물 13개가 대부분 이것이다(5700X3D 는 30건 전부, 990 PRO 1TB 는 24건 중 22건). 숫자 pcode(가격비교 상품)만 쓰고 없을 때만 오픈마켓으로 물러서거나, RSC 상품에 오픈마켓 표지가 있으면 그걸로 거르고, ALWAYS_NOT 에 `[해외]` 를 더해 달라. 부품 쪽 `not` 으로는 이름이 멀쩡한 해외 매물(7900 XTX · 5300G · 9900X3D)을 못 가른다 — `catch_capture/crawlers/crawl_hardware.py` `_parse_rsc`·`ALWAYS_NOT`.
