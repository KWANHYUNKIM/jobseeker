# 소셜 자동 발행 — 인스타그램 + 페이스북 페이지

회사 전용 포스터(BRAND_RESEARCH.md)를 **사람이 승인한 것만** 정해진 시각에 인스타와 페이스북
페이지에 올리고, 어떻게 올라갔는지는 크롤 운영 대시보드(8770)의 **인스타 발행** 칸에서 본다.

```
[윈도우] 포스터 완성 ── publish.cli approve ──▶ inbox/<id>/ ── publish.cli push ──▶ [맥] inbox/<id>/
                                                                                      │ launchd 5분마다
                                                                        publish.daemon tick
                       받기 → 마감 제외 → 예약(12:30·19:30) → 한 건을 두 곳에 → 반응·토큰
                                                                                      │
                                     state/publish_queue.json (원장) · state/publish_status.json
                                                                                      │
                                                            8770 '인스타 발행' 칸 (읽기 전용)
```

올리는 단위는 둘이다.

| 단위 | 무엇 | 명령 |
|---|---|---|
| 공고 한 건 | 그 회사 전용 판 한 장 | `approve <공고키>` |
| **묶음(카테고리)** | 키워드 표지 + 차례 표지 + 공고 판 여러 장을 **한 게시물**로 (인스타 캐러셀 / 페이스북 사진 여러 장) | `approve-collection <카테고리>` |

사람들이 저장하고 공유하는 건 공고 한 장보다 묶음이다. 카테고리는 여섯 가지다.

| 카테고리 | 표지에 뜨는 말 | 고르는 기준 |
|---|---|---|
| `week` | 이번 주 채용 · 9월 14–20일 | 모집중 공고(기간은 라벨) |
| `deadline` | 마감 임박 · 9월 14–20일 마감 | 마감일이 그 기간에 드는 공고 |
| `role` | 직군별 채용 · 백엔드 개발자 | 제목·기술로 판정한 직군(backend/frontend/data/infra/mobile) |
| `size` | 회사 규모별 · 대기업 채용 | `company_meta.json` 의 회사 규모 |
| `stack` | 기술별 채용 · React 쓰는 곳 | 기술 스택에 그 낱말이 있는 공고 |
| `newgrad` | 신입 가능 | 경력 조건에 '신입' 이 있는 공고 |

### 끝난 모집은 올리지 않는다

이게 제일 중요하다. 근거가 셋 다 약해서 장치를 여러 겹 둔다.

| 겹 | 무엇을 보나 | 어디 |
|---|---|---|
| 1 | 색인의 마감 표기가 지났나(연도 없는 '~ 06.16' 도 읽는다) | `collection._deadline` |
| 2 | 회사 조사 중 발견한 원본 데이터 문제(OCR 깨짐 등) | `brands/<회사>.json` 의 `data_warning` |
| 3 | **원본 사이트에 "지금도 모집중?" 묻기** | `publish/openness.py` (크롤의 `pipeline/close_check` 재사용) |
| 4 | 원본에서 찾아온 마감일이 지났나 | `publish/postingdates.py` |

**네 겹 다 고르는 단계에서 돈다** — 판을 그리기 전이다. 렌더가 제일 비싸다(판 하나에 브라우저 +
수십 초). 확인 불가(차단·타임아웃)는 '열려 있다' 가 아니므로 묶음에 넣지 않는다.

색인의 `status: active` 는 못 믿는다 — 모집중 9,245건 중 3,050건(33%)이 마감일이 지난 공고였고,
마감 표기가 아예 없는 공고는 영구 '모집중' 으로 남는다(wanted 는 마감 필드가 없다).

### '언제부터 언제까지' 는 원본에서 찾아온다

색인에는 마감 한 줄뿐이라 사이트마다 가서 게시일·마감일을 찾는다(`publish/postingdates.py`,
찾은 값은 5일 캐시).

| 사이트 | 어디에 있나 |
|---|---|
| wanted | 공고 페이지 JSON-LD `datePosted` |
| jumpit | position API `publishedAt` / `closedAt` / `alwaysOpen` |
| jobkorea | 공고 페이지 JSON-LD `datePosted` / `validThrough` |
| saramin | 공고 페이지의 '시작일 … 마감일 …' |
| dev(catch) | 상세 JSON-LD `datePosted` / `validThrough` |

