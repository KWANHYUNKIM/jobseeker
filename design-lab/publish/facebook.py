"""페이스북 페이지 — 사진 한 방(1단계).

  POST /{page_id}/photos   url(공개 이미지) 또는 source(바이너리) + message
링크는 본문에 그대로 걸린다. 페이지 토큰(user 토큰 아님)이 필요하다.
"""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from .base import PublishResult, Publisher

GRAPH = "https://graph.facebook.com"


def _multipart(fields: dict, file_field: str, path: Path) -> tuple[bytes, str]:
    """stdlib 만으로 multipart/form-data 를 만든다(requests 를 안 쓰기 위해)."""
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
            f"filename=\"{path.name}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
    out += path.read_bytes() + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


class FacebookPublisher(Publisher):
    name = "facebook"
    preferred_format = "fb_landscape"
    caption_limit = 5000

    @property
    def required(self) -> tuple[str, ...]:
        return ("page_id", "access_token")

    def publish(self, *, image: Path, caption: str, link: str = "",
                dry_run: bool = True) -> PublishResult:
        ver = self.creds.get("graph_version", "v21.0")
        url = f"{GRAPH}/{ver}/{self.creds.get('page_id', 'PAGE_ID')}/photos"
        message = caption[: self.caption_limit]
        if link and link not in message:
            message = f"{message}\n\n지원하기 → {link}"
        steps = [{"step": "upload_photo", "method": "POST", "url": url,
                  "params": {"source": image.name, "message": message[:80] + "…"}}]
        if dry_run:
            return PublishResult(self.name, True, True, steps=steps)
        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        body, ctype = _multipart(
            {"message": message, "access_token": self.creds["access_token"]}, "source", image)
        resp = self._request(url, raw=body, headers={"Content-Type": ctype})
        pid = resp.get("json", {}).get("post_id") or resp.get("json", {}).get("id", "")
        return PublishResult(self.name, bool(pid), False, remote_id=pid,
                             url=f"https://www.facebook.com/{pid}" if pid else "", steps=steps)
