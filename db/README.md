# DB 설계 — JSON 덩어리에서 PostgreSQL 로

`db/schema.sql` 이 정본이다. 이 문서는 **왜 이렇게 잘랐는지**와 **어떻게 옮기는지**를 적는다.

## 왜 바꾸나 — 측정된 것들

현재 원본은 `jd-viewer/public/all_jobs_enriched.json` 하나다. 17,584건짜리 99MB 배열을
매 사이클 통째로 다시 쓴다. 키가 없으니 제약도 없고, 그 결과가 지금 화면에 보이는 정합성 문제다.

| 증상 | 실측 | 원인 |
|---|---|---|
| 같은 회사가 여러 회사로 갈림 | 표기 8,438개 중 **1,383 그룹**이 동일 회사 | `aggregate._norm_key` 는 공백·소문자만 처리 — `(주)클로봇` ≠ `클로봇` |
| 같은 공고가 중복 생존 | **1,150건** | 중복 키가 `(회사명, 제목)` 문자열 쌍이라 표기가 갈리면 못 잡는다 |
| 한 공고가 모집중이자 마감 | 위 1,150건에 다수 포함 | 사이트마다 status 가 따로 달려 있고 이를 묶을 키가 없다 |
| 결측이 그냥 통과 | company 없는 공고 **492건**, title 없는 **25건** | 중복 검사가 `if key[0] and key[1]` 이라 결측이면 건너뜀 |
| `(site,pid)` 중복 | **7건** | 그 쌍에 유일성 제약이 없다 |
| 모집중인데 마감일 과거 | active 9,458건 중 **2,373건** | `status` 가 계산 시점에 파일로 구워진다 |
| 마감 근거 없음 | active 중 **5,615건(59%)** | 마감일 표기가 없는 사이트(wanted 3,120건 전량) |
| 원장이 사본 1개 | `job_closures.json` | git 미추적 + 운영 맥 로컬. 날아가면 재확인 이력 전부 소실 |
| 통째로 날아간 적 있음 | 10,275건 → 25건 (2026-08-17) | 99MB 를 `write_text()` 로 직접 덮어씀. 트랜잭션도 백업도 없음 |
| 레코드 시각 없음 | `crawled_at` 필드 자체가 없음 | 개별 공고가 언제 것인지 알 수 없다 |

## 설계의 축 4개

### 1. 표기와 정체성을 분리한다 — `company` / `company_alias`

회사를 문자열로 식별하는 한 표기 변형은 코드로 못 막는다. `company.norm`(법인격·공백 제거한
정규화 결과)이 UNIQUE 키가 되고, 크롤이 들고 온 표기는 전부 `company_alias` 행이 된다.
정규화가 놓친 변형은 `company_alias` 에 `manual=true` 로 한 줄 이어붙이면 그때부터 같은 회사다.
나중에 통합할 일이 생기면 행을 지우지 않고 `company.merged_into` 로 넘긴다 — 옛 슬러그 주소를
리다이렉트로 살릴 수 있다.

`company.slug` 는 `companySlug.js` 가 만드는 값을 그대로 넣는다. **한 번 정하면 안 바뀐다**
(바뀌면 색인된 `/companies/<slug>` 가 통째로 404).

### 2. 공고의 정체성은 URL 이다 — `job`

```sql
CONSTRAINT job_url_uniq      UNIQUE (url),
CONSTRAINT job_site_pid_uniq UNIQUE (site, pid),
CONSTRAINT job_title_not_blank CHECK (btrim(title) <> ''),
company_id bigint NOT NULL REFERENCES company(id)
```

이 네 줄이 위 표의 1~5행을 전부 막는다. 회사명 없는 공고 492건은 **들어오다가 거부된다** —
지금처럼 조용히 통과해 중복 검사만 건너뛰는 일이 없다. 크롤이 회사명을 못 뽑았으면
그건 데이터가 아니라 크롤러 버그이고, 지금은 그걸 알 방법이 없었다.

### 3. 상태는 저장하지 않는다 — `job_state` 뷰 ★

가장 중요한 결정이다. `status` 는 컬럼이 아니라 뷰다.

