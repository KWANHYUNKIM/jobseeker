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
