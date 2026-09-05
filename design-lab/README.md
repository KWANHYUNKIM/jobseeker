# 디자인 랩

채용 공고 한 건을 **한 장의 이미지**로 접고, 그걸 인스타그램·페이스북·링크드인에
올리기까지를 한 곳에서 굴리는 실험실. 크롤 파이프라인(8765/8770/8771)과 뷰어(5173)를
건드리지 않고 따로 논다. 여기서 확정된 것만 나중에 `jd-viewer` 로 옮긴다.

```
python design-lab/serve.py        # http://localhost:8780
```

## 왜 있나

`jd-viewer` 의 공고 상세(`src/components/JobDetail.tsx`)를 새로 짜기 전에,
남들이 '상세'를 어떻게 접는지부터 본다. 예쁜 화면 구경이 아니라 **레이아웃 /
섹션 순서 / 카피 / 강약 만드는 법** 을 떼어 보는 게 목적이다.

## 화면 셋

| 탭 | 하는 일 |
|---|---|
| 레퍼런스 | 인스타에서 모은 상세페이지·채용포스터 캡처와, 거기서 읽어낸 특징(읽은 것 / 훔칠 것 / 버릴 것) |
| 포스터 스튜디오 | 공고를 골라 템플릿·포맷·팔레트를 바꿔 가며 실제 크기로 미리 본다. 플랫폼별 캡션도 같이 나온다 |
| 발행 큐 | 렌더 → DRY 발행 → 실제 발행. 어디에 무엇을 올렸는지의 원장 |

## 흐름

```
all_jobs_enriched.json                (크롤 산출물, 127MB)
        │  poster/jobsource.py  ← 필요한 필드만 깎아 state/jobs_index.json
        ▼
   PosterSpec                         poster/model.py
        │  직군명 정리 · 팔레트 선택 · 불릿 3개 · 회사 마크(assets/)
        ▼
   HTML 한 장                          poster/templates/*.html
        │  poster/render.py — Playwright 로 캔버스 크기 그대로 스크린샷
        ▼
   out/<공고키>/<템플릿>_<포맷>.jpg
        │  publish/caption.py — 플랫폼별 카피·해시태그
        ▼
   instagram / facebook / linkedin    publish/*.py
        └ state/publish_queue.json 에 결과를 남긴다
```

## CLI (랩 UI 의 버튼들도 결국 이걸 부른다)

```bash
cd design-lab
P=../catch_capture/.venv/bin/python          # Playwright 가 여기 있다

$P -m poster.jobsource                        # 공고 색인 다시 만들기
$P -m poster.render wanted-339244 --template info_grid --format ig_portrait
$P -m publish.cli check                       # 플랫폼별 자격 점검
$P -m publish.cli plan wanted-339244 -t role_hero -p instagram,linkedin
$P -m publish.cli render <item-id>
$P -m publish.cli caption <item-id>
$P -m publish.cli publish <item-id>           # 기본 dry-run: 요청만 만들어 보여 준다
$P -m publish.cli publish <item-id> --live    # 진짜로 올린다
```

## 템플릿

레퍼런스에서 뽑은 결론이 그대로 템플릿 하나씩이다.

| id | 출처 | 성격 |
|---|---|---|
| `role_hero` | hire-03 imago.xyz | 직군명이 주인공. 마감 한 줄이 위에, 회사는 아래 작게 |
| `info_grid` | hire-05 sddaejeon | 담당업무·지원자격·우대사항 라벨을 그대로 세운다 |
| `point_cards` | detail-04 design_j_d | Point.01/02/03 번호 카드. 캐러셀 2~4번째 장 |
| `swiss_white` | hire-04 designfever | 여백 90%, 정보는 네 귀퉁이. 짧은 공고 전용 |

템플릿은 그냥 HTML 파일이다. 치수를 전부 `min(1vw,1vh)` 기준으로 써서 캔버스 크기만
바꾸면 인스타 세로/정사각/스토리·링크드인 가로가 같은 판으로 늘어난다.
문법은 `{{key}}` / `{{#if}}` / `{{#unless}}` / `{{#each}}` 넷뿐(`poster/templates.py`).

**없는 정보는 그리지 않는다.** 마감일이 없으면 '상시 채용'이라고 지어내지 않고 그 줄을 비운다.

## 회사 이미지

```
assets/companies/<회사>/logo.png    정사각 권장. 히어로 배경 마크로도 쓰인다
assets/companies/<회사>/bg.jpg      (선택)
assets/index.json                   회사명 → 폴더 별칭
```

```python
from poster import assets
assets.put("토스", Path("~/Downloads/toss.png").expanduser())   # 보관소에 넣기
```

로고가 없으면 회사 이니셜로 대체한다. 렌더할 때는 `data:` URI 로 심으므로 브라우저에
파일 접근 권한을 주지 않는다.

## 발행 준비물

`config/accounts.example.json` 을 `accounts.json` 으로 복사해 채운다(커밋 금지).
환경변수(`DESIGN_LAB_IG_TOKEN` 등)가 있으면 파일보다 우선한다.

