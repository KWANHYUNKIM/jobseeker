# 에이전트에게 무엇을 못 하게 하는가 — 손을 묶었나 눈을 가렸나 머리를 좁혔나

> 비교 대상: Grab `contain-not-trust`·`wrapper-in-the-box`(+ 기능으로 안 쓴 SOP 프레임워크) ·
> Wix `context-before-fix`·`agent-ready-org` · Snap `code-review-agent`·`agentic-code-search` ·
> monday.com `agent-with-guardrails`
> 각 회사 페이지에서 `확인`으로 정리한 사실만 엮었다. 비교에서 나오는 해석은 **추정**으로 표시했다.
>
> **기계가 낸 결과를 무엇이 통과시키는가**는 비교 문서 `문지기를 무엇으로 세우는가` 에 있다.
> 거기는 **결과물 앞에 세운 문**(컴파일러·린터·샌드박스·타입 정의)이 축이고,
> 여기는 **에이전트가 일하는 동안 애초에 못 하게 막아 둔 것**이 축이다.
> 겹치는 재료가 셋 있는데(Wix 컴파일러 문지기 · Wix AirBot · monday.com 린터) **여기서는
> 그 결과가 아니라 그 앞의 제약만 본다.**
> **자동이 낸 것을 무엇으로 믿는가**는 `기계가 그렇다는데` 에 있다.

에이전트 이야기는 대개 **무엇을 할 수 있게 됐는가**로 전해진다. 그런데 여섯 회사의 여덟
글에서 설계를 실제로 가른 것은 **못 하게 막아 둔 것**이었다. 그리고 막은 자리가 회사마다
다르다 — **닿는 범위**를 줄인 곳, **생각하는 방식**을 좁힌 곳, **마지막 한 걸음**만 안 준
곳, 그리고 **일부러 안 막은 곳**이 있다.

가장 분명한 자리가 Grab 이다. Palana 의 설계 전제를 한 문장으로 못 박는다 —
*"Palana assumes an agent might become confused, compromised, or uncooperative."*
**헷갈리거나 뚫리거나 말을 안 들을 수 있다고 전제하고 짓는다.** 그래서 자격을 아예 안 준다:
*"Separating 'can read a credential' from 'can cause a credentialed request' is powerful."*

## 무엇을 못 하게 했는가

| | 못 하게 한 것 | 대신 준 것 | 회사의 말 |
|---|---|---|---|
| Grab `contain-not-trust` | **자격을 쥐는 것** · 다른 에이전트를 보는 것 · 아무 데나 나가는 것 | 프록시가 대신 요청을 만든다 · 에이전트마다 네임스페이스 · **기본 거부하되 열어 준 길은 두 층으로 본다** | *"Instead of forbidding network access, Palana makes network access observable"* |
| Snap `agentic-code-search` | **부른 사람보다 넓게 보는 것** | 사람의 저장소 권한을 그대로 물려받는다 | *"Agents inherit their human user's repo access"* |
| Snap `code-review-agent` | **저장소를 통째로 내려받는 것** · 승인 | 심볼 색인과 diff 로 볼 파일을 고른다 | *"AI review doesn't yet replace human review, it reshapes it"* |
| Wix `context-before-fix` | **이유 없이 도구를 부르는 것** | 이유를 대면 부를 수 있다 | *"Every tool call requires a stated reason"* |
| Wix AirBot(같은 도메인) | **인바운드 구멍** · 만능 API 계정 · 자유 텍스트 출력 | Socket Mode · IAM 역할로 S3 를 읽는 자체 MCP · 엄격한 타입 JSON | *"Avoiding 'God Mode' API user"* |
| monday.com `agent-with-guardrails` | **한 번에 크게 생각하는 것** · 자기 PR 을 병합하는 것 | Research → Plan → Review 세 단계 · Human Todos 로 스스로 병합을 막는다 | *"when we tried giving AI such complex tasks, it would get lost very quickly and start hallucinating"* |
| Wix `agent-ready-org` | (반대편) **행동 공간이 무한한 에이전트를 안 쓴다** | 코드베이스 안에서 도는 하네스 | *"The action space is unbounded. More capability, more autonomy, more risk"* |
| Grab `wrapper-in-the-box` | (반대편) **아무것도 강제하지 않는다** | 도는 에이전트 둘과 포장이 든 템플릿 | *"A platform would have locked teams into rigid assumptions that would soon become outdated"* |

## ① 손을 묶는다 — 닿을 수 있는 범위를 줄인다

**Grab 이 가장 멀리 갔다.** 여덟 결정 중 여섯이 **무엇을 안 준다**는 이야기다.