```sql
WHEN o.value IS NOT NULL              THEN 사람이 정한 값       -- override
WHEN c.closed                         THEN 'closed'            -- 사이트에 물어본 원장
WHEN c.deadline_on < CURRENT_DATE     THEN 'closed'
WHEN j.always_open                    THEN 'active'            -- 상시채용
WHEN j.deadline_on < CURRENT_DATE     THEN 'closed'
ELSE                                       'active'            -- 모름
```

우선순위는 `pipeline/job_status.py` 의 규칙 그대로다. 달라진 건 **계산 시점**뿐이다.
저장하지 않으면 낡을 수 없다 — 2,373건 문제가 구조적으로 사라진다. `dday` 도 마찬가지로
`deadline_on - CURRENT_DATE` 로 그 자리에서 계산한다. 지금 화면의 `D-4` 는 크롤 시점 문자열이라
마감일 8/23 인 공고가 며칠 뒤에도 D-4 로 보인다.

덤으로 `status_source` 가 나온다. `'unknown'` 은 "모집중"이 아니라 **"마감을 알 방법이 없어
열어둔 것"** 이다. 지금 active 의 59%가 여기다. 화면에서 `모집중(확인 8/30)` 과 `모집중(미확인)`
을 갈라 보여줄 수 있고, 이건 정합성이 아니라 정직함의 문제다.

### 4. 이력은 덮어쓰지 않고 쌓는다 — `job_closure_check` / `job_event`

원장을 "site:pid → 최신 결과" 맵으로 덮어쓰면 파서를 고쳤을 때 재해석할 재료가 없다.
확인할 때마다 한 행을 남기고(`checked_at`, `closed`, `evidence`), 최신 1건은
`job_closure_latest` 뷰가 뽑는다. `job_recheck_queue` 뷰가 close_check 의 대기열이 된다
(원장 없음 → 7일 지난 것 순). `job_event` 는 appeared/closed/reopened 를 append-only 로 남겨
`reposts.json` 을 대체한다 — 전량 스냅샷이 아니라 **변화만** 기록하므로 17,584건 × 사이클이
쌓이지 않는다.

## 벡터 연동 — sqlite-vec 를 pgvector 로 들인다

지금 `semantic.db` 는 별도 SQLite 파일이다: `documents`(kind=job|post) + `vec_documents`
(sqlite-vec) + `fts_documents`(FTS5). 공고와 **다른 파일**에 있어서 색인이 마감 여부를 알 수
없고, 그래서 `meta` JSON 에 status 를 베껴 담는다. 그 사본은 공고가 마감돼도 다음 ingest
전까지 낡은 채로 남는다 — 검색 결과에 마감 공고가 뜨는 경로다.

새 구조에서 임베딩은 `job` 의 자식이다.

| 지금 | 새 스키마 |
|---|---|
| `documents` (kind='job') | `job` 본체 (별도 사본 없음) |
| `documents` (kind='post') | `post` |
| `documents.meta` 의 status 사본 | 없음 — `JOIN job_state` |
| `vec_documents` (sqlite-vec) | `job_embedding.embedding vector(1024)` + HNSW |
| `fts_documents` (FTS5) | `job.search_tsv` 생성 컬럼 + GIN |
| `content_hash` / `embedded_hash` | `job.content_hash` vs `job_embedding.content_hash` |
| 임베딩 대기 조회 | `job_embed_pending` 뷰 |
| `similar_*.json` | `job_similar` / `post_similar` 테이블 |
| search.py 의 파이썬 RRF | `search_jobs(q, q_embedding, n, include_closed)` 함수 |

증분 임베딩 규칙은 그대로다 — 두 해시가 어긋나면 재임베딩. 달라지는 건:

- **마감 제외가 조인 조건이 된다.** `meta.status` 사본을 유지할 필요가 없다. 마감 공고는
  색인에 남고(지난 공고 통계·유사도의 재료), 검색에서 뺄 때만 `WHERE s.status='active'` 를 건다.
  `--include-closed` 는 함수 인자 하나가 된다.
- **RRF 가 SQL 안으로 들어간다.** `search_jobs()` 가 FTS 랭킹과 벡터 랭킹을 `FULL OUTER JOIN`
  으로 합쳐 `1/(k+rank)` 를 더한다. 파이썬은 질의 임베딩을 만들어 넘기는 일만 한다.
- **임베딩이 공고와 같은 트랜잭션에 있다.** 공고를 지우면 `ON DELETE CASCADE` 로 벡터도 간다.
  지금은 두 파일이 따로라 고아 벡터가 남는다.

