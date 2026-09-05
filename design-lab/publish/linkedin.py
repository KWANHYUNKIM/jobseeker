"""링크드인 — 이미지 업로드 후 글에 붙인다(3단계).

  1) POST /rest/images?action=initializeUpload  → uploadUrl + image URN
  2) PUT  uploadUrl                              바이너리 그대로
  3) POST /rest/posts                            content.media.id = 그 URN
author 는 개인(urn:li:person:...) 또는 회사페이지(urn:li:organization:...).
회사페이지에 올리려면 앱에 w_organization_social 권한이 있어야 한다.
"""
from __future__ import annotations

from pathlib import Path

from .base import PublishResult, Publisher

API = "https://api.linkedin.com"
VERSION = "202405"   # LinkedIn-Version 헤더. 분기마다 올려 준다.


class LinkedInPublisher(Publisher):
    name = "linkedin"
    preferred_format = "li_landscape"
    caption_limit = 3000

    @property
    def required(self) -> tuple[str, ...]:
        return ("author_urn", "access_token")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.creds.get('access_token', '')}",
            "LinkedIn-Version": self.creds.get("api_version", VERSION),
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def publish(self, *, image: Path, caption: str, link: str = "",
                dry_run: bool = True) -> PublishResult:
        author = self.creds.get("author_urn", "urn:li:organization:<ID>")
        text = caption[: self.caption_limit]
        if link and link not in text:
            text = f"{text}\n\n지원하기 → {link}"
        steps = [
            {"step": "initialize_upload", "method": "POST",
             "url": f"{API}/rest/images?action=initializeUpload",
             "params": {"initializeUploadRequest": {"owner": author}}},
            {"step": "upload_binary", "method": "PUT", "url": "<1단계 uploadUrl>",
             "params": {"file": image.name}},
            {"step": "create_post", "method": "POST", "url": f"{API}/rest/posts",
             "params": {"author": author, "commentary": text[:80] + "…",
                        "content": {"media": {"id": "<1단계 image URN>"}}}},
        ]
        if dry_run:
            return PublishResult(self.name, True, True, steps=steps)
        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")

        init = self._request(f"{API}/rest/images?action=initializeUpload",
                             json_body={"initializeUploadRequest": {"owner": author}},
                             headers=self._headers())
        value = init.get("json", {}).get("value", {})
        upload_url, image_urn = value.get("uploadUrl", ""), value.get("image", "")
        if not upload_url or not image_urn:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"업로드 URL 없음: {init}")
        self._request(upload_url, raw=image.read_bytes(), method="PUT",
                      headers={**self._headers(), "Content-Type": "application/octet-stream"})
        post = self._request(
            f"{API}/rest/posts",
            json_body={
                "author": author,
                "commentary": text,
                "visibility": "PUBLIC",
                "distribution": {"feedDistribution": "MAIN_FEED",
                                 "targetEntities": [], "thirdPartyDistributionChannels": []},
                "content": {"media": {"id": image_urn, "title": text.splitlines()[0][:100]}},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
            headers={**self._headers(), "Content-Type": "application/json"})
        post_id = post.get("headers", {}).get("x-restli-id") or post.get("json", {}).get("id", "")
        return PublishResult(self.name, bool(post_id), False, remote_id=post_id,
                             url=f"https://www.linkedin.com/feed/update/{post_id}" if post_id else "",
                             steps=steps)
