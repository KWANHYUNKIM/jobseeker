-- 스키마가 "막겠다고 한 것"을 실제로 막는지 확인한다.
-- 실행: docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -f - < db/smoke_test.sql
--
-- 각 블록은 실패해야 정상인 INSERT 를 일부러 던진다. 통과하면 그게 버그다.
\set ON_ERROR_STOP off
\timing off

-- ── 준비 ────────────────────────────────────────────────────────────
INSERT INTO company (norm, slug, display_name) VALUES
    ('클로봇', 'clobot', '클로봇'),
    ('메가존클라우드', 'megazonecloud', '메가존클라우드(주)');

-- 표기 변형은 전부 alias 로 흡수된다 — 이게 1,383 그룹을 합치는 방식이다
INSERT INTO company_alias (raw, company_id) VALUES
    ('클로봇',        (SELECT id FROM company WHERE norm='클로봇')),
    ('(주)클로봇',     (SELECT id FROM company WHERE norm='클로봇')),
    ('주식회사 클로봇', (SELECT id FROM company WHERE norm='클로봇'));

INSERT INTO tech (slug, name, kind) VALUES ('react','React','library'), ('dev','dev','noise');
UPDATE tech SET is_noise = true WHERE slug = 'dev';

INSERT INTO job (site, pid, url, company_id, title, deadline_on, content_hash) VALUES
    ('wanted','1001','https://www.wanted.co.kr/wd/1001', (SELECT id FROM company WHERE norm='클로봇'), '백엔드 개발자', NULL, 'h1'),
    ('saramin','2002','https://www.saramin.co.kr/x/2002', (SELECT id FROM company WHERE norm='클로봇'), '백엔드 개발자', CURRENT_DATE - 5, 'h2'),
    ('jumpit','3003','https://www.jumpit.co.kr/position/3003', (SELECT id FROM company WHERE norm='메가존클라우드'), 'DevOps 엔지니어', CURRENT_DATE + 10, 'h3');

INSERT INTO job_tech (job_id, tech_id)
SELECT j.id, t.id FROM job j, tech t WHERE j.pid='1001' AND t.slug IN ('react','dev');

\echo '───── 1. 같은 URL 두 번 → 막혀야 한다'
INSERT INTO job (site,pid,url,company_id,title,content_hash)
VALUES ('wanted','9999','https://www.wanted.co.kr/wd/1001',(SELECT id FROM company LIMIT 1),'중복 URL','h');

\echo '───── 2. 같은 (site,pid) → 막혀야 한다'
INSERT INTO job (site,pid,url,company_id,title,content_hash)
VALUES ('wanted','1001','https://www.wanted.co.kr/wd/other',(SELECT id FROM company LIMIT 1),'중복 site+pid','h');

\echo '───── 3. 제목 없음 → 막혀야 한다 (지금 데이터의 25건)'
INSERT INTO job (site,pid,url,company_id,title,content_hash)
VALUES ('jobkorea','4004','https://www.jobkorea.co.kr/4004',(SELECT id FROM company LIMIT 1),'   ','h');

\echo '───── 4. 회사 없음 → 막혀야 한다 (지금 데이터의 492건)'
INSERT INTO job (site,pid,url,company_id,title,content_hash)
VALUES ('jobkorea','4005','https://www.jobkorea.co.kr/4005',NULL,'회사 없는 공고','h');

\echo '───── 5. 미래로 튄 마감일(옛 연도 파싱 버그) → 막혀야 한다'
INSERT INTO job (site,pid,url,company_id,title,deadline_on,content_hash)
VALUES ('saramin','4006','https://www.saramin.co.kr/x/4006',(SELECT id FROM company LIMIT 1),'파싱 사고',DATE '2999-01-01','h');

\echo '───── 6. status 오타 override → 막혀야 한다'
INSERT INTO job_override (job_id, field, value)
VALUES ((SELECT id FROM job WHERE pid='1001'), 'status', '"actve"'::jsonb);

\set ON_ERROR_STOP on

\echo ''
\echo '═════ 7. status 는 지금 계산된다 (저장값이 아니다)'
SELECT j.site, j.pid, s.status, s.status_source, s.effective_deadline, s.dday
  FROM job j JOIN job_state s ON s.job_id = j.id ORDER BY j.pid;

\echo ''
\echo '═════ 8. 원장이 마감일 텍스트를 이긴다 — wanted(마감일 없음)를 닫아본다'
INSERT INTO job_closure_check (job_id, closed, evidence)
VALUES ((SELECT id FROM job WHERE pid='1001'), true, '채용이 마감되었습니다');
SELECT j.pid, s.status, s.status_source FROM job j JOIN job_state s ON s.job_id=j.id WHERE j.pid='1001';

\echo ''
\echo '═════ 9. 사람이 정한 값이 원장을 이긴다'
INSERT INTO job_override (job_id, field, value)
VALUES ((SELECT id FROM job WHERE pid='1001'), 'status', '"active"'::jsonb);
SELECT j.pid, s.status, s.status_source FROM job j JOIN job_state s ON s.job_id=j.id WHERE j.pid='1001';

\echo ''
\echo '═════ 10. v_job — 뷰어가 읽는 모양 (noise 기술은 빠진다)'
SELECT job_key, company, company_slug, title, status, status_source, dday, tech_stack FROM v_job ORDER BY pid;

\echo ''
\echo '═════ 11. 벡터 — 임베딩 대기열 → 삽입 → 코사인 이웃'
SELECT count(*) AS pending FROM job_embed_pending;
INSERT INTO job_embedding (job_id, model, content_hash, embedding)
SELECT j.id, 'bge-m3', j.content_hash,
       (SELECT array_agg(CASE WHEN i = (j.id % 1024) + 1 THEN 1.0 ELSE 0.0 END ORDER BY i)
          FROM generate_series(1,1024) i)::vector
  FROM job j;
SELECT count(*) AS pending_after FROM job_embed_pending;

SELECT a.job_id, b.job_id AS neighbor, round((1 - (a.embedding <=> b.embedding))::numeric, 4) AS cosine
  FROM job_embedding a JOIN job_embedding b ON b.job_id <> a.job_id
 ORDER BY a.job_id, a.embedding <=> b.embedding LIMIT 3;

\echo ''
\echo '═════ 12. 하이브리드 검색 — 마감 공고는 기본으로 빠진다'
SELECT * FROM search_jobs('백엔드', (SELECT embedding FROM job_embedding LIMIT 1), 10, false);
\echo '   (include_closed => true 로 열면)'
SELECT count(*) AS with_closed FROM search_jobs('백엔드', (SELECT embedding FROM job_embedding LIMIT 1), 10, true);

\echo ''
\echo '═════ 13. 엔진 대기열 뷰'
SELECT * FROM guide_gap;

\echo ''
\echo '═════ 14. 집계 갱신'
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_company_stack;
SELECT display_name, tech, n_jobs FROM mv_company_stack ORDER BY n_jobs DESC;
