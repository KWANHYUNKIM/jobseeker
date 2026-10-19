---
name: writing-design-lessons
description: Use when adding or changing a design lesson (디자인 교훈) for the design-lab design agent — after a human verdict reason, a new observation from Instagram/YouTube/articles, or when `agent lessons` shows a lesson marked "글로만".
---

# 디자인 교훈 쓰기 — TDD

교훈은 글이 아니라 **검사 + 손잡이 + 근거** 셋이 한 벌이다. 셋 중 하나가 없으면 배운 게 아니다.

- **검사** `design-lab/evals/checks.py` — 원고가 교훈을 지켰는지 기계가 말한다
- **손잡이** `design_lesson.apply` — 원고를 실제로 바꾼다(layout · kit · copy · photo_tags, `agent/db.py` 의 EFFECTS)
- **근거** `design_lesson_ref` — 어디서 배웠나([공식]/[관찰]/[실무], 출처 링크)

## 철칙

**지금 원고가 그 교훈에 실패하는 걸 먼저 본다.** 실패를 못 보이면 그 교훈은 이미 지켜지고 있거나, 검사가 틀렸다.

## 순서

1. **RED** — `tests/test_cover_checks.py` 에 실패하는 예와 통과하는 예를 하나씩 쓴다 → `pytest` 가 빨갛다.
   검사로 못 보는 교훈(색감·사진 분위기)은 검사 대신 **판정 화면에서 사람이 볼 것**으로 남기고 손잡이만 단다.
2. **GREEN** — `evals/checks.py` 의 `CHECKS` 에 한 줄(검사 함수 · 교훈 문장 · 근거). 테스트가 초록이 될 만큼만.
3. **지금 원고에 건다** — `python -m agent eval` 이 그 검사에서 실패해야 한다(RED 를 진짜 원고로 확인).
4. **교훈을 DB 에** — `python -m agent note <근거 주소> "<규칙>" --area <분야>` (후보로 들어간다, 점수 0).
5. **손잡이를 단다** — `python -m agent knob <번호> '{"layout": {...}, "check": "<검사 id>"}'`.
   손잡이 종류가 모자라면 `poster/corners.py`(`_apply_lessons`)와 `agent/db.py`(`EFFECTS`)에 더하고
   `tests/test_agent_knobs.py` 에 시험을 먼저 쓴다.
6. **다음 시안에서 확인** — `python -m agent knobs` 에 이번에 시험할 교훈으로 뜨는지, 찍은 뒤 `agent eval` 이 초록인지.
7. **REFACTOR** — 사람이 '별로' 와 이유를 남기면 검사가 놓친 빈틈이다. 1번으로 돌아가 그 빈틈을 RED 로 만든다.

## 하지 않는 것

- 점수·판정을 매기지 않는다 — 사람만(8780 `/design`).
- 한 시안에 새 교훈을 둘 이상 걸지 않는다(`pick_knobs` 가 하나만 고른다 — 우회하지 말 것).
- 근거 없는 수치를 교훈에 쓰지 않는다. 검증 안 된 '클릭률 38%' 같은 말은 옮기지 않는다.
- 사람의 판정 이유를 고쳐 쓰지 않는다 — 그대로 교훈 문장이 된다.

## 멈춤 신호

- "이건 당연하니 검사는 건너뛰자" → 당연하면 RED 가 쉽게 나온다. 써라.
- "손잡이 없이 글로 남겨 두자" → 글로만 있는 교훈은 시안에 안 걸리고 점수도 못 받는다.
- "검사를 원고에 맞게 느슨하게" → 검사를 고치는 건 사람이 그 규칙을 바꾸라고 했을 때뿐이다.