판에 적는 말은 이 순서로 고른다(`collection.period_label`):

1. 시작·마감 둘 다 → **"8월 10일부터 8월 31일까지 모집중"**
2. 시작만 → **"9월 11일부터 모집중"**
3. 마감만 → **"9월 21일까지 모집중"**
4. 회사가 쓴 방식 → **"상시 채용 · 마감 없음"** / "수시 채용 · 채용 시 마감"
5. 아무것도 못 찾음 → **아무것도 적지 않는다.** 우리 사정(확인 시점)을 판에 적으면 보는 사람에게는
   모를 소리가 된다. 마감된 공고는 이미 걸러졌으니 판에 남은 것은 모집중인 공고다.

판 17개가 같은 문구를 쓴다 — 마감을 직접 그리는 판은 `D.until` 을 쓰고, 안 그리는 판에는
`_frame.js` 의 `Frame.period` 가 빈 귀퉁이를 찾아 붙인다(글자 크기를 맞춘 뒤에 붙으므로 본문이
줄지 않는다).

묶음이 지키는 것:

- **회사 전용 판이 있는 회사만 들어간다.** 전용 판은 BRAND_RESEARCH.md 절차로 회사마다 만든 것
  (대표 물건 → 실제 서체 → 공식 색 → 원본 이미지)이고, 기본 틀 판을 섞으면 묶음 전체가
  '색만 바꾼 판' 으로 보인다. 자리가 모자라면 **어떤 회사 판을 만들면 채워지는지** 같이 찍어 준다
  (`poster.collection gaps <카테고리>`). 급할 때만 `--allow-generic` 으로 기본 틀을 섞는다.
- **회사는 한 번씩만.** 같은 회사가 여러 장이면 묶음이 아니라 그 회사 광고가 된다.
- **순서는 알아보는 회사부터** — 전용 판이 있는 회사 → 큰 회사 → 마감 빠른 순. 앞장에 모르는
  회사만 나오면 아무도 넘겨 보지 않는다.
