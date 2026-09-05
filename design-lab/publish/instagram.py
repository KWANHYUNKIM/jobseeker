"""인스타그램 — Graph API 컨텐츠 게시(2단계).

  1) POST /{ig_user_id}/media           image_url + caption  → creation_id
  2) POST /{ig_user_id}/media_publish   creation_id          → 게시물 id
image_url 은 메타 서버가 직접 받아 가는 주소라 반드시 공개 URL 이어야 한다.
캐러셀은 각 장을 is_carousel_item 으로 만들고 children 으로 묶는다.
"""
from __future__ import annotations

from pathlib import Path

from .base import PublishResult, Publisher

GRAPH = "https://graph.facebook.com"


class InstagramPublisher(Publisher):
    name = "instagram"
    preferred_format = "ig_portrait"
    caption_limit = 2200

    @property
    def required(self) -> tuple[str, ...]:
        return ("ig_user_id", "access_token")

    @property
    def _base(self) -> str:
        ver = self.creds.get("graph_version", "v21.0")
        return f"{GRAPH}/{ver}/{self.creds.get('ig_user_id', 'IG_USER_ID')}"

    def publish(self, *, image: Path, caption: str, link: str = "",
                dry_run: bool = True) -> PublishResult:
        # 인스타 본문은 링크가 안 걸린다. 그래서 링크를 캡션에 넣는 대신 안내 한 줄로 바꾼다.
        caption = caption[: self.caption_limit]
        steps: list[dict] = []
        try:
            image_url = self.public_url_for(image) if not dry_run else f"<public>/{image.name}"
            steps.append({"step": "create_media", "method": "POST",
                          "url": f"{self._base}/media",
                          "params": {"image_url": image_url, "caption": caption[:80] + "…"}})
            steps.append({"step": "publish_media", "method": "POST",
                          "url": f"{self._base}/media_publish",
                          "params": {"creation_id": "<1단계 결과>"}})
        except RuntimeError as e:
            return PublishResult(self.name, False, dry_run, error=str(e), steps=steps)

        if dry_run:
            return PublishResult(self.name, True, True, steps=steps)

        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        token = self.creds["access_token"]
        created = self._request(f"{self._base}/media",
                                data={"image_url": image_url, "caption": caption,
                                      "access_token": token})
        creation_id = created.get("json", {}).get("id", "")
        if not creation_id:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"creation_id 없음: {created}")
        done = self._request(f"{self._base}/media_publish",
                             data={"creation_id": creation_id, "access_token": token})
        media_id = done.get("json", {}).get("id", "")
        return PublishResult(self.name, bool(media_id), False, remote_id=media_id,
                             url=f"https://www.instagram.com/p/{media_id}/" if media_id else "",
                             steps=steps)