**용량 (17,067건을 실제로 넣고 잰 값).** 벡터 1개가 4KB 라 TOAST 임계(2KB)를 넘어
전부 out-of-line 으로 저장된다 — 그래서 힙은 거의 비어 있고 TOAST 가 본체다.

| | 크기 |
|---|---|
| `job_embedding` 힙 | 1.5 MB |
| 〃 TOAST(벡터 본체) | 91 MB |
| `job_embedding_hnsw_idx` | 115 MB |
| DB 전체(공고 본문 포함) | 427 MB |

HNSW 인덱스가 벡터 본체보다 크다. 8GB M1 에서 메모리에 들지만 여유가 많지는 않다.
빠듯해지면 `ef_construction` 을 낮추거나 IVFFlat 으로 바꾼다(정확도를 조금 내주고
인덱스가 훨씬 작아진다).

**⚠️ 벡터를 CTE 로 감싸지 말 것.** 이웃 검색의 `LATERAL` 안에서는 `job_embedding` 을
직접 읽어야 한다. 편하다고 `WITH pool AS (SELECT ... FROM job_embedding ...)` 로 한 번
싸면 Postgres 가 CTE 를 실체화하면서 HNSW 인덱스가 사라지고 17,067 × 17,067 완전탐색이
된다. 실측 차이가 **단일 질의 1.7ms 대 전체 251초** 였다. 마감 필터·회사 상한은 이웃을
뽑은 **뒤에** 걸어야 한다 — `store/similar.py` 상단에 같은 경고를 적어 뒀다.

한국어 검색: Postgres 기본 파서는 형태소를 모른다. `to_tsvector('simple', ...)` 로 토큰만
쪼개 기술명·회사명 같은 고유명사를 잡고, 한글 부분일치("백엔드", "재택")는 `pg_trgm` GIN 이
맡는다. 이 조합으로 부족하면 `pg_bigm` 을 추가로 올린다(별도 컴파일 필요).

## 파일 → 테이블 대응

| 지금 | 새 위치 | 비고 |
|---|---|---|
| `all_jobs_enriched.json` | `job` + `company` + `job_tech` | 파일은 `v_job` 의 덤프로 강등 |
| `job_closures.json` | `job_closure_check` | 맵 → append-only 이력 |
| `overrides.json` | `job_override` | `site:pid` 키 → 필드 단위 |
| `closed_<label>.json` | 없음 — `job_state` 가 계산 | 아카이브가 따로 필요 없다 |
| `health/history.jsonl` | `crawl_run` + `crawl_run_site` | |
| `reposts.json` | `job_event` | |
| `company_stacks.json` (15MB) | `mv_company_stack` | `REFRESH ... CONCURRENTLY` |
| `trends.json`, `trends_reports/*.md` | `tech_daily` | |
| `similar_jobs.json`, `similar_posts.json` | `job_similar`, `post_similar` | |
| `tech_relations.json` | `job_tech` 조인 질의 | 미리 굳힐 이유가 없다 |
| `semantic.db` | `job_embedding`, `post_embedding` | 위 표 참조 |
| `guide/`, `reveng/`, `study/` **본문** | **파일 그대로** | 사람이 쓴 글, git 리뷰 대상 |
| `validate.py --gaps` | `guide_gap`, `study_gap` 뷰 | |

`jd-viewer/public/*.json` 은 없어지지 않는다. **정본에서 뽑아내는 빌드 산출물로 강등**될 뿐이다
— 뷰어는 지금처럼 정적 JSON 을 fetch 하면 되고, nginx read-only 볼륨 구조도 그대로다.

## 쓰기 경로 — upsert 하나

크롤러가 공고 1건을 넣는 흐름. `aggregate` 의 중복 제거 루프를 대체한다.

