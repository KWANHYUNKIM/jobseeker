# 조사 방법 — 터진 릴스 모으기

로그인한 인스타 웹 탭(Claude in Chrome)에서 페이지 안 `fetch` 로 검색 API 를 부른다. 계정 행동(팔로우·좋아요·댓글)은 하지 않는다.

## 수집

`/api/v1/fbsearch/web/top_serp/?query=<키워드>` (헤더 `X-IG-App-ID: 936619743392459`, `credentials:'include'`) 응답을
훑어 `media_type === 2`(릴스)만 남긴다. 받는 필드:

| 필드 | 뜻 |
|---|---|
| `code` | 주소 `instagram.com/reel/<code>/` |
| `play_count` (없으면 `ig_play_count`) | 조회 |
| `like_count` · `comment_count` | 좋아요 · 댓글 |
| `video_duration` | 길이(초) |
| `taken_at` | 올린 시각(유닉스) |
| `clips_metadata.music_info.music_asset_info.title` / `original_sound_info.original_audio_title` | 음원 |
| `caption.text` | 캡션 |

한 편 더 자세히: `/api/v1/media/<pk>/info/` (pk 는 code 를 base64url 로 읽은 정수).

```js
// 키워드 5개씩 병렬 — 탭이 숨으면 setTimeout 이 분당 1번으로 느려지므로 sleep 대신 Promise.all 로 묶는다
const one = async q => { const r = await fetch('/api/v1/fbsearch/web/top_serp/?query=' + encodeURIComponent(q),
  {credentials:'include', headers:{'X-IG-App-ID':'936619743392459'}}); /* ...walk(json) 로 media_type 2 만 모은다... */ };
for (let i = 0; i < Q.length; i += 5) await Promise.all(Q.slice(i, i + 5).map(one));
```

## 주의

- **페이지를 옮기면 모은 것이 사라진다**(window 변수) — 다 모은 뒤 표로 뽑고, 다른 주소로 가기 전에 `data/` 에 적는다.
- 자바스크립트 결과는 2,000자 안팎에서 잘린다 — 짧은 열만 여러 번 나눠 뽑는다.
- `web_profile_info`·`feed/user` 는 몇 번 부르면 429(속도 제한) — 검색 API 위주로, 계정별 조회는 아껴 쓴다.
- 탭이 화면 뒤에 있으면 **화면 캡처가 안 된다**. 첫 프레임을 보려면 사람에게 그 창을 앞에 띄워 달라고 한다.
- 남의 화면·글은 옮기지 않는다 — 형식(길이·구조·소리·훅의 모양)만 적는다.

## 키워드 (회차 1)

연봉: 신입 연봉 · 개발자 연봉 · 대기업 연봉 · 공기업 연봉 · 삼성 연봉 · 초봉 · 신입 초봉 · 직업별 연봉 · 연봉 순위 · 연봉 협상 · 연봉 공개 · 월급 공개 · 첫 월급 · 성과급
회사: 중소기업 현실 · 중견기업 · IT 회사 · 판교 · 네이버/카카오/토스/삼성전자 입사 · 복지 좋은 회사 · 회사 복지 · 웰컴키트 · 입사 선물 · 사원증
직장인: 직장인 공감 · 직장인 현실 · 회사 생활 · MZ 직장인 · 직장 상사 · 팀장님 · 회식 · 연차 · 칼퇴 · 야근 · 출근 · 재택근무 · 구내식당 · 회사 점심 · 탕비실 · 직장인/신입/퇴사 브이로그
취업: 취업 현실 · 취준생 · 신입사원(공감) · 면접 꿀팁/질문/썰 · 자소서 · 이력서 · 이직 · 퇴사 · 채용 · 취업 · 합격 · 인턴 · 인적성 · AI 면접 · 공채 · 대기업 합격 · 취업 성공 · 불합격 · 서류 탈락
개발자: 개발자 · 개발자 현실 · 개발자 취업 · 코딩 · 비전공 개발자 · 개발자 면접 · 코딩테스트 · 개발자 브이로그 · 부트캠프 · SSAFY · IT 취업 · 반도체 취업

## 영상·댓글 받기 (릴스 공부 — `insta-reels` 루프)

탭이 화면 뒤에 있으면 인스타가 영상을 재생하지 않는다. 그래서 탭에서는 **주소·숫자·캡션·댓글만 모으고**, 영상은 로컬 수신기가 받는다.

1. 수신기: `cd design-lab && python -m research.reelstudy serve --dir <작업폴더>` (백그라운드, 127.0.0.1:8799)
2. 인스타 탭에서 고른 code 마다 `/api/v1/media/<pk>/info/`(영상 주소·숫자·캡션·음원)와
   `/api/v1/media/<pk>/comments/?can_support_threading=true`(15개씩, `next_min_id` 로 3쪽까지 → 40여 개, 좋아요·답글 수)를 모은다.
3. 모은 것을 `[{name, url, meta}]` 로 만들어 **같은 탭을** `http://127.0.0.1:8799/#<JSON>` 으로 옮긴다 — 수신기 페이지가 POST 로 넘기고 영상을 받는다.
   (인스타 페이지에서 바로 로컬로 보내면 CSP 에 막힌다. 주소는 탭 밖으로 꺼내지 않는다.)
4. `python -m research.reelstudy frames --clean --dir <작업폴더>` → `sheet_<이름>.jpg`(0·0.5·1·1.5·2·3초 + 고르게 10장), 영상은 지운다.
5. 장면표를 열어 보고, `<이름>.json` 의 댓글을 좋아요 순으로 읽어 reels-study.md 분류(C1…)로 센다. 끝나면 탭을 인스타로 되돌린다.

고르는 법: `data/reels-1m-2026-10-02-links.csv` 와 새 키워드 검색에서 **reels-study.md·teardown.md 에 없는 것**, 갈래가 겹치지 않게(돈 표·콩트·브이로그·인터뷰·실촬영·공식 계정 섞어서).
