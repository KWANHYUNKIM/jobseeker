"""디자인 에이전트 — 영감을 모으고(①) 교훈으로 뽑고(②) 시안에 써 본다(③). 판정(④)과 점수(⑤)는 사람이 매긴다.

    ① 모으기   유튜브(공식 Data API)·인스타(로그인한 웹에서 사람처럼 본 것)·디자인 칼럼 → design_ref
    ② 배우기   모은 것에서 교훈 → design_lesson (근거는 design_lesson_ref)
    ③ 써 보기  점수 높은 교훈부터 코너에 적용해 찍고 → design_trial (어떤 교훈을 썼나 design_trial_lesson)
    ④ 판정     8780 /design 에서 장마다 좋다/별로 + 이유, 묶음마다 올려도 됨/안 됨 → design_verdict · design_trial.release
    ⑤ 점수     design_lesson_score — 판정이 쌓일수록 교훈 순위가 바뀐다. 코드는 그대로다

    python -m agent seed                 # 출처·처음 교훈(지금까지의 사용자 판정 포함)
    python -m agent youtube              # YOUTUBE_API_KEY 가 있을 때 — 출처 채널의 최근 영상
    python -m agent lessons              # 교훈과 점수
    python -m agent render               # 코너를 하나씩 찍고(메모리 보며) 시안으로 기록 — agent/render.py
    python -m agent trial deadline       # 찍은 코너를 시안으로 기록(적용한 교훈과 함께)
    python -m agent status

표는 db/migrations/016_design_agent.sql. 루프는 catch_capture/automation/loops.py 의 design-agent.
"""