```sql
-- 1. 회사: 표기를 alias 로 흡수하고 norm 으로 식별한다
INSERT INTO company (norm, slug, display_name)
VALUES ($norm, $slug, $raw_name)
ON CONFLICT (norm) DO UPDATE SET last_seen_at = now()
RETURNING id;

INSERT INTO company_alias (raw, company_id)
VALUES ($raw_name, $company_id)
ON CONFLICT (raw) DO UPDATE SET n_seen = company_alias.n_seen + 1;

-- 2. 공고: URL 이 키다. 이미 있으면 본문만 갱신하고 first_seen_at 은 지킨다
INSERT INTO job (site, pid, url, company_id, title, ..., content_hash)
VALUES (...)
ON CONFLICT (url) DO UPDATE SET
    title           = EXCLUDED.title,
    qualifications  = EXCLUDED.qualifications,
    deadline_text   = EXCLUDED.deadline_text,
    deadline_on     = EXCLUDED.deadline_on,
    always_open     = EXCLUDED.always_open,
    content_hash    = EXCLUDED.content_hash,
    last_seen_at    = now(),
    last_crawled_at = now(),
    gone_at         = NULL            -- 다시 나타났다
RETURNING id, (xmax = 0) AS inserted; -- inserted=true 면 job_event('appeared')
```

한 사이클 전체가 하나의 트랜잭션이다. **10,275건 → 25건 사고가 구조적으로 불가능해진다** —
부분 실패는 롤백이고, "건수가 확 줄면 멈춘다"는 `refresh-data.sh` 의 가드는 트랜잭션 안의
`SELECT count(*)` 비교 한 줄이 된다.

목록에서 사라진 공고는 지우지 않는다. `gone_at = now()` 만 찍고 `close_check` 가 원본에
물어보게 둔다 — **사라짐 ≠ 마감**이기 때문이다(페이지네이션 실패로도 사라진다).

## 구현 상태

| 단계 | 모듈 | 상태 |
|---|---|---|
| 스키마 | `db/schema.sql` | ✅ 적용·검증 (`db/smoke_test.sql`) |
| 1. 백필 | `catch_capture/store/backfill.py` | ✅ 17,067건 적재 완료 |
| 3. 정본 교체 | `catch_capture/store/export.py` | ✅ `--check` 로 기존 JSON 과 대조됨 |
| 2. 이중 쓰기 | `catch_capture/store/ingest_crawl.py` | ✅ aggregate 에 연결·4개 시나리오 검증 |
| 4. 벡터 이관 | `catch_capture/store/migrate_vectors.py` | ⚠️ 코드만 — 맥에서 실행 필요 |
| 임베딩 | `catch_capture/store/embed.py` | ⚠️ 코드만 — Ollama 필요 |
| 유사 공고 | `catch_capture/store/similar.py` | ✅ SQL 검증(합성 벡터 17k) |
| 검색 | `catch_capture/store/search.py` | ✅ FTS·RRF·마감제외 검증 |

| 블로그 글 적재 | `catch_capture/store/ingest_posts.py` | ✅ 1,063건 (회사 연결 282) |

공통 기반: `store/conn.py`(DSN) · `store/slug.py`(주소 슬러그) · `store/upsert.py`(쓰기 경로).
임베딩 입력 텍스트는 `semantic/text.py` 로 떼어내 SQLite·PostgreSQL 두 경로가 공유한다.

### 검사 — `python -m store.selftest`

**별도의 시험용 DB**(`jobseeker_test`)를 만들어 거기서만 돌고 끝나면 지운다. 운영
데이터는 건드리지 않는다. Ollama 없이 돈다 — 벡터는 유사도를 손으로 지정한 결정적
값을 넣고, Ollama 는 HTTP 호출(`_post`)만 대역으로 바꿔 `embed_batch` 의 정규화·
차원 검사는 실제 코드가 돌게 한다.

47개 항목, 12개 절: 회사 표기 흡수 · 기술 슬러그 충돌 · 공고 제약 6종 거부 ·
`job_state` 우선순위 · `v_job` 필드 · 유사도 밴드(MIN/DUP/회사상한) ·
`similar_jobs.json` 형식(`useSimilar.ts` 와 대조) · 검색과 마감 제외 ·
증분 임베딩 대기열 · 이중 쓰기 6종 · 임베딩 배치 · sqlite-vec→pgvector 이관.

이 파일이 있는 이유는 이관 중에 나온 결함이 **전부 오류를 안 내고 값만 틀리는
종류**였기 때문이다(아래 표). 그런 건 눈으로 못 잡는다.

### 백필 실측 (2026-09-07, 8/21자 스냅샷 기준)