- **인스타그램** — 프로 계정 + 연결된 페이스북 페이지 + `instagram_content_publish` 권한.
  이미지를 **공개 URL** 로 줘야 해서 `public_base_url` 이 없으면 발행이 막힌다
  (out/ 을 그대로 웹에 열지 말 것 — 노출용 경로를 따로 둔다).
  본문에 링크가 안 걸리므로 캡션은 '프로필 링크' 로 유도한다.
- **페이스북** — 페이지 액세스 토큰(사용자 토큰 아님) + `pages_manage_posts`.
- **링크드인** — 앱 + 회사페이지 관리자, `w_organization_social`. 이미지를 먼저 업로드해
  URN 을 받고 그걸 글에 붙이는 3단계.

자격이 없어도 `plan → render → DRY 발행` 까지는 전부 돌아간다. DRY 는 어떤 요청을
어떤 순서로 보낼지만 찍어 준다.

## 안전장치

- 발행은 언제나 dry-run 이 기본. `--live` 를 줘야 실제로 나간다.
- 같은 공고가 이미 올라간 플랫폼은 건너뛴다(`--force` 로만 무시).
- 무거운 일(크로미움, 실제 발행)은 서버가 아니라 자식 프로세스에서 돈다 — 8GB 머신.

## 수집 방법

인스타그램은 로그인 세션이 필요해서 Playwright 로는 못 긁는다. 사용자 Chrome
(claude-in-chrome)으로 해시태그 그리드를 열고 **포스트를 하나씩 열어** 캡처한다.
그리드 통째 캡처는 나중에 관리가 안 되므로 쓰지 않는다.

1. `https://www.instagram.com/explore/tags/<태그>/` 진입 후 이미지 로드까지 대기
2. 첫 포스트 클릭 → 모달 진입
3. 캡처 → 모달 오른쪽 바깥 화살표로 다음 포스트. 캐러셀은 이미지 위 화살표로 슬라이드 이동
4. `refs.json` 에 항목 추가 (분석 세 줄은 반드시 채운다)

돌아 본 태그: `#상세페이지디자인` `#채용포스터` `#recruitmentposter` `#채용공고`

## 레퍼런스 이미지 두 벌

| 폴더 | 무엇 |
|---|---|
| `refs/instagram/posts/` | 원본 캡처. 인스타 UI(캡션 패널·사이드바)가 같이 찍혀 있다 |
| `refs/instagram/crops/` | 같은 파일명으로, 포스트 이미지 영역만 잘라낸 것 |

잘라내기는 인스타 모달의 기하로 푼다 — 캡션 패널(흰 세로 띠) 오른쪽 끝을 찾아
캡션 폭 407px 를 빼면 이미지 오른쪽 경계, 모달이 뷰포트 가운데(x=778)에 서 있으므로
거기서 왼쪽 경계가 나온다. 폭은 인스타가 허용하는 1:1 / 4:5 중 가까운 쪽으로 스냅한다.
`refs.json` 의 `files` 는 잘라낸 쪽을, `files_raw` 는 원본을 가리킨다(갤러리는 `files`).

## 피그마 시안

레퍼런스에서 읽어낸 것을 실제 화면으로 옮긴 파일:
**채용 상세페이지 디자인랩** — https://www.figma.com/design/mrtdYak7qUaNJQvWgT3RNI

| 페이지 | 내용 |
|---|---|
| `01 · 레퍼런스` | 잘라낸 캡처 14장 + 건별 '훔칠 것' 한 줄 |
| `02 · 토큰 & 컴포넌트` | 색 4칸(+보조 5) · 타입 6단 · 간격 스케일. 변수 26개(`디자인 토큰`)와 텍스트 스타일 9개로 박아 뒀다 |
| `03 · 공고 상세 시안` | Desktop 1440 / Mobile 390. 더미 공고(PAYMO · 결제 정산 백엔드)로 채운 상세 화면 |

시안이 레퍼런스에서 가져온 것:
- 히어로는 회사가 아니라 **자리**가 주인공 — 직군명 88px, 마감 한 줄만 위에 (hire-03)
- 메타 4분할(경력·고용형태·근무지·마감) 아이콘 카드 (detail-04)
- 섹션은 `01 담당업무 / 02 지원자격 / 03 우대사항` — 항목 이름을 그대로 쓰고 번호를 박는다 (hire-05, detail-04)
- 강약은 색이 아니라 타입 3단으로. 색은 Ink / Paper / Surface / Accent 넷으로 못 박음 (detail-05, detail-01)
- 눈이 멈출 자리로 기술 칩 — 진한 칩 = 백과사전 문서가 있는 낱말 (detail-06)
- 하단은 감성 끝내고 사무 한 덩어리 — 접수 / 제출서류 / 문의 (hire-02, detail-03)
- 맨 아래 '이 자리 준비하려면' 3장 = 백과사전·역설계 문서 재활용 (hire-06)

## 아직 안 한 것

- 피그마 컴포넌트(버튼·칩 변형 세트)는 못 만들었다 — Figma MCP 무료 플랜 호출 한도에 걸렸다.
  시안은 아직 컴포넌트가 아니라 프레임 조립이다
- 기업 채용 사이트(토스·당근·쿠팡) 실제 상세 화면은 아직 안 모았다
- 시안을 `jd-viewer/src/components/JobDetail.tsx` 로 옮기는 일은 시작 전
