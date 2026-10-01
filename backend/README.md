# backend — 뷰어 API (8771)

정본 DB(PostgreSQL)를 읽어 뷰어(`jd-viewer`)에 답한다. **읽기만 한다** — DB 에 쓰는
쪽은 크롤 파이프라인(`catch_capture`)이다.

```
파이프라인(catch_capture) ──쓰기──▶ PostgreSQL ◀──읽기── backend(8771) ◀── 뷰어(/api/)
```

## 폴더 규칙

```
backend/
├─ app/
│  ├─ main.py              앱 생성·라우터 등록·실행(python -m app.main)
│  ├─ core/                config(환경변수) · exceptions(404/400/503 처리)
│  ├─ db/session.py        DB 연결
│  ├─ features/<기능>/     router(경로) → service(규칙) → repository(SQL) · schemas(요청 형식)
│  └─ utils/               캐시·문자열 같은 공통 보조 함수
└─ tests/features/<기능>/  기능별 테스트(conftest.py 가 DB 없으면 db 마커를 건너뛴다)
```

- 새 엔드포인트는 `features/<기능>/` 하나를 만들고 `main.py` 의 `ROUTERS` 에 더한다.
- SQL 은 `repository.py` 에만 둔다. `router.py` 는 파라미터 검증과 호출만 한다.
- ORM 은 쓰지 않는다(`models.py`·`db/base.py` 가 없는 이유). 스키마의 원본은 저장소 루트의
  `db/schema.sql` + `db/migrations/` 이다 — 파이프라인과 같이 쓰므로 여기로 옮기지 않았다.
- `features/jobs/mapping.py` 는 **공고 한 건이 뷰어에 어떻게 보이는가의 단일 소스**다.
  파이프라인의 파일 내보내기(`store/jobs/export.py`)가 이걸 import 한다. 반대 방향
  (backend → catch_capture) import 는 하지 않는다.

## 실행·테스트

```bash
cd backend
python -m app.main                       # 127.0.0.1:8771, 문서 /api/docs
python -m pytest                         # DB 없으면 db 테스트는 건너뛴다
JOBSEEKER_DSN=postgresql://...  python -m pytest
```

운영 맥은 크롤러와 같은 venv(`catch_capture/.venv`)로 launchd 가 띄운다
(`deploy/setup-dashboards.sh`, 작업 폴더 `backend/`). 환경변수는 `.env.example`.

DB 에 못 붙어도 서버는 죽지 않는다 — `/api/*` 가 503 을 돌려주고 뷰어는 정적 파일로
물러선다. DB 가 살아나면 다시 등록하지 않아도 그대로 답한다.
