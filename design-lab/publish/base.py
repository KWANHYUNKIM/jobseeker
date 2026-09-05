"""플랫폼 공통 규약 + 자격증명 로딩."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
CONFIG = LAB_DIR / "config" / "accounts.json"
PLATFORMS = ("instagram", "facebook", "linkedin")

# 환경변수가 있으면 파일보다 우선한다(로컬 파일에 토큰을 안 남기고 싶을 때).
ENV_KEYS = {
    "instagram": {"access_token": "DESIGN_LAB_IG_TOKEN", "ig_user_id": "DESIGN_LAB_IG_USER_ID"},
    "facebook": {"access_token": "DESIGN_LAB_FB_TOKEN", "page_id": "DESIGN_LAB_FB_PAGE_ID"},
    "linkedin": {"access_token": "DESIGN_LAB_LI_TOKEN", "author_urn": "DESIGN_LAB_LI_AUTHOR"},
}


def load_config() -> dict:
    cfg = {}
    if CONFIG.is_file():
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    for platform, keys in ENV_KEYS.items():
        block = cfg.setdefault(platform, {})
        for field_name, env in keys.items():
            if os.environ.get(env):
                block[field_name] = os.environ[env]
    if os.environ.get("DESIGN_LAB_PUBLIC_BASE"):
        cfg["public_base_url"] = os.environ["DESIGN_LAB_PUBLIC_BASE"]
    return cfg


@dataclass
class PublishResult:
    platform: str
    ok: bool
    dry_run: bool
    remote_id: str = ""
    url: str = ""
    error: str = ""
    steps: list[dict] = field(default_factory=list)   # 어떤 요청을 어떤 순서로 보냈는지

    def as_dict(self) -> dict:
        return asdict(self)


class Publisher(ABC):
    """플랫폼 하나. check() 로 자격을 보고, publish() 로 한 건 올린다."""

    name: str = ""
    #: 이 플랫폼에서 가장 잘 먹는 포맷(랩 UI 가 기본 선택으로 쓴다)
    preferred_format: str = "ig_portrait"
    #: 캡션 길이 상한(플랫폼 실제 제한)
    caption_limit: int = 2200

    def __init__(self, config: dict | None = None):
        self.config = (config or load_config())
        self.creds = self.config.get(self.name, {})

    # --- 자격 ---------------------------------------------------------
    @property
    @abstractmethod
    def required(self) -> tuple[str, ...]:
        """있어야 올릴 수 있는 자격 키들."""

    def missing(self) -> list[str]:
        return [k for k in self.required if not self.creds.get(k)]

    def check(self) -> dict:
        return {
            "platform": self.name,
            "ready": not self.missing(),
            "missing": self.missing(),
            "preferred_format": self.preferred_format,
        }

    # --- 발행 ---------------------------------------------------------
    @abstractmethod
    def publish(self, *, image: Path, caption: str, link: str = "",
                dry_run: bool = True) -> PublishResult:
        """포스터 한 장을 올린다. dry_run 이면 요청을 만들기만 하고 안 보낸다."""

    # --- 공통 HTTP ----------------------------------------------------
    def _request(self, url: str, *, data=None, headers=None, method="POST",
                 json_body: dict | None = None, raw: bytes | None = None) -> dict:
        headers = dict(headers or {})
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body).encode()
            headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            body = urllib.parse.urlencode(data).encode()
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif raw is not None:
            body = raw
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8", "replace")
                out = {"status": resp.status, "headers": dict(resp.headers)}
                try:
                    out["json"] = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    out["text"] = text[:400]
                return out
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:600]
            raise RuntimeError(f"{self.name} HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"{self.name} 연결 실패: {e.reason}") from None

    def public_url_for(self, image: Path) -> str:
        """인스타처럼 '공개 URL' 을 요구하는 곳에 쓸 주소.

        out/ 을 그대로 웹에 노출하는 순간 남의 공고 이미지가 다 열린다. 그래서
        base 는 설정에서만 온다 — 없으면 여기서 막는다.
        """
        base = (self.config.get("public_base_url") or "").rstrip("/")
        if not base:
            raise RuntimeError(
                "public_base_url 이 없습니다. 인스타는 공개 URL 로만 받으므로 "
                "config/accounts.json 에 out/ 을 노출할 주소를 적어야 합니다.")
        rel = image.resolve().relative_to((LAB_DIR / "out").resolve())
        return f"{base}/{rel.as_posix()}"


def publisher_for(platform: str, config: dict | None = None) -> Publisher:
    from . import facebook, instagram, linkedin
    table = {
        "instagram": instagram.InstagramPublisher,
        "facebook": facebook.FacebookPublisher,
        "linkedin": linkedin.LinkedInPublisher,
    }
    if platform not in table:
        raise KeyError(f"모르는 플랫폼: {platform}")
    return table[platform](config)
