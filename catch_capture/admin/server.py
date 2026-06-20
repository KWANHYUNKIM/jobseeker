"""관리자 백엔드 — 이력서 자동화(AX) 로컬 도구.

보안 핵심:
  * 오직 127.0.0.1 에만 바인딩한다. 0.0.0.0 옵션을 두지 않는다(공개 금지).
  * 공개 뷰어/ngrok 경로와 완전히 분리. 이 서버는 인터넷에 노출되지 않는다.

실행:  python -m admin.server         (포트: 환경변수 ADMIN_PORT, 기본 8910)
접속:  http://127.0.0.1:8910
"""
from __future__ import annotations

import datetime
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import domains, jobs, match, store

HOST = "127.0.0.1"  # 고정 — 절대 외부 바인딩 금지
PORT = int(os.environ.get("ADMIN_PORT", "8910"))
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class Handler(BaseHTTPRequestHandler):
    server_version = "JobseekerAdmin"

    # ── 응답 헬퍼 ────────────────────────────────────────────
    def _json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg: str, status: int = 400) -> None:
        self._json({"error": msg}, status)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def log_message(self, *args) -> None:  # 조용히
        pass

    # ── 정적 파일 ────────────────────────────────────────────
    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        rel = os.path.normpath(rel).lstrip("/.")
        target = STATIC_DIR / rel
        if not target.is_file():
            target = STATIC_DIR / "index.html"  # SPA fallback
        if not target.is_file():
            self._err("not found", 404)
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ── 라우팅 ───────────────────────────────────────────────
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self._json({"ok": True, "ai": store.get_api_key() != ""})
            elif path == "/api/jobs":
                q = (qs.get("q", [""])[0])
                limit = min(int(qs.get("limit", ["50"])[0] or 50), 200)
                offset = int(qs.get("offset", ["0"])[0] or 0)
                self._json(jobs.search(q, limit, offset))
            elif path == "/api/fit":
                self._fit(qs)
            elif path == "/api/job":
                key = qs.get("key", [""])[0]
                job = jobs.get(key)
                self._json(job) if job else self._err("job not found", 404)
            elif path == "/api/profile":
                self._json(store.get_profile())
            elif path == "/api/applications":
                self._json({"items": store.list_applications(),
                            "statuses": store.STATUSES})
            elif path == "/api/captures":
                self._json({"items": store.list_captures()})
            elif path == "/api/watchlist":
                self._json({"items": store.list_watchlist()})
            elif path == "/api/resumes":
                self._json({"items": store.list_resumes()})
            elif path == "/api/resume":
                rid = qs.get("id", [""])[0]
                r = store.get_resume(rid)
                self._json(r) if r else self._err("resume not found", 404)
            elif path.startswith("/api/"):
                self._err("unknown endpoint", 404)
            else:
                self._serve_static(path)
        except Exception as e:  # noqa: BLE001 — 로컬 도구, 에러를 JSON으로
            self._err(f"server error: {e}", 500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._body()
        try:
            if path == "/api/profile":
                self._json(store.save_profile(body, _now()))
            elif path == "/api/applications":
                self._json(store.add_application(body, _now()), 201)
            elif path == "/api/settings/apikey":
                key = str(body.get("key", "")).strip()
                if not key:
                    return self._err("key required")
                store.save_api_key(key)
                self._json({"ok": True})
            elif path == "/api/captures":
                self._json(store.add_capture(body, _now()), 201)
            elif path == "/api/watchlist":
                self._add_watch(body)
            elif path == "/api/watchlist/check":
                self._check_watch(body)
            elif path == "/api/answer":
                self._ai_answer(body)
            elif path == "/api/analyze":
                self._ai_analyze(body)
            elif path == "/api/generate":
                self._ai_generate(body)
            else:
                self._err("unknown endpoint", 404)
        except Exception as e:  # noqa: BLE001
            self._err(f"server error: {e}", 500)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        body = self._body()
        try:
            if parsed.path == "/api/applications":
                app_id = parse_qs(parsed.query).get("id", [""])[0]
                rec = store.update_application(app_id, body, _now())
                self._json(rec) if rec else self._err("not found", 404)
            else:
                self._err("unknown endpoint", 404)
        except Exception as e:  # noqa: BLE001
            self._err(f"server error: {e}", 500)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/applications":
                app_id = parse_qs(parsed.query).get("id", [""])[0]
                ok = store.delete_application(app_id)
                self._json({"ok": ok}) if ok else self._err("not found", 404)
            elif parsed.path == "/api/captures":
                cap_id = parse_qs(parsed.query).get("id", [""])[0]
                ok = store.delete_capture(cap_id)
                self._json({"ok": ok}) if ok else self._err("not found", 404)
            elif parsed.path == "/api/watchlist":
                wid = parse_qs(parsed.query).get("id", [""])[0]
                ok = store.delete_watch(wid)
                self._json({"ok": ok}) if ok else self._err("not found", 404)
            else:
                self._err("unknown endpoint", 404)
        except Exception as e:  # noqa: BLE001
            self._err(f"server error: {e}", 500)

    # ── 자동 적합도 분석 (규칙 기반, 전체 랭킹) ──────────────
    def _fit(self, qs: dict) -> None:
        profile = store.get_profile()
        have = match.profile_terms(profile)
        if not have:
            return self._json({"items": [], "facets": {"domains": []},
                               "profile_terms": [], "scanned": 0,
                               "warning": "프로필에 인식된 기술이 없습니다. 사실 프로필의 스킬/경력을 먼저 채우세요."})
        q = (qs.get("q", [""])[0]).strip().lower()
        terms = q.split()
        min_score = int(qs.get("min_score", ["0"])[0] or 0)
        limit = min(int(qs.get("limit", ["50"])[0] or 50), 200)
        domain_filter = qs.get("domain", [""])[0]

        scored = []
        for j in jobs.all_jobs():
            if not jobs.matches_query(j, terms):
                continue
            s = match.score(have, j)
            if s["score"] < min_score:
                continue
            doms = domains.classify(j)
            if domain_filter and domain_filter not in doms:
                continue
            scored.append((s, doms, j))

        # 도메인 facet(필터 결과 기준)
        facet: dict[str, int] = {}
        for _, doms, _ in scored:
            for d in doms:
                facet[d] = facet.get(d, 0) + 1
        facets = sorted(({"name": k, "count": v} for k, v in facet.items()),
                        key=lambda x: -x["count"])

        scored.sort(key=lambda t: (t[0]["score"], len(t[0]["matched"])), reverse=True)
        items = []
        for s, doms, j in scored[:limit]:
            items.append({
                "key": jobs.job_key(j), "company": j.get("company"), "title": j.get("title"),
                "url": j.get("url"), "career": j.get("career"), "dday": j.get("dday"),
                "score": s["score"], "matched": s["matched"], "missing": s["missing"],
                "low_confidence": s["low_confidence"], "domains": doms,
                "main_tasks": str(j.get("main_tasks") or "")[:800],
                "qualifications": str(j.get("qualifications") or "")[:800],
                "preferences": str(j.get("preferences") or "")[:600],
            })
        self._json({"items": items, "facets": facets,
                    "profile_terms": sorted(have), "scanned": len(scored)})

    # ── 재공고 추적 ──────────────────────────────────────────
    def _add_watch(self, body: dict) -> None:
        snapshot = None
        company = str(body.get("company", "")).strip()
        if body.get("key"):
            job = jobs.get(body["key"])
            if job:
                snapshot = {k: (str(job.get(k, ""))[:1500] if k in ("qualifications", "preferences") else job.get(k))
                            for k in ("key", "title", "url", "company", "tech_stack", "qualifications", "preferences")}
                snapshot["key"] = jobs.job_key(job)
                if not company:
                    company = str(job.get("company", "")).strip()
        body = dict(body)
        body["company"] = company
        self._json(store.add_watch(body, snapshot, _now()), 201)

    def _watch_query(self, w: dict) -> str:
        return " ".join(p for p in [w.get("company", ""), w.get("keyword", "")] if p).strip()

    def _check_watch(self, body: dict) -> None:
        wid = body.get("id")
        watches = [store.get_watch(wid)] if wid else store.list_watchlist()
        watches = [w for w in watches if w]
        results = []
        for w in watches:
            q = self._watch_query(w)
            matches = jobs.search(q, limit=20)["items"] if q else []
            results.append({"id": w.get("id"), "query": q, "matches": matches})
        self._json({"results": results})

    # ── AI 핸들러(지연 임포트: anthropic 미설치/키 없음 시 친절히 안내) ──
    def _ai_ready(self):
        if not store.get_api_key():
            self._err("ANTHROPIC_API_KEY가 없습니다. 설정 탭에서 키를 저장하세요.", 412)
            return None
        try:
            from . import ai
        except ImportError:
            self._err("anthropic 패키지가 없습니다: .venv/bin/pip install anthropic", 500)
            return None
        return ai

    def _ai_analyze(self, body: dict) -> None:
        ai = self._ai_ready()
        if ai is None:
            return
        job = jobs.get(body.get("key", "")) or body.get("job")
        if not job:
            return self._err("job not found", 404)
        result = ai.analyze_fit(store.get_profile(), job)
        self._json(result)

    def _ai_answer(self, body: dict) -> None:
        ai = self._ai_ready()
        if ai is None:
            return
        cap = store.get_capture(body.get("capture_id", ""))
        if not cap:
            return self._err("capture not found", 404)
        job = jobs.get(body.get("key", "")) if body.get("key") else None
        result = ai.generate_answers(store.get_profile(), cap, job)
        self._json(result)

    def _ai_generate(self, body: dict) -> None:
        ai = self._ai_ready()
        if ai is None:
            return
        job = jobs.get(body.get("key", "")) or body.get("job")
        if not job:
            return self._err("job not found", 404)
        kind = body.get("kind", "resume")  # resume | cover_letter
        result = ai.generate_document(store.get_profile(), job, kind)
        # 결과 보관(지원 추적에서 연결 가능)
        rid = store.save_resume(
            {"kind": kind, "job": {k: job.get(k) for k in ("site", "idx", "company", "title", "url")},
             "document": result.get("document", ""), "gaps": result.get("gaps", []),
             "facts_used": result.get("facts_used", [])},
            _now())
        result["resume_id"] = rid
        self._json(result)


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[admin] 비공개 관리자 서버 → http://{HOST}:{PORT}  (외부 노출 안 됨)")
    print(f"[admin] AI 키: {'설정됨' if store.get_api_key() else '없음 — 설정 탭에서 입력'}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[admin] 종료")


if __name__ == "__main__":
    main()
