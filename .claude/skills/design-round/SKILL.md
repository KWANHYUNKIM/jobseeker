---
name: design-round
description: Use when running one round of the design-lab design agent (디자인 에이전트 한 회차) — the `design-agent` loop in catch_capture/automation/loops.py, or when asked to make new card-news drafts for human judging on 8780 /design.
disable-model-invocation: true
---

# 디자인 에이전트 한 회차

①모으기 ②배우기 ③써 보기만 한다. ④판정 ⑤점수는 사람이 8780 `/design` 에서 매긴다.
모든 명령은 `design-lab/` 에서.

## 순서

1. **읽기** — `python -m agent status` · `python -m agent lessons`. 새 판정 이유가 있으면 그게 오늘 첫 일감이다.
2. **판정 이유 → 교훈** — 이유 중 아직 교훈이 아닌 것은 `writing-design-lessons` 스킬(필수) 순서로 더한다.
   사람의 말을 고쳐 쓰지 않는다.
3. **공부 하나** — `.claude/skills/card-cover/references/evidence.md` 의 '더 볼 것' 하나를 조사해 근거와 함께
   덧붙인다([공식]/[관찰]/[실무] 구분, 원문은 옮기지 않고 요약, 검증 안 된 수치 금지). 표지 규칙이 나오면 2번처럼 교훈으로.
   유튜브는 `YOUTUBE_API_KEY` 가 있을 때 `python -m agent youtube`(공식 API 만 — 자막·영상 받기 금지).
   인스타는 로그인한 웹 탭에서 보기만 한다(팔로우·댓글·게시 금지).
4. **원고** — `python -m poster.corners`. 표지는 `card-cover` 스킬(필수)을 따른다.
5. **검사** — `python -m agent eval`. 실패가 있으면 원고를 고친다. 손잡이가 시험 중인 교훈 때문에 실패하면 그대로 둔다
   (그것도 판정 재료다) — 보고에 적는다.
6. **찍기** — `python -m agent render`. 코너를 하나씩, 메모리를 보며 기다린다(오래 걸려도 된다). cardpress 를 직접
   여러 개 동시에 돌리지 않는다. 임베딩·크롤과 겹치지 않는다.
7. **눈으로 확인** — 찍은 표지를 직접 열어 1초 한눈 시험. 이상하면 보고에 적되 점수는 매기지 않는다.
8. **커밋** — 코드를 고쳤으면 `python -m pytest tests` 통과 후 `feat(design-lab)`. 푸시하지 않는다.
   git add 는 `design-lab/agent/` · `poster/corners.py` · `poster/direction.py` · `evals/` · `tests/test_cover_checks.py` ·
   `tests/test_agent_knobs.py` · `research/` · `.claude/skills/card-cover/` 만.
9. **보고** — 새 시안 번호, 이번에 시험한 교훈, 검사 결과, 그리고 "8780 /design 에서 판정해 주세요" 두세 줄.
