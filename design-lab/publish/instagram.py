"""인스타그램 — 컨텐츠 게시(컨테이너 → 상태 확인 → 게시).

  1) POST /{ig_user_id}/media                 image_url + caption  → 컨테이너 id
  2) GET  /{컨테이너}?fields=status_code        FINISHED 가 될 때까지 (IN_PROGRESS / ERROR / EXPIRED)
  3) POST /{ig_user_id}/media_publish         creation_id          → 게시물 id
  4) GET  /{게시물}?fields=permalink            게시물 id 는 주소가 아니다(/p/ 뒤는 shortcode)

로그인 방식이 둘이다. 기본은 인스타 로그인(graph.instagram.com) — 프로 계정만 있으면 되고
페이스북 페이지가 필요 없다. 권한은 instagram_business_basic + instagram_business_content_publish.
페이지에 연결된 계정을 페이스북 로그인으로 쓰려면 login 을 "facebook" 으로 둔다.

image_url 은 메타 서버가 직접 받아 가는 주소라 반드시 공개 URL 이어야 하고 JPEG 만 된다.
게시 한도는 24시간 이동 창에서 100건(content_publishing_limit 로 확인).

**릴스**(`publish_video`)도 같은 세 단계인데, video_url 로 mp4 를 주고 기다리는 시간이
훨씬 길다(메타가 받아서 다시 인코딩한다). `share_to_feed=true` 를 켜야 릴스 탭만이
아니라 프로필 피드에도 남는다.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

from .base import PublishResult, Publisher

HOSTS = {"instagram": "https://graph.instagram.com", "facebook": "https://graph.facebook.com"}

# 문서 권장은 '1분에 한 번, 5분 이하'. 이미지는 대개 몇 초면 끝나서 앞쪽을 촘촘히 둔다.
STATUS_WAITS = (3, 7, 20, 30, 60, 60, 60, 60)
# 영상은 메타가 받아서 **다시 인코딩**한다. 이미지처럼 몇 초에 끝나지 않아
# 따로 둔다(합 10분). 여기서 일찍 포기하면 멀쩡한 영상이 실패로 기록된다.
VIDEO_WAITS = (10, 15, 20, 30, 45, 60, 60, 60, 60, 60, 60, 60)
#: 캐러셀 한 게시물에 들어가는 장 수 상한
CAROUSEL_MAX = 10


class InstagramPublisher(Publisher):
    name = "instagram"
    preferred_format = "ig_portrait"
    caption_limit = 2200

    #: 테스트가 바꿔 끼운다
    sleep = staticmethod(time.sleep)

    @property
    def required(self) -> tuple[str, ...]:
        return ("ig_user_id", "access_token")

    @property
    def login(self) -> str:
        return self.creds.get("login", "instagram")

    @property
    def _root(self) -> str:
        ver = self.creds.get("graph_version", "v21.0")
        return f"{HOSTS.get(self.login, HOSTS['instagram'])}/{ver}"

    @property
    def _base(self) -> str:
        return f"{self._root}/{self.creds.get('ig_user_id', 'IG_USER_ID')}"

    def _get(self, url: str, **params) -> dict:
        params["access_token"] = self.creds["access_token"]
        return self._request(url, data=params, method="GET").get("json", {})

    # --- 게시 ---------------------------------------------------------
    def publish(self, *, image: Path, caption: str, link: str = "",
                dry_run: bool = True) -> PublishResult:
        # 인스타 본문은 링크가 안 걸린다. 캡션이 '프로필 링크' 로 넘긴다(caption.py).
        caption = caption[: self.caption_limit]
        steps: list[dict] = []
        if image.suffix.lower() not in (".jpg", ".jpeg"):
            return PublishResult(self.name, False, dry_run, steps=steps,
                                 error=f"인스타는 JPEG 만 받습니다: {image.name}")
        try:
            image_url = self.public_url_for(image) if not dry_run else f"<public>/{image.name}"
        except RuntimeError as e:
            return PublishResult(self.name, False, dry_run, error=str(e), steps=steps)
        steps += [
            {"step": "create_media", "method": "POST", "url": f"{self._base}/media",
             "params": {"image_url": image_url, "caption": caption[:80] + "…"}},
            {"step": "container_status", "method": "GET", "url": f"{self._root}/<컨테이너>",
             "params": {"fields": "status_code"}},
            {"step": "publish_media", "method": "POST", "url": f"{self._base}/media_publish",
             "params": {"creation_id": "<1단계 결과>"}},
            {"step": "permalink", "method": "GET", "url": f"{self._root}/<게시물>",
             "params": {"fields": "permalink"}},
        ]
        if dry_run:
            return PublishResult(self.name, True, True, url=image_url, steps=steps)

        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        token = self.creds["access_token"]
        try:
            created = self._request(f"{self._base}/media",
                                    data={"image_url": image_url, "caption": caption,
                                          "access_token": token})
            creation_id = created.get("json", {}).get("id", "")
            if not creation_id:
                raise RuntimeError(f"컨테이너 id 없음: {created.get('json') or created.get('text')}")

            status = self._wait_container(creation_id)
            if status != "FINISHED":
                raise RuntimeError(f"컨테이너 상태 {status} — 이미지 주소를 메타가 못 받았을 수 있습니다: {image_url}")

            done = self._request(f"{self._base}/media_publish",
                                 data={"creation_id": creation_id, "access_token": token})
            media_id = done.get("json", {}).get("id", "")
            if not media_id:
                raise RuntimeError(f"게시물 id 없음: {done.get('json') or done.get('text')}")
        except RuntimeError as e:
            return PublishResult(self.name, False, False, steps=steps, error=str(e))

        permalink = ""
        try:                                   # 게시는 이미 됐다. 주소 조회 실패로 실패 처리하면 중복 게시가 난다
            permalink = self._get(f"{self._root}/{media_id}", fields="permalink").get("permalink", "")
        except RuntimeError:
            pass
        return PublishResult(self.name, True, False, remote_id=media_id, url=permalink,
                             steps=steps, image_url=image_url)

    def publish_many(self, *, images: list[Path], caption: str, link: str = "",
                     dry_run: bool = True) -> PublishResult:
        """캐러셀 — 장마다 컨테이너(is_carousel_item)를 만들고 children 으로 묶어 한 번에 게시한다."""
        if len(images) == 1:
            return self.publish(image=images[0], caption=caption, dry_run=dry_run)
        caption = caption[: self.caption_limit]
        steps = [
            {"step": "create_items", "method": "POST", "url": f"{self._base}/media",
             "params": {"is_carousel_item": "true", "image_url": f"<public>/… ({len(images)}장)"}},
            {"step": "create_carousel", "method": "POST", "url": f"{self._base}/media",
             "params": {"media_type": "CAROUSEL", "children": "<장별 컨테이너>", "caption": caption[:60] + "…"}},
            {"step": "publish_media", "method": "POST", "url": f"{self._base}/media_publish",
             "params": {"creation_id": "<캐러셀 컨테이너>"}},
        ]
        if len(images) > CAROUSEL_MAX:
            return PublishResult(self.name, False, dry_run, steps=steps,
                                 error=f"캐러셀은 {CAROUSEL_MAX}장까지입니다({len(images)}장)")
        bad = [p.name for p in images if p.suffix.lower() not in (".jpg", ".jpeg")]
        if bad:
            return PublishResult(self.name, False, dry_run, steps=steps,
                                 error=f"인스타는 JPEG 만 받습니다: {', '.join(bad)}")
        try:
            urls = [self.public_url_for(p) if not dry_run else f"<public>/{p.name}" for p in images]
        except RuntimeError as e:
            return PublishResult(self.name, False, dry_run, error=str(e), steps=steps)
        if dry_run:
            return PublishResult(self.name, True, True, url=urls[0], steps=steps)

        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        token = self.creds["access_token"]
        try:
            children = []
            for url in urls:
                r = self._request(f"{self._base}/media",
                                  data={"image_url": url, "is_carousel_item": "true",
                                        "access_token": token})
                cid = r.get("json", {}).get("id", "")
                if not cid:
                    raise RuntimeError(f"장별 컨테이너 id 없음: {r.get('json') or r.get('text')}")
                children.append(cid)
            for cid in children:                      # 한 장이라도 처리 중이면 캐러셀이 실패한다
                st = self._wait_container(cid)
                if st != "FINISHED":
                    raise RuntimeError(f"장별 컨테이너 상태 {st} — 이미지 주소 확인: {urls[children.index(cid)]}")
            made = self._request(f"{self._base}/media",
                                 data={"media_type": "CAROUSEL", "children": ",".join(children),
                                       "caption": caption, "access_token": token})
            carousel = made.get("json", {}).get("id", "")
            if not carousel:
                raise RuntimeError(f"캐러셀 컨테이너 id 없음: {made.get('json') or made.get('text')}")
            if (st := self._wait_container(carousel)) != "FINISHED":
                raise RuntimeError(f"캐러셀 컨테이너 상태 {st}")
            done = self._request(f"{self._base}/media_publish",
                                 data={"creation_id": carousel, "access_token": token})
            media_id = done.get("json", {}).get("id", "")
            if not media_id:
                raise RuntimeError(f"게시물 id 없음: {done.get('json') or done.get('text')}")
        except RuntimeError as e:
            return PublishResult(self.name, False, False, steps=steps, error=str(e))

        permalink = ""
        try:
            permalink = self._get(f"{self._root}/{media_id}", fields="permalink").get("permalink", "")
        except RuntimeError:
            pass
        return PublishResult(self.name, True, False, remote_id=media_id, url=permalink,
                             steps=steps, image_url=urls[0])

    def publish_video(self, *, video: Path, caption: str, cover: Path | None = None,
                      link: str = "", dry_run: bool = True) -> PublishResult:
        """릴스 — media_type=REELS + video_url 로 컨테이너를 만들고 처리가 끝나면 게시한다.

        이미지와 다른 점이 셋이다.

        1. **share_to_feed 를 켠다.** 안 켜면 릴스 탭에만 남고 프로필 피드(타임라인)에
           안 보인다. 우리가 원하는 건 타임라인에 남는 것이다.
        2. **훨씬 오래 걸린다.** 메타가 받아서 다시 인코딩한다 — VIDEO_WAITS 를 따로 둔 이유.
        3. **음원을 못 붙인다.** API 로는 인기 음원 사용이 막혀 있어 영상은 무음으로
           나간다(무음 AAC 트랙은 `poster.video` 가 깔아 둔다). 음악은 앱에서 얹는다.

        표지(cover)는 넘기지 않는다. 릴스의 `cover_url` 도 공개 URL 을 요구하는데,
        첫 장이 곧 표지가 되도록 판을 짜 두었으므로 한 장을 더 노출할 이유가 없다.
        """
        caption = caption[: self.caption_limit]
        steps = [
            {"step": "create_reel", "method": "POST", "url": f"{self._base}/media",
             "params": {"media_type": "REELS", "video_url": f"<public>/{video.name}",
                        "share_to_feed": "true", "caption": caption[:60] + "…"}},
            {"step": "wait_container", "method": "GET", "url": f"{self._root}/<컨테이너>",
             "params": {"fields": "status_code"}},
            {"step": "publish_media", "method": "POST", "url": f"{self._base}/media_publish",
             "params": {"creation_id": "<릴스 컨테이너>"}},
        ]
        if video.suffix.lower() not in (".mp4", ".mov"):
            return PublishResult(self.name, False, dry_run, steps=steps,
                                 error=f"릴스는 mp4/mov 만 받습니다: {video.name}")
        try:
            video_url = self.public_url_for(video) if not dry_run else f"<public>/{video.name}"
        except RuntimeError as e:
            return PublishResult(self.name, False, dry_run, error=str(e), steps=steps)
        if dry_run:
            return PublishResult(self.name, True, True, url=video_url, steps=steps)

        missing = self.missing()
        if missing:
            return PublishResult(self.name, False, False, steps=steps,
                                 error=f"자격 없음: {', '.join(missing)}")
        token = self.creds["access_token"]
        try:
            made = self._request(f"{self._base}/media",
                                 data={"media_type": "REELS", "video_url": video_url,
                                       "share_to_feed": "true", "caption": caption,
                                       "access_token": token})
            cid = made.get("json", {}).get("id", "")
            if not cid:
                raise RuntimeError(f"릴스 컨테이너 id 없음: {made.get('json') or made.get('text')}")
            if (st := self._wait_container(cid, waits=VIDEO_WAITS)) != "FINISHED":
                raise RuntimeError(
                    f"릴스 컨테이너 상태 {st} — 영상 주소를 메타가 못 받았거나 "
                    f"규격에 걸렸습니다(h264/yuv420p/오디오 트랙): {video_url}")
            done = self._request(f"{self._base}/media_publish",
                                 data={"creation_id": cid, "access_token": token})
            media_id = done.get("json", {}).get("id", "")
            if not media_id:
                raise RuntimeError(f"게시물 id 없음: {done.get('json') or done.get('text')}")
        except RuntimeError as e:
            return PublishResult(self.name, False, False, steps=steps, error=str(e))

        permalink = ""
        try:
            permalink = self._get(f"{self._root}/{media_id}", fields="permalink").get("permalink", "")
        except RuntimeError:
            pass
        return PublishResult(self.name, True, False, remote_id=media_id, url=permalink,
                             steps=steps, image_url=video_url)

    def _wait_container(self, creation_id: str, waits: tuple[int, ...] = STATUS_WAITS) -> str:
        status = "IN_PROGRESS"
        for wait in waits:
            self.sleep(wait)
            status = self._get(f"{self._root}/{creation_id}", fields="status_code").get("status_code", "")
            if status != "IN_PROGRESS":
                return status
        return status

    # --- 운영 조회 ----------------------------------------------------
    def publishing_limit(self) -> dict:
        """{"used": n, "limit": 100} — 24시간 이동 창 기준."""
        j = self._get(f"{self._base}/content_publishing_limit", fields="quota_usage,config")
        row = (j.get("data") or [{}])[0]
        return {"used": row.get("quota_usage", 0),
                "limit": (row.get("config") or {}).get("quota_total", 100)}

    def media_stats(self, media_id: str) -> dict:
        j = self._get(f"{self._root}/{media_id}",
                      fields="like_count,comments_count,permalink,timestamp")
        return {"likes": j.get("like_count"), "comments": j.get("comments_count"),
                "permalink": j.get("permalink", "")}

    def refresh_token(self) -> dict:
        """장기 토큰(60일)을 새로 받는다. 발급 24시간 뒤부터, 만료 전에만 된다.

        인스타 로그인 토큰만 이 방식이다. 페이스북 로그인은 앱 비밀키로 교환해야 해서 여기서 안 한다.
        """
        if self.login != "instagram":
            raise RuntimeError("페이스북 로그인 토큰은 refresh_access_token 으로 갱신할 수 없습니다")
        j = self._request(f"{HOSTS['instagram']}/refresh_access_token",
                          data={"grant_type": "ig_refresh_token",
                                "access_token": self.creds["access_token"]},
                          method="GET").get("json", {})
        if not j.get("access_token"):
            raise RuntimeError(f"토큰 갱신 응답에 access_token 이 없습니다: {j}")
        expires = datetime.now() + timedelta(seconds=int(j.get("expires_in") or 0))
        return {"access_token": j["access_token"],
                "token_expires_at": expires.isoformat(timespec="seconds"),
                "token_refreshed_at": datetime.now().isoformat(timespec="seconds")}
