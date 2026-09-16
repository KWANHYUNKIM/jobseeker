"""페이스북 페이지 — 사진 한 방(1단계).

  POST /{page_id}/photos   url(공개 이미지) 또는 source(바이너리) + message
  POST /{page_id}/videos   source(바이너리) + description        ← 영상
링크는 본문에 그대로 걸린다. 페이지 토큰(user 토큰 아님)이 필요하다.

인스타와 달리 페이스북은 **파일을 직접 받는다** — 공개 URL 을 요구하지 않는다.
그래서 영상도 exposed/ 에 내놓지 않고 multipart 로 그냥 올린다(주소가 하나 덜 샌다).
"""
from __future__ import annotations

import json
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
        url = f"{GRAPH}/{ver}/{self.creds.get('page_id') or 'PAGE_ID'}/photos"
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

    def publish_video(self, *, video: Path, caption: str, cover: Path | None = None,
                      link: str = "", dry_run: bool = True) -> PublishResult:
        """페이지 동영상 한 편. 인스타 릴스와 같은 묶음이 여기로도 나간다.

        페이스북은 파일을 직접 받으므로 공개 URL 이 필요 없고, 인코딩을 기다릴 필요도
        없다(업로드가 끝나면 id 가 온다). 인스타 쪽보다 단계가 하나 적은 이유다.
        """
        ver = self.creds.get("graph_version", "v21.0")
        page = self.creds.get("page_id") or "PAGE_ID"
        url = f"{GRAPH}/{ver}/{page}/videos"
        message = f"{caption}\n{link}".strip() if link else caption
        message = message[: self.caption_limit]
        steps = [{"step": "upload_video", "method": "POST", "url": url,
                  "params": {"source": video.name, "description": message[:80] + "…"}}]
        if video.suffix.lower() not in (".mp4", ".mov"):
            return PublishResult(self.name, False, dry_run, steps=steps,
                                 error=f"동영상은 mp4/mov 만 받습니다: {video.name}")
        if dry_run:
            return PublishResult(self.name, True, True, steps=steps)
        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        try:
            body, ctype = _multipart(
                {"description": message, "access_token": self.creds["access_token"]},
                "source", video)
            resp = self._request(url, raw=body, headers={"Content-Type": ctype})
        except RuntimeError as e:
            return PublishResult(self.name, False, False, steps=steps, error=str(e))
        vid = resp.get("json", {}).get("id", "")
        if not vid:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"동영상 id 없음: {resp.get('json') or resp.get('text')}")
        return PublishResult(self.name, True, False, remote_id=vid,
                             url=f"https://www.facebook.com/{page}/videos/{vid}", steps=steps)

    def publish_many(self, *, images: list[Path], caption: str, link: str = "",
                     dry_run: bool = True) -> PublishResult:
        """사진 여러 장 글 — 사진을 published=false 로 먼저 올려 id 를 받고, 글에 붙인다."""
        if len(images) == 1:
            return self.publish(image=images[0], caption=caption, link=link, dry_run=dry_run)
        ver = self.creds.get("graph_version", "v21.0")
        page = self.creds.get("page_id") or "PAGE_ID"   # dry-run 주소에 '//' 가 찍히지 않게
        photos_url, feed_url = f"{GRAPH}/{ver}/{page}/photos", f"{GRAPH}/{ver}/{page}/feed"
        message = caption[: self.caption_limit]
        steps = [
            {"step": "upload_photos", "method": "POST", "url": photos_url,
             "params": {"published": "false", "source": f"<{len(images)}장>"}},
            {"step": "create_post", "method": "POST", "url": feed_url,
             "params": {"message": message[:80] + "…", "attached_media": "<사진 id 목록>"}},
        ]
        if dry_run:
            return PublishResult(self.name, True, True, steps=steps)
        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        token = self.creds["access_token"]
        try:
            ids = []
            for img in images:
                body, ctype = _multipart({"published": "false", "access_token": token}, "source", img)
                r = self._request(photos_url, raw=body, headers={"Content-Type": ctype})
                pid = r.get("json", {}).get("id", "")
                if not pid:
                    raise RuntimeError(f"사진 업로드 실패({img.name}): {r.get('json') or r.get('text')}")
                ids.append(pid)
            data = {"message": message, "access_token": token}
            for i, pid in enumerate(ids):
                data[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
            resp = self._request(feed_url, data=data)
            post = resp.get("json", {}).get("id", "")
            if not post:
                raise RuntimeError(f"글 id 없음: {resp.get('json') or resp.get('text')}")
        except RuntimeError as e:
            return PublishResult(self.name, False, False, steps=steps, error=str(e))
        return PublishResult(self.name, True, False, remote_id=post,
                             url=f"https://www.facebook.com/{post}", steps=steps)
