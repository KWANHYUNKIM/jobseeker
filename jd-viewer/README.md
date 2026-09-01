# jd-viewer

채용 크롤 파이프라인(`catch_capture/`)이 만든 데이터를 시각화하는 React/Vite 뷰어.
`public/` 의 JSON 을 그대로 소비하며, 상단 탭으로 화면을 전환한다. 모든 화면은 진짜 경로를
가진다(`/jobs/wanted-364849`, `/companies/쿠팡`, `/radar/netflix`) — 새로고침·공유·뒤로가기가
그대로 되고, 빌드가 주소마다 정적 HTML 을 깔아 검색엔진이 색인할 수 있다.

## 실행

```bash
npm install
npm run dev        # 개발 서버(5173)
npm run build      # tsc -b + vite build (타입체크 포함, 배포 산출물 dist/)
npm run preview    # 빌드 결과 미리보기
```

## 주소와 검색 노출(SEO)

해시 라우팅(`#radar/netflix`)을 경로 라우팅으로 바꿨다. 해시 뒤는 서버도 검색엔진도
URL 의 일부로 보지 않아서, 공고가 1만 건이어도 색인되는 주소는 `/` 하나뿐이었다.

| 화면 | 주소 |
|------|------|
| 공고 목록 | `/` (검색어는 `?q=`, 색인 제외) |
| 공고 상세 | `/jobs/<사이트>-<공고번호>` |
| 기업 기술스택 | `/companies`, `/companies/<회사>` |
| 기술 레이더 | `/radar`, `/radar/<key>` |
| 기술 역설계 | `/reveng/<slug>`, `/reveng/문서/<slug>` |
| 기술블로그 | `/blog`, `/blog/<id>` (원문이 색인 주체 — noindex) |
| 그 외 탭 | `/mindmap` `/calendar` `/reposts` `/trend` |

구성 요소는 셋이다.

- `src/lib/router.ts` — pushState 라우터(60줄, 의존성 없음). 예전 해시 주소는
  진입 시 새 경로로 리다이렉트한다.
- `src/lib/seo.ts` + `src/lib/urls.ts` — 라우트마다 제목·설명·정규 URL·오픈그래프·
  구조화 데이터(JobPosting/Organization)를 `<head>` 에 갈아끼운다.
- `scripts/prerender.mjs` — `npm run build` 끝에 주소별 정적 HTML 과 `sitemap.xml`,
  `robots.txt` 를 찍는다. 크롤러와 카카오톡·슬랙 미리보기 봇이 보는 게 이것이다.
  ```bash
  PRERENDER_JOBS=2000 npm run prerender    # 공고 페이지 수 제한(디스크 절약)
  ```
  현재 12,000쪽 남짓(공고 10.5k · 회사 2k · 레이더 100 · 역설계 60), `dist/` 기준 약 115MB.

### 배포 도메인

`canonical`·오픈그래프·`sitemap.xml`·`robots.txt` 의 기준 오리진은 `.env` 한 줄이다.
앱(`seo.ts`)과 프리렌더가 **같은 값**을 읽는다 — 예전에는 이름이 둘(`VITE_SITE_URL` /
`SITE_URL`)이라 한쪽만 고치면 화면은 새 도메인인데 sitemap 은 옛 도메인을 가리켰다.

```bash
cp .env.example .env      # VITE_SITE_URL=https://내도메인  (끝 슬래시 없이)
npm run build
SITE_URL=https://staging.example.com npm run build   # 한 번만 덮을 때(CI 등)
```

값이 없으면 `canonical` 은 상대경로로만 붙고 `sitemap.xml`·`robots.txt` 는 만들지
않는다(지난 빌드에 남아 있던 것도 지운다). 틀린 도메인이 박힌 색인 파일을
내보내느니 안 내보내는 쪽이 낫다 — 검색엔진에 "정본은 저기"라고 잘못 알려주는
값이기 때문이다.

서버는 `$uri → $uri/ → /index.html` 순으로 찾는다(`nginx.conf`, `bin/serve_viewer.py`).
프리렌더가 있으면 그걸, 없으면 앱 셸을 주고 브라우저에서 라우터가 이어받는다.

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
