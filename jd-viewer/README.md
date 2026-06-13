# jd-viewer

채용 크롤 파이프라인(`catch_capture/`)이 만든 데이터를 시각화하는 React/Vite 뷰어.
`public/` 의 JSON 을 그대로 소비하며, 상단 탭으로 6개 화면을 전환한다. 탭·회사 상세는
URL 해시와 동기화되어 새로고침·공유·뒤로가기가 유지된다(예: `#radar`, `#radar/netflix`).

## 실행

```bash
npm install
npm run dev        # 개발 서버(5173)
npm run build      # tsc -b + vite build (타입체크 포함, 배포 산출물 dist/)
npm run preview    # 빌드 결과 미리보기
```

## 탭

| 탭 | 컴포넌트 | 데이터 |
|----|----------|--------|
| 잡 리스트 | `JobList`/`JobDetail` | `all_jobs_enriched.json` |
| 기업 기술스택 | `CompanyView` | `company_stacks.json` (채용공고 집계) |
| 기술스택 확장 | `ExpansionView` | 〃 |
| 커리어 마인드맵 | `CareerMap`/`MindmapView` | `mindmap_tree.json` |
| 기술 블로그 | `BlogView`/`BlogDetail` | `tech_blogs.json` |
| **기술 스택 레이더** | `RadarView` | `company_tech_radar.json` |

## 기술 스택 레이더

글로벌 IT 대기업 100개사(미국·한국·인도)가 **어떤 도메인에서 어떤 기술 스택·아키텍처·언어를
왜 쓰는지** 를 큐레이션 + LLM 리서치로 정리해 보여준다.

- **회사별 보기**: 국가·도메인·언어·콘텐츠(토론/공개코드/AI갱신) 필터 + 검색(이름·기술뿐
  아니라 '왜' 설명·심화 해설 본문까지 훑음) + 정렬. 카드 하단에 보유 자료(구조도·심화·토론·코드) 표시.
- **도메인별 보기**: 산업 도메인이 어떤 공통 스택으로 이루어지는지 집계. 기술 태그 클릭 시
  그 기술로 회사 검색.
- **회사 상세**(`RadarDetail`): 주요 언어·아키텍처(클릭 시 교차 검색), **Mermaid 아키텍처
  다이어그램**(노드별 기술스택, 전체화면 줌), '어떻게 작동하는가' 심화 해설(마크다운, 토픽별
  누적), **멀티 에이전트 아키텍처 토론**(설계자↔검토자+정리자: 후보 여러 개 + 토론 전사 +
  합의 결론), 검증된 공개 GitHub repo(star). ←/→ 로 회사 이동, `🔗 링크` 로 딥링크 공유.

### 데이터 생성/갱신 — `bin/build_company_tech_radar.py`

`company_tech_radar.json` 하나가 원본이자 산출물이다. 크롤에서 파생되는 다른 데이터와 달리
사람이 큐레이션한 시드를 in-place 로 키운다(추가 API 키 없이 로컬 `claude` CLI 로 리서치).

```bash
# 시드 JSON 배열 병합으로 최초 생성
python bin/build_company_tech_radar.py --init seed_us.json seed_kr.json seed_in.json

# {key, diagram, github, deep_dive, ...} 부분필드를 key 매칭 병합(누적)
python bin/build_company_tech_radar.py --patch patch_*.json

# 가장 오래된 N개사를 claude CLI 로 리서치·갱신(스택·다이어그램·심화 누적·github 검증)
python bin/build_company_tech_radar.py --refine 5

# N개사를 멀티 에이전트 토론(설계자↔검토자+정리자)으로 아키텍처 도출
python bin/build_company_tech_radar.py --debate 5 --rounds 2

# github repo 미검증 N개사를 GitHub API 로 검증·보강(star/lang, 환각 repo 제거)
GITHUB_TOKEN=$(gh auth token) python bin/build_company_tech_radar.py --github 100

# 무한 루프로 '이유'·다이어그램·심화를 계속 발전(증분)
python bin/build_company_tech_radar.py --refine 5 --loop --interval 1800
```

- **리파인/토론은 절대 내용을 줄이지 않는다.** 심화 해설(`deep_dive`)은 새 토픽을 덧붙이고
  기존 토픽은 더 긴 본문일 때만 갱신한다.
- 주기 갱신은 `bin/refresh-radar.sh`(+ `install-radar-cron.sh`)로 cron 등록. `gh` 로그인
  시 토큰을 실어 GitHub API 한도를 5000/h 로 올린다.

## 데이터 모델 요약 (`src/types.ts`)

`RadarFile { generated_at, total, countries[], domains[], domain_groups[], refined, companies[] }`,
`RadarCompany { key, name, country, domain, languages[], stack{backend,frontend,data,infra},
architecture[], diagram?, why_language, why_architecture, summary, deep_dive[], debate?, github?, ... }`.
토론: `Debate { architectures[], transcript[{round,role,text}], verdict{chosen,rationale,key_insights,open_questions} }`.