- **앞장 두 개의 역할이 다르다.** 1장은 키워드만 있는 표지("2026.09 · 3주차 / 개발자 채용 /
  8곳 모집중") — 피드에서 넘길지 말지가 여기서 갈린다. 2장은 차례로, 회사·자리·경력만 세운다
  (장식 없음). 캡션에도 같은 목록을 글로 적는다 — 검색과 저장은 글에서 걸린다.
- **10장 상한**(인스타 캐러셀) = 표지 2 + 공고 8.
- **브랜드 전용 판이 안 맞으면 기본 틀로 물러난다.** 전용 판은 그 회사의 '어떤 공고' 에 맞춰
  만든 것이라, 다른 공고를 넣으면 본문이 16px 아래로 떨어질 수 있다.
- **묶음은 마감 검사를 하지 않는다.** 9곳 중 한 곳이 닫혔다고 묶음을 버릴 수는 없다. 대신
  승인한 날 안에 나가도록 슬롯을 가까이 둔다(`--since/--until` 로 기간을 박아 두는 것도 방법).

한 판이 두 곳에 나간다. **캡션은 플랫폼마다 따로** 만든다(`publish/caption.py`) — 인스타는
해시태그가 붙고 링크가 안 걸리므로 주소를 글자로 적고, 페이스북은 링크가 그대로 걸린다.
승인 묶음의 `caption_instagram.txt` / `caption_facebook.txt` 를 push 전에 고쳐도 된다.

## 왜 이렇게 나눴나

| 결정 | 이유 |
|---|---|
| 사람은 **승인**까지만 | 판마다 회사 사진·캠페인 그래픽이 들어 있다. 승인이 곧 "사용 허락 확인했음" 이다 |
| 원장은 **맥에만** | 포스터는 윈도우에서, 발행·대시보드는 맥에서 돈다. 두 머신이 같은 파일을 고치지 않게 윈도우는 묶음만 보낸다 |
| bundle.json 을 **맨 나중에** 보낸다 | 데몬은 bundle.json 이 있는 묶음만 받는다. 반쯤 복사된 묶음을 집지 않는다 |
| 대시보드는 **읽기만** | 8770 은 인증 없이 터널로 열려 있다. 버튼·토큰을 두면 주소를 아는 누구나 우리 계정으로 올린다 |
| 이미지는 **exposed/ 에 해시 이름** | 인스타는 공개 URL 로만 받는다(페이스북은 파일을 직접 올린다). out/ 을 열면 승인 안 한 판까지 새고, 공고키 이름이면 주소를 짐작한다 |
| **한 tick 에 한 판**, 하루 슬롯 | 밀린 예약이 한꺼번에 쏟아지면 계정이 공고 게시판처럼 보인다. 인스타 한도(24시간 100건)와도 멀다 |
| 한쪽 실패는 **그쪽만 재시도** | 인스타는 됐는데 페이스북이 막히는 일이 흔하다. 재시도 때 인스타에 같은 판을 두 번 올리면 안 된다 |
| 한쪽 자격이 없으면 **판 전체가 연습** | 두 곳에 같이 올리려던 판이 조용히 한 곳에만 올라가지 않게. 한 곳만 원하면 `approve -p instagram` |
| live 기본 **꺼짐** | 자격 없이 설치해도, 켜기 전까지는 연습 발행(rehearsed)만 남는다 |
| 발행 직전 **마감 확인** | 승인하고 며칠 뒤 올라가는 사이 공고가 닫힐 수 있다 → skipped |

## 상태

```
approved → scheduled → published   (platforms 전부 성공)
                    ↘ (한 곳이라도 실패) 다음 슬롯에 실패한 곳만 재시도, 3번째 실패면 failed
                    ↘ rehearsed   live 꺼짐·자격 없음 — 실제로 안 나감
                    ↘ skipped     공고 마감 / 두 곳 다 이미 올라감
```

rehearsed·failed·skipped 는 `requeue` 로 되돌린다. 이미 올라간 플랫폼은 빼고 남은 곳만 다시 간다.

## 매일 쓰는 명령

```bash
cd design-lab
python -m publish.cli approve wanted-376128            # 인스타+페이스북 (기본)
python -m publish.cli approve wanted-376128 -p instagram   # 한 곳만

# 묶음(카테고리) — 표지 + 공고 판 여러 장이 한 게시물로
python -m poster.collection cats                       # 카테고리 목록
python -m poster.collection pick week                  # 뭐가 들어가나 먼저 본다
python -m publish.cli approve-collection week                      # 이번 주 채용
python -m publish.cli approve-collection deadline --since 2026-09-21 --until 2026-09-27
python -m publish.cli approve-collection role --value backend --limit 8
python -m publish.cli approve-collection size --value 대기업
python -m publish.cli approve-collection stack --value React
#   → inbox/<id>/caption_*.txt 를 고쳐도 된다(push 전에)
python -m publish.cli push                             # 맥으로 (ssh jobseeker-mac)

# 맥에서
python -m publish.cli queue                            # 원장 — 어디에 올라갔는지까지
python -m publish.daemon tick                          # 기다리지 않고 한 번
python -m publish.cli requeue --all-rehearsed          # 연습분을 실제 발행 대기로
python -m publish.cli check                            # 자격·한도·토큰 만료
```

## 처음 한 번 — 계정 연결

> 메타 개발자 화면의 메뉴 이름은 자주 바뀐다. 아래는 2026-09 기준 공식 문서
> (developers.facebook.com/docs/instagram-platform) 의 흐름이다.

두 곳에 다 올리려면 **페이스북 로그인 방식** 하나로 묶는 게 낫다(토큰 하나로 둘 다 됨).
인스타만 할 거면 페이지 없이 인스타 로그인 방식(`login: "instagram"`, graph.instagram.com)도 된다.

1. **인스타를 프로 계정으로** — 앱 설정 → 계정 유형 → 비즈니스/크리에이터. 개인 계정은 API 게시가 안 된다.
2. **페이스북 페이지 만들기** — facebook.com/pages/create.
   페이스북은 **개인 담벼락에 API 로 못 올린다.** 페이지가 있어야 하고, 인스타를 이 방식으로 쓰려면
   인스타 프로 계정이 그 페이지에 연결돼 있어야 한다.
3. **메타 앱** — developers.facebook.com → 앱 만들기(비즈니스) → Instagram 제품 추가.
4. **권한 다섯 개** — 하나라도 빠지면 그쪽이 막힌다.

   | 권한 | 없으면 |
   |---|---|
   | `instagram_basic` | 인스타 계정 조회 불가 |
   | `instagram_content_publish` | **인스타 게시 불가** |
   | `pages_show_list` | 페이지 목록이 비어 보인다 |
   | `pages_read_engagement` | 페이지 정보·연결된 인스타 조회 불가 |
   | `pages_manage_posts` | **페이스북 페이지 게시 불가** |

   동의 창에서 **올릴 페이지를 반드시 선택**한다. 안 고르면 `me/accounts` 가 빈 목록으로 온다.
5. **토큰 정리** — 발급받은 단기 사용자 토큰(1~2시간)을 장기 토큰(60일)으로 바꾸고, 거기서
   **페이지 토큰**을 뽑는다. 장기 사용자 토큰에서 나온 페이지 토큰은 만료가 없다.
   인스타 로그인 방식이면 `refresh_access_token` 으로 60일씩 늘린다(데몬이 만료 7일 전에 한다).
6. **계정 번호** — 페이스북 로그인 방식은 `me/accounts` → 페이지의 `instagram_business_account.id`,
   인스타 로그인 방식은 `graph.instagram.com/v21.0/me?fields=user_id`.
7. **맥의 `design-lab/config/accounts.json`** (커밋 금지):

   ```json
   {
     "public_base_url": "https://<뷰어 고정 주소>/ig",
     "autopublish": {"live": false, "slots": ["12:30", "19:30"]},
     "instagram": {"login": "facebook", "ig_user_id": "<페이지에 연결된 인스타 번호>",
                   "access_token": "<장기 사용자 토큰 또는 페이지 토큰>",
                   "token_expires_at": "2026-11-15T10:00:00"},
     "facebook": {"page_id": "<페이지 번호>", "access_token": "<페이지 토큰>"}
   }
   ```

8. **공개 주소** — `public_base_url` 은 **재시작해도 안 바뀌는 주소**여야 한다(인스타용).
   quick 터널(trycloudflare)은 재시작마다 바뀌어 예약분이 전부 실패한다 → ngrok 정적 도메인이나
   Cloudflare 고정 터널(`deploy/README.md`).
9. **데몬 등록** — `./deploy/setup-publisher.sh` → 8770 칸에 "연습 모드" 가 뜬다.
10. **확인** — `python -m publish.cli check` 가 두 플랫폼 모두 "준비됨" 과 인스타 한도 `0/100` 을
    보여 주면 된다. 판 하나를 approve → push → 연습 발행으로 흐름을 본 뒤 `autopublish.live` 를
    `true` 로 바꾸고 `requeue --all-rehearsed`.

### 2026-09-16 에 실제로 막혔던 것

첫 토큰은 이랬다 — 같은 실수를 반복하지 않으려고 적어 둔다.

- `instagram_content_publish` 가 없었다 → 인스타 게시 불가.
- 동의 창에서 페이지를 고르지 않아 `me/accounts` 가 **빈 목록**이었다 → 페이스북 게시 불가,
  인스타 계정 번호도 못 찾음.
- 단기 토큰이라 **약 1시간 뒤 만료**였다 → 장기 토큰 교환이 빠졌다.

`python -m publish.cli check` 가 이 셋을 한 번에 보여 준다.

## 대시보드 칸이 보여 주는 것

- 경고 띠 — 데몬 20분 넘게 무응답 / 연습 모드인 이유 / 한쪽 자격만 있는 상태 / 공개 주소 없음 /
  토큰 7일 이내 만료
- 예약·게시됨·연습·실패 건수, 인스타 24시간 게시 한도, 토큰 남은 날
- 다음 예약(회사·직무·나갈 곳·시각), 확인할 것(실패·재시도·뺌과 플랫폼별 이유)
- 최근 게시 — 썸네일과 플랫폼별 링크, 인스타 좋아요·댓글(게시 뒤 14일, 3시간마다 갱신)
- 데몬 기록 — 받음·예약·게시·실패 한 줄씩

예약 중인 판은 썸네일을 주지 않는다(공개 전 판의 주소를 흘리지 않는다). 오류 문구 속 토큰 흔적은 가린다.

## 권리

승인 전에 확인한다: 판에 들어간 **회사 이미지·캠페인 그래픽·사진의 사용 허락**.
각 회사 `out/<키>/RECORD_v*.md` 끝의 권리 메모에 무엇을 확인해야 하는지 적혀 있다
(쿠팡 뉴스룸 자료는 변형 금지, 오늘의집 주방 사진은 원 촬영자 확인 등).
