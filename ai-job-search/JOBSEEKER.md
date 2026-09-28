# jobseeker 에서 바꾼 것

이 폴더는 [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search)(MIT)를
`git subtree` 로 들인 것이다. 원본은 덴마크 사이트를 긁는다 — 여기서는 우리 MCP 서버
(`../catch_capture/agent_mcp`, 기본 `http://127.0.0.1:8790/mcp`)의 국내 공고·회사 브리핑·
외주 단가 데이터를 쓰도록 붙였다. 원본 갱신을 합칠 때 충돌을 줄이려고 **원본 파일은 최소로
고쳤고**, 고친 자리마다 `<!-- jobseeker -->` 또는 `# jobseeker:` 표시를 남겼다.

## 쓰는 법

```bash
# 1) 서버를 띄운다(저장소 루트에서)
cd catch_capture && python -m agent_mcp.server          # 8790

# 2) 이 폴더에서 Claude Code 를 연다 — .mcp.json 이 jobseeker 서버를 잡는다
cd ai-job-search && claude
#    처음 한 번 '프로젝트 MCP 서버 jobseeker 를 쓸까?' 를 묻는다 → 허용
#    다른 주소면: JOBSEEKER_MCP_URL=http://<host>:8790/mcp claude

# 3) 원본 흐름 그대로
/setup            # 내 프로필(한 번)
/reality          # 가려는 직군이 이 스펙으로 현실적인지 먼저(국내)
/scrape 백엔드     # jobseeker-kr 포털로 국내 공고를 찾는다
/apply wanted-334745   # 또는 원티드·사람인 등 공고 URL
/interview ...
```

## 바꾼 파일

| 파일 | 무엇을 |
|---|---|
| `.mcp.json` (새) | `jobseeker` MCP 서버 등록. 주소는 `JOBSEEKER_MCP_URL` 로 바꾼다 |
| `.agents/skills/jobseeker-kr/SKILL.md` (새) | 국내 공고 포털. CLI 대신 MCP 도구(`search_jobs`/`get_job`)로 검색하고, 결과를 스크레이퍼의 검색 계약(제목·회사·지역·날짜·URL)에 맞춰 옮기는 표 |
| `.claude/skills/job-scraper/SKILL.md` | `transport: mcp` 포털을 알아듣는 한 단락(Step 1b), bun 이 없어도 MCP 포털은 돈다(Step 1a), allowed-tools 에 두 도구 |
| `.claude/skills/job-scraper/search-queries.md` | 국내 검색어 예시 |
| `.claude/commands/apply.md` | Step 1: 국내 공고면 Market Reality Gate 를 먼저(평가 0번 항목). Step 0: 공고 id·국내 URL 이면 `get_job` 먼저(원문 전문은 그래도 WebFetch). Step 3 검토자: `company_brief`·`company_tech` 로 조사 시작(검증 규칙은 그대로). Step 5d: ATS 키워드에 `job_keywords` — **이력서는 서버로 보내지 않고** 로컬에서 대조 |
| `.claude/commands/reality.md` (새) | `/reality` — 지원서를 쓰기 **전에** 목표 직군이 이 학력·지역·연차로 현실적인지 `market_check` 로 직군끼리 견주고, 판정(현실적/도전/지금은 비현실적)을 첫 줄에 말한 뒤 더 열린 경로 2~3개를 낸다. 원본의 적합도 평가는 '이 공고에 맞나'만 묻고 '이 방향이 맞나'는 묻지 않는다 — 전문학사 신입에게 AI 엔지니어 서류를 정성껏 만들어 준 일이 있어 넣었다 |
| `.claude/skills/job-application-assistant/04-job-evaluation.md` | §6 연봉: 국내는 세 겹(회사 밴드·그 회사 공고에 적힌 값·비슷한 자리 시세)을 섞지 않고 따로 보인다. **Market Reality Gate** — 적힌 학력 관문을 못 넘으면 자격 관문처럼 멈추고, 문이 좁은 직군이면 평가 맨 앞에 깃발을 세우고 판정을 Moderate 이하로 묶는다 |
| `salary_lookup.py` · `tools/build_salary_kr.py` (새) · `tests/test_salary_lookup_kr.py` (새) | **한국식 연봉 비교** — 원본은 덴마크 조합 통계(지수)용이라 한글 회사명을 아예 못 찾았다(정규화가 한글을 지웠다). 한글·(주)/㈜/주식회사를 알아듣게 하고, `build_salary_kr.py` 가 우리 데이터(브리핑 연봉 밴드 + 공고에 적힌 연봉 + 규모×경력 시세)로 `salary_data.json` 을 만든다. `--career` 로 시세 줄을 고른다. 회사가 데이터에 없어도 시세는 준다 |
| `.claude/commands/interview.md` | Step 2: 브리핑의 공고별 면접 질문·공부할 것·차별점을 출발점으로 |
| `.claude/settings.json` · `tools/security_guards.py` | `mcp__jobseeker` 허용 — 도구가 전부 읽기 전용이라 미리 허용해도 되돌릴 수 없는 일이 없다. 원본의 보안 검사 규칙대로 두 곳에 함께 올렸다 |

덴마크 포털 4곳은 원본에서 이미 `enabled: false` 다(고치지 않았다). LinkedIn·freehire 는 켜져 있다.

## 아직 안 한 것

- **국문 이력서 양식.** 원본은 moderncv(영문 LaTeX)다. 국내 지원서는 사이트 양식에 직접 적거나
  국문 이력서·자기소개서를 따로 내는 경우가 많아, `/add-template` 로 국문 양식을 올리거나
  `08-application-forms.md`(지원 폼 문항별 답안) 흐름을 쓰는 쪽을 검토한다.
- 외주·프리 프로젝트는 `/scrape` 대상이 아니다(공고가 아니라 프로젝트). 필요하면 대화에서
  `search_freelance`·`freelance_rates` 를 직접 부른다.

## 원본 갱신 받기

```bash
git subtree pull --prefix=ai-job-search https://github.com/MadsLorentzen/ai-job-search master --squash
cd ai-job-search && python -m pytest tests && python tools/lint_skills.py && python tools/security_guards.py
```
충돌이 나면 위 표의 자리(표시가 붙은 곳)만 다시 맞춘다.
