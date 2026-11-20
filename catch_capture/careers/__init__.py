"""커리어 경로 — 개발자 합격·이직·전환 후기를 모아 '어떤 길로 어디에 갔는가'를 센다.

혼자 보는 자료다 — 뷰어 기술도서 › 취업(`/wiki/careers`, noindex)이 정본 DB(019)를 읽는다. 사람이 아니라 경로를 모은다 — 글쓴이 이름·아이디·사진·다른
계정은 저장하지 않고, 글 안에서 스스로 밝힌 이력만 표 한 줄로 바꾼다. 원문은 `var/careers/raw/`
와 DB `career_post` 에 두고(추출을 다시 돌리기 위해), 공개 API 는 구조화된 값만 내준다 — 본문은 `CAREERS_KEY` 열쇠가 있어야 열린다.

  collect  — 출처별 수집(velog 검색 + 직접 넣은 글 inbox) → raw/
  extract  — raw 를 claude 로 구조화 → paths.jsonl
  report   — 회사·직무·배경·전환별 집계 → report.json + report.html
  DB       — store.ingest.careers 가 원문·경험담·명단을 career_post/story/roster 에(cycle 끝에 부른다)

출처 원칙은 크롤러와 같다: robots·약관이 허용한 곳만 자동으로 받는다. brunch·medium 은 AI 수집을
막아 두었고, 인스타그램·페이스북은 자동 수집이 약관 위반이라 사람이 inbox 에 넣은 글만 받는다.
"""
