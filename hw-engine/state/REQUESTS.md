# 형식 변경 요청

루프 레인(`hw-engine`·`hw-models`)은 형식 파일을 고치지 않는다 — `schema.json` · `validate.py` · `PROMPT.md` ·
뷰어 코드(`jd-viewer/src/`). 바꿔야 할 게 보이면 여기 한 줄 적고 다음 일감으로 넘어간다.
사람이 지시한 세션이 모아서 처리하고, 처리한 줄은 지운다.

형식: `- YYYY-MM-DD [레인] 무엇을 왜 — 어느 파일`

- 2026-09-30 (hw-datacenter): datacenter.json 에 행마다 `rechecked`(YYYY-MM-DD) 필드를 두고 --gaps 10번이 as_of 대신 max(as_of, rechecked) 로 나이를 재게 해 달라. 슈퍼컴퓨터(El Capitan·Frontier·Aurora 등)와 ByteDance·Tencent 2024 구매 추정처럼 '다시 찾아봤지만 새 공개 숫자가 없는' 행이 영영 일감으로 남는다.
