"""① 모으기 — 유튜브. **공식 YouTube Data API v3 만** 쓴다.

유튜브 약관은 공식 API·검색엔진 말고는 자동 수집을 막고, robots.txt 도 자막(/timedtext_video)과
내부 API(/youtubei/, /api/)를 막는다(2026-10-19 확인). 그래서 자막·영상은 받지 않는다 —
API 가 주는 제목·설명·태그·조회수·썸네일 주소만. 영상 속 설명은 사람이 보고 한 줄로 남긴다(python -m agent note).

키: 환경변수 YOUTUBE_API_KEY (Google Cloud 콘솔 → YouTube Data API v3 사용 설정 → 사용자 인증 정보 → API 키).
할당량: 하루 10,000 단위. 채널 하나에 약 3단위(channels 1 + playlistItems 1 + videos 1).
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from . import db

API = "https://www.googleapis.com/youtube/v3/"


def _get(path: str, **params) -> dict:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY 가 없다 — 공식 API 키 없이는 유튜브를 모으지 않는다")
    q = urllib.parse.urlencode({**params, "key": key})
    with urllib.request.urlopen(API + path + "?" + q, timeout=30) as r:
        return json.load(r)


def collect(handle: str, source_id: int, limit: int = 15) -> int:
    """채널 하나의 최근 영상 → design_ref. 돌려주는 값은 넣은 수."""
    ch = _get("channels", part="snippet,statistics,contentDetails", forHandle=handle.lstrip("@")).get("items") or []
    if not ch:
        raise LookupError(f"{handle}: 채널을 못 찾았다")
    ch = ch[0]
    subs = ch["statistics"].get("subscriberCount")
    db.upsert_source("youtube", handle, f"https://www.youtube.com/{handle}", name=ch["snippet"]["title"],
                     followers=f"{int(subs):,}" if subs else None)
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = _get("playlistItems", part="contentDetails", playlistId=uploads, maxResults=min(50, limit)).get("items") or []
    ids = [i["contentDetails"]["videoId"] for i in items]
    if not ids:
        return 0
    vids = _get("videos", part="snippet,statistics", id=",".join(ids)).get("items") or []
    for v in vids:
        sn, st = v["snippet"], v.get("statistics", {})
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("maxres") or thumbs.get("high") or thumbs.get("medium") or {}).get("url")
        db.upsert_ref(f"https://www.youtube.com/watch?v={v['id']}", source_id=source_id, title=sn["title"],
                      summary=(sn.get("description") or "")[:400], published_at=sn.get("publishedAt"),
                      metrics={k: int(st[k]) for k in ("viewCount", "likeCount", "commentCount") if k in st},
                      media=[{"kind": "thumbnail", "url": thumb}] if thumb else [], collected_by="youtube-api")
    db.touch_source(source_id)
    return len(vids)
