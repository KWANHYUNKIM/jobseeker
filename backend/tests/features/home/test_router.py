"""메인 API 가 모르는 값을 계산 전에 돌려보내는지 — 밖에 열린 API 다(DB 없이 돈다: 검증에서 끝난다)."""
from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_rejects_unknown_params():
    assert client.get("/api/home?size=<script>").status_code == 422
    assert client.get("/api/home?sort=drop table").status_code == 422
    assert client.get("/api/home?industry=없는업종").status_code == 422
    assert client.get("/api/home?limit=100000").status_code == 422
    assert client.get("/api/home?offset=-1").status_code == 422


def test_rejects_bad_slugs_and_section_keys():
    assert client.get("/api/home/company/" + "a" * 200).status_code == 422
    assert client.get("/api/home/company/..%2F..%2Fetc").status_code in (404, 422)
    assert client.get("/api/home/company/<img>").status_code == 422
    assert client.get("/api/home/section/whatever").status_code == 422