- **자격을 안 준다.** 에이전트가 *"may execute tools, run untrusted code, summarize files,
  install packages, or expose a web UI"* 하므로 **파일시스템·로그·환경이 전부 자격 저장소가
  된다.** 그래서 Vault 경로를 `kv/agents/` 와 `kv/proxy-secrets/` 로 갈랐다.
  **권한을 없앤 것이 아니라 위치를 옮긴 것이다**(이 표현은 이 사이트의 것).
- **모델 호출도 예외가 아니다.** *"Agents do not need raw upstream LLM credentials"* —
  래퍼를 지나고, 그 김에 사용량이 에이전트별로 귀속된다.
- **서로를 못 본다.** *"Agents should not see each other's pods, secrets, or filesystem
  state by default"* 이고, 회사는 그 경계 하나가 *"A namespace boundary is simple, but it
  compounds"* 라고 적는다 — RBAC·저장소·네트워크 정책·로깅·쿼터·수명주기가 다 거기 걸린다.
- **신원을 클라이언트가 주는 헤더에서 안 가져온다.** 쿠버네티스 컨텍스트에서 도출하고,
  *"the display-safe or path-safe version of a user ID should not accidentally become the
  authorization subject"* 라고 적는다.

**⭐ 그런데 이 회사가 막는 방식에는 한 가지 특징이 있다 — 전면 금지를 피한다.** 네트워크를
통째로 막지 않는 이유가 *"Agents can be useful only if they can call tools and services"* 다.
**기본은 거부하되 열어 준 길을 두 층(담기 + 애플리케이션 인식 판단)으로 본다.**

**Snap 은 훨씬 짧은 한 줄로 같은 일을 한다** — *"Agents inherit their human user's repo
access."* **에이전트에게 사람보다 넓은 시야를 주지 않는다.** ⚠️ **그리고 이 회사 페이지가
그 대가를 스스로 짚는다 — 그 제약이 도구의 목적과 맞선다.** 조직을 가로지르는 파급 범위를
보라고 만든 검색인데, **부른 사람이 못 보는 저장소의 호출부는 안 나온다.**

**Wix AirBot 은 막는 대상이 사람 쪽 인프라다.** 방화벽에 인바운드 구멍을 뚫지 않으려고
**Socket Mode** 를 쓰고, *"Avoiding 'God Mode' API user"* 하려고 REST API 대신 **IAM 역할로
S3 를 직접 읽는 자체 MCP** 를 만들었다. **에이전트를 막는 대신 에이전트가 쓸 통로를 좁게
새로 판 것이다**(이 정리는 이 사이트의 것).

## ② 머리를 좁힌다 — 생각하는 방식을 제한한다

**여기서 이 문서의 두 번째 갈래가 선다**(이 구분은 이 사이트의 것). 앞의 셋이 **닿는 것**을
줄였다면, 이쪽은 **에이전트가 자유롭게 추론하는 것 자체**를 문제로 본다.

**monday.com 이 그 이유를 가장 솔직하게 적는다** — 순수 AI 도구를 실제로 써 보고
*"it would get lost very quickly and start hallucinating"* 라서 버렸다. 그래서 모델을 더
좋게 만드는 대신 **일을 모델이 감당할 크기로 잘랐다** — Research → Plan → Review 를 결정론적
오케스트레이터가 돌리고, 각 단계를 *"as simple and straightforward as possible for the AI to
carry out"* 만든다. **대가는 그 자르는 장치를 직접 만들고 유지해야 한다는 것**이고, 실제로
**엔지니어 7명**이 붙었다.

**Wix 는 더 가벼운 방식으로 같은 곳을 건드린다** — 도구를 부르려면 **이유를 대야 한다.**
근거가 분명하다: *"forces the agent to actually think about what it's looking for rather
than pattern-matching on surface-level keywords."* **모델을 바꾸는 대신 절차에 마찰을 한 칸
넣은 것이다**(이 표현은 이 사이트의 것).

**⭐ 그리고 이 갈래의 극단이 Grab 에 하나 더 있는데, 이 사이트는 그것을 기능으로 쓰지
않았다.** `Introducing the SOP-driven LLM agent frameworks` 는 SOP 를 **트리**로 표현하고
**깊이 우선 탐색**으로 훑어 LLM 이 다음 수를 지어내지 못하게 한다. 문제 설정도 이 갈래
그대로다 — *"LLMs may make incorrect decisions or invent non-existent steps due to
hallucination."* **수치는 이 문서의 어느 재료보다 강하다** — **99.8% 정확도**, 계정 탈취 조사
**23분에서 3분**과 **87% 자동화**, 사기 조사 **처리시간 45% 감소**와 **월 300시간 이상** 절감.
**⚠️ 그런데 버린 설계 대안이 하나도 없고 인정한 한계도 하나도 없어서** 이 사이트의 기준
(**버린 대안 · 대가 · 수치 중 둘**)을 못 넘겼고, 그래서 회사 페이지의 `open_questions` 에만
남아 있다. **여기서도 재료로만 쓰고 결정으로 세지 않는다.**