```
입력 17,584건 → 적재 17,067건
  회사명 없음 492건 · 제목 없음 25건  ← 제약에 걸려 거부(지금까지는 조용히 통과)
  회사 표기 8,412개 → 회사 6,790곳   ← 표기 1,622개가 기존 회사로 흡수
  기술 연결 74,590건 · 기술 787종(노이즈 18종)
소요 3분 6초
```

`store.export --check` 로 기존 JSON 과 대조한 결과:

```
기존에만 있는 공고 517건 (= 492 + 25, 제약 위반)
DB 에만 있는 공고 0건
status 가 달라진 공고: active → closed 1,842건 (전부 status_source=deadline)
```

1,842건은 파일이 구워진 뒤 마감일이 지난 공고다. 지금까지 화면에 '모집중'으로 남아
있던 것이고, 이제는 파일을 다시 뽑을 때마다 그 시점 기준으로 다시 판정된다.

## 이관 계획

DB 를 붙이는 동안 사이트가 멈추면 안 되므로 4단계로 나눈다.

**1단계 — 스키마 + 백필 (읽기 없음).**
Postgres 를 띄우고 `schema.sql` 적용. `all_jobs_enriched.json` + `job_closures.json` +
`overrides.json` 을 읽어 넣는 일회성 스크립트를 만든다. 여기서 회사 1,383 그룹과 중복
1,150건이 실제로 합쳐진다. `first_seen_at` 은 `reposts.json` 의 이력에서 최대한 복원하고,
없으면 백필 시각으로 둔다. **이 단계는 기존 파이프라인을 건드리지 않는다** — 결과만 비교한다.

**2단계 — 이중 쓰기.** `pipeline/aggregate.py` 가 매 사이클 `store.ingest_crawl` 을 부른다.
**중복 제거를 거치기 전** 목록을 넘기므로 DB 는 URL 로 식별하고, JSON 쪽은 지금까지처럼
`(회사명, 제목)` 으로 줄인다 — 두 결과를 며칠 나란히 두고 `store.export --check` 로
diff 해서 차이가 전부 "고쳐진 것"인지 확인한다.

DB 가 꺼져 있거나 느려도 사이클은 그대로 간다(`[db] 이중 쓰기 건너뜀` 한 줄만 찍힌다).
끄려면 `DB_DUAL_WRITE=0`.

**사이트별 급감 가드가 이 단계의 핵심 안전장치다.** 이번 사이클에 본 건수가 DB 에
살아 있는 건수의 절반(`DB_GONE_MIN_RATIO`)보다 적으면 그 사이트의 `gone_at` 처리를
통째로 건너뛴다. 크롤이 차단당하거나 페이지네이션이 끊겼을 뿐인데 멀쩡한 공고
수천 건을 "사라졌다"고 찍으면 close_check 가 헛돌고 화면에서도 근거 없이 사라진다.
실제로 4건만 들어온 시험에서 `wanted(4/3121)` 로 보류가 걸렸다.

검증한 시나리오(remote 24건):

| | 결과 |
|---|---|
| 전량 재투입 | 신규 0 · 사라짐 0 (멱등) |
| 3건 누락 | 그 3건만 `gone_at` + `disappeared` 이벤트 |
| 5건만 옴(부분 크롤) | 급감 가드로 **보류** — 아무것도 안 지움 |
| 전량 복귀 | 3건 `reopened` |

전 구간에서 다른 사이트는 건드리지 않았다. 성능은 17,067건 재투입 기준 54초다
(회사·기술 id 를 실행 내 캐시하고, `content_hash` 가 그대로면 기술 연결을 다시
맞추지 않는다 — 그 둘이 없으면 6분 20초였다).

**3단계 — 정본 교체.** `enrich_jobs.py` 를 "DB 에서 `v_job` 을 덤프하는" 스크립트로 바꾼다.
뷰어는 파일명도 형식도 그대로라 코드 변경이 거의 없다. 이 시점에 `status`/`dday` 가
읽는 시점 계산으로 바뀐다.

**4단계 — 벡터 이관.** `semantic.db` 의 임베딩을 `job_embedding` 으로 복사한다
(재임베딩 불필요 — 같은 모델·같은 차원이면 벡터를 그대로 옮기면 된다. `documents.url` 로
`job.url` 에 조인한다). `search.py` 를 `search_jobs()` 호출로 바꾸고 SQLite 를 내린다.