**세 재료가 같은 방향을 가리킨다** — **자유롭게 생각하게 두면 지어낸다는 것을 셋 다
전제한다.** 다만 좁히는 정도가 다르다: monday.com 은 **단계로** 잘랐고, Wix 는 **이유를
요구**했을 뿐이고, Grab SOP 는 **경로 자체를 미리 그려 두었다.**

## ③ 마지막 한 걸음만 안 준다

**셋이 여기 있고, 셋 다 병합·승인에서 멈춘다.**

| | 어디까지 하는가 | 마지막에 누가 |
|---|---|---|
| Snap `code-review-agent` | PR 의 **90%** 를 리뷰하고 중앙값 **10분**에 답을 낸다 | **승인은 사람.** ⚠️ 다만 같은 연작의 Casper 가 **PR 을 여는 앞 칸을 이미 가져갔다** |
| monday.com | 변환·검증·플래그까지 | **최소 두 명**이 본다. 자동 병합은 버린 대안이다 |
| Wix AirBot | PR 후보 **180개** 를 만든다 | **28개만 직접 병합 — 완전 자동화율 15%.** 나머지 85%는 사람 손을 거친다 |

**⭐ monday.com 의 방식이 이 셋 중 유일하게 결이 다르다** — **에이전트가 스스로 자기를
막는다.** 판단이 필요하거나 위험을 발견하면 **Human Todos** 를 달아
*"alert the linter to block the PR from merging"* 한다. **멈추는 권한을 자동화 쪽에 준
것이다**(이 표현은 이 사이트의 것). ⚠️ **대가도 거기서 나온다 — 무엇을 '판단이 필요한 것'
으로 볼지 결국 AI 가 정하고, 그 기준이 틀리면 조용히 지나간다.**

**Snap 은 지어낸 지적을 막는 자리를 하나 더 둔다** — 검증기가
*"checks that every symbol cited in a finding is actually present in the provided context"*
한다. **모델을 고치는 대신 출력이 입력에 근거하는지만 본다.** ⚠️ **대신 맞는 지적인데 이름을
살짝 다르게 쓴 경우도 함께 걸릴 수 있고, 그 이야기는 글에 없다.**

## ④ 반대편 — 안 막고 열어 주는 쪽

**둘이 정반대로 갔고, 둘 다 이유가 분명하다.**

**Wix `agent-ready-org` 는 막을 곳을 도구 선택에서 미리 정했다.** 에이전트를 세 층으로 갈라
**둘을 이유와 함께 버렸다** — **클라우드 에이전트**는 *"Stateless per task… no codebase
awareness, no iteration loop, no project context"* 라서, **컴퓨터를 통째로 주는 에이전트**는
*"The action space is unbounded. More capability, more autonomy, more risk"* 라서. 가운데
**하네스**를 골랐다. **행동 공간을 런타임에 막는 대신 처음부터 좁은 것을 고른 셈이다**
(이 정리는 이 사이트의 것).

**그리고 이 글의 핵심은 에이전트가 아니라 저장소를 고친 것이다** — **Agent Ready
Repositories** 는 *"a standard for structuring a codebase so that an AI agent can contribute
to it reliably"* 이고 근거가 *"An agent dropped into an unprepared codebase will produce
unreliable results"* 다. **문제를 모델 쪽이 아니라 입력 쪽에서 풀었다.**

**Grab `wrapper-in-the-box` 는 아예 강제를 포기했다.** 무거운 중앙 플랫폼을 버린 이유가
*"A platform would have locked teams into rigid assumptions that would soon become
outdated"* 다. **⚠️ 그 대가가 이 문서의 축과 정면으로 만난다** — 능력을 **런타임에 발견**하게
했으므로 *"Adding a new capability can be as simple as registering an MCP server"* 인데,
**등록된 MCP 서버가 50개가 넘는데 어떤 에이전트가 무엇에 닿는지의 통제 이야기가 이 글에는
없다.**

## ⭐⭐ 같은 회사가 두 방향으로 간다

**이게 이 문서에서 가장 센 관찰이다**(이 정리는 이 사이트의 것). **세 회사가 에이전트를 두
방향에서 다루면서, 그 두 글이 서로를 한 번도 안 부른다.**

| | 조이는 쪽 | 푸는 쪽 |
|---|---|---|
| **Grab** | **Palana** — 기본 거부, 자격을 안 줌, 네임스페이스 격리 | **LLM-Kit** — 강제하지 않는 프레임워크, MCP 를 런타임에 발견 |
| **Wix** | **AirBot** — 인바운드 구멍 없음, 만능 계정 없음, 타입 강제 | **Agent Ready Repos** — 저장소를 에이전트가 읽기 좋게 고쳐 준다 |
| **Snap** | **CodePal** — 저장소를 안 내려받고 승인도 안 준다 | **코드 검색** — MCP 서버 하나로 *"any MCP-capable agent can call it with one config line"* |