되돌리기: 3단계까지는 JSON 이 계속 살아 있으므로 언제든 스크립트만 되돌리면 된다.

## 띄우기

```bash
docker compose -f db/docker-compose.db.yml up -d
export JOBSEEKER_DSN="postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker"
psql "$JOBSEEKER_DSN" -f db/schema.sql
```

포트는 5433 을 쓴다 — 로컬에 다른 Postgres 가 있어도 안 겹치게. 이 머신은 8GB M1 이고
Playwright 크롤과 Ollama 임베딩이 이미 메모리를 다투므로 `shared_buffers` 를 256MB 로 묶었다
(compose 파일 참조). 17,584행짜리 DB 라 그 이상은 필요 없다.

## 검증하며 고친 것 (프론트엔드 대조)

`store.export` 결과를 실제로 뷰어에 끼우고 Playwright 로 5개 화면 + 공고 상세를
렌더해 본 결과, 이쪽에서 잡은 결함들이다. 전부 조용히 틀리는 종류라 적어 둔다.

| 결함 | 증상 | 고친 곳 |
|---|---|---|
| 기술 슬러그가 한글을 지운 뒤 만들어짐 | `Windows 서버`→`windows`, `QA 엔지니어링`→`qa` 로 **다른 기술이 합쳐짐**(26·15건) | `store/slug.py` — 지우기 전에 로마자로 |
| 마감일을 백필 시점에 재파싱 | `D-4` 가 오늘 기준이 돼 끝난 공고 899건이 미래 마감으로 되살아남 | `store/backfill.py`·`ingest_crawl.py` — 계산된 값 우선 |
| `dday`·`education`·`employment` 누락 | `build_calendar.py`·`build_role_insights.py` 가 실제로 읽는 필드 | `store/export.py` — `dday` 는 재계산해서 |
| `similar_*.json` 형식 불일치 | 뷰어는 `docs`+`similar`(sha1 id) 를 읽는데 `site-pid` 키로 씀 → **오류 없이 추천만 안 뜸** | `store/similar.py` |
| `㈜` 가 대표표기로 뽑힘 | 뷰어의 `normalizeCompany` 가 `(주)` 만 지워서 그 회사 브리핑·로고가 사라짐 | `store/upsert.py`(NFKC 출력) + `companyMark.ts`(NFKC 입력) |

마지막 것은 원래 뷰어에 있던 결함이고, 이쪽 변경이 드러냈다. 양쪽을 다 고쳐서
브리핑이 붙는 공고가 588 → 599건(+11)이 됐다. **회사명 정규화 규칙이 이 저장소에
네 벌 있다** — `aggregate._norm_key`, `classifier._norm_company`(DB 기준),
`companySlug.js`, `companyMark.normalizeCompany`. 하나로 모으는 것이 다음 숙제다.

## 아직 안 정한 것

- **`career_min` 파싱 규칙.** `career_text` 분포는 `경력무관`(2,548) `경력3년↑`(1,380)
  `신입·경력`(1,261) 순이라 대부분 규칙으로 뽑힌다. `경력무관`/`신입·경력` 을
  `career_min=0, accepts_entry=true` 로 볼지 `NULL` 로 둘지는 화면 필터가 뭘 원하는지에 달렸다.
- **`employment` / `education`.** 지금 데이터는 파싱이 깨져 있다 — `employment` 값에
  `[아이모비] 웹 풀스택 개발자(정규직/신입)` 같은 **공고 제목이 통째로** 들어가 있고,
  채워진 것도 3,398건(19%)뿐이다. ENUM 으로 조인 것은 그 쓰레기가 INSERT 에서 걸리게 하려는
  것이다. jobkorea txt 파서를 먼저 고쳐야 한다.
- **`tech` 초기 적재.** 850개 토큰 중 `dev`, `mobile` 같은 비-기술을 `is_noise` 로 찍는 작업이
  한 번 필요하다. `crawlers/tech_taxonomy.py` 가 이미 분류를 들고 있으니 거기서 시작한다.
- **개인 이력(`admin/`, 8910).** LAN 전용 비공개 데이터라 이 스키마에 넣지 않았다. 같은
  Postgres 의 별도 스키마(`CREATE SCHEMA admin`)로 두면 지원 이력 ↔ 공고 조인이 가능해진다.