**⭐ 방향이 갈리는 자리에 규칙이 하나 보인다**(**추정**) — **에이전트가 무엇을 만들지에는
느슨하고, 에이전트가 무엇에 닿을지에는 빡빡하다.** Grab 은 만드는 프레임워크를 강제하지
않으면서 닿는 것은 기본 거부에서 시작하고, Wix 는 저장소를 열어 주면서 만능 계정은 막고,
Snap 은 검색을 한 줄 설정으로 열어 주면서 그 시야를 부른 사람의 권한으로 자른다.

**⚠️ 그런데 두 쪽이 만나는 자리를 적은 회사가 없다.** Grab 의 LLM-Kit 이 MCP 서버 50개를
런타임에 붙이는데 Palana 의 기본 거부가 그 위에서 어떻게 도는지, Wix 의 준비된 저장소에
AirBot 의 최소 권한이 어떻게 걸리는지 — **두 글을 따로 읽으면 알 수 없다.**

## 막은 값을 잰 곳이 있는가 — 거의 없다

**여덟 중 막은 것 때문에 무엇을 잃었는지 숫자로 적은 곳이 하나도 없다.**

| | 막은 대가로 적힌 것 | 숫자가 있는가 |
|---|---|---|
| Grab Palana | 프록시 한 겹이 지연을 늘린다 · 길을 하나씩 열어 줘야 한다 | ❌ **지연도 절차 시간도 없다.** 규모 수치도 *"hundreds of agents"* 한 줄뿐 |
| Snap 코드 검색 | 부른 사람이 못 보는 곳은 안 나온다 | ❌ 그런 질의가 몇 %인지 없다 |
| Snap CodePal | 저장소를 안 내려받아 두 단계 파일 선별기가 필요해졌다 | ⚠️ **클론을 피한 이유가 속도인지 보안인지 규모인지조차 글에 없다** |
| Wix 이유 요구 | 이유를 대느라 왕복이 는다 | ❌ 없다 |
| monday.com | 단계마다 왕복이 붙는다 | ❌ **한 파일에 모델 호출이 몇 번인지 없다** |
| Wix 하네스 | 하네스가 코드베이스에 묶인다 | ❌ 없다 |

**반대로 막지 않은 쪽의 이득은 숫자로 적힌다** — Grab LLM-Kit 은 준비가 **2주 이상에서 약
1시간**, Wix AirBot 은 월 **675 엔지니어 시간** 절감, monday.com 은 **8 person-years 추정이
6 person-months**. **푼 쪽의 이득은 세고 조인 쪽의 값은 안 센다**(이 대비는 이 사이트의 것).

## 이 사이트에 아직 없는 것

- **막은 것이 실제로 사고를 막은 기록이 없다.** 여덟 다 **이렇게 막았다**까지이고,
  **막아 둔 덕에 무엇이 안 일어났는지**는 어디에도 없다. Grab 은 *"confused, compromised,
  or uncooperative"* 를 전제로 짓는다고 적지만 **그 셋 중 무엇이 실제로 일어났는지는 없다.**
- **막은 것을 나중에 푼 기록이 없다.** 반대로 monday.com 만 **사고 뒤에 늘렸다**(셀렉터
  이관이 테스트를 통과했는데 메모이제이션에 숨은 부작용이 있었고, 그 뒤 22포인트 검증과
  비교 테스트와 동결 시 병합 차단이 붙었다). **완화한 사례는 이 사이트에 하나도 없다.**
- **에이전트가 막힌 벽을 우회하려 한 이야기가 없다.** 가장 가까운 것이 Grab 의
  *"teams will work around it"* 인데, **그것은 사람이 통제를 우회한다는 이야기지 에이전트가
  아니다.** ⚠️ 그래서 **통제를 쉽게 만드는 것을 안전 설계의 일부로 적은 회사도 Grab 하나뿐**
  이다.
- **무엇을 못 하게 할지 정하는 기준이 어디에도 없다.** 여덟 다 결과만 적는다 — Grab 이
  왜 자격은 완전히 막고 네트워크는 안 막았는지, Snap 이 왜 저장소 클론은 막고 MCP 노출은
  열었는지, **그 선을 어디에 긋는지를 설명한 글이 없다.**
- **네 번째 갈래(추론 경로를 미리 그린다)의 재료가 아직 얇다.** monday.com 과 Wix 와 Grab
  SOP 셋인데, **그중 하나(Grab SOP)는 버린 대안도 한계도 0줄이라 이 사이트가 기능으로 쓰지
  않은 글**이다. **같은 방식을 다른 회사가 쓴 기록을 더 찾아야 축이 단단해진다.**
