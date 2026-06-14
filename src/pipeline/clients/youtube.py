"""YouTube Data API v3 client (API-key auth).

For each internal song we run a search and collect matching videos. The
business metric (number of videos per song) is computed later in dbt.

Quota note: search.list costs 100 units per call; the default daily quota is
10,000 units => ~100 songs/day. MAX_SONGS in config guards against overrun.
"""
from __future__ import annotations

import logging
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .. import config

log = logging.getLogger("pipeline.youtube")


def _client():
    if not config.youtube.api_key:
        raise RuntimeError("YOUTUBE_API_KEY not set.")
    return build("youtube", "v3", developerKey=config.youtube.api_key, cache_discovery=False)


@retry(
    retry=retry_if_exception_type(HttpError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
def _search(yt, query: str) -> list[dict]:
    res = (
        yt.search()
        .list(q=query, part="snippet", type="video", maxResults=config.youtube.max_results)
        .execute()
    )
    return res.get("items", [])


def search_videos_for_song(song_id: str, title: str, artist: str) -> list[dict]:
    """Return one record per matching YouTube video for an internal song."""
    yt = _client()
    artist = (artist or "").strip()
    query = f"{title} {artist}".strip()
    items = _search(yt, query)
    rows: list[dict] = []
    for it in items:
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid:
            continue
        rows.append(
            {
                "song_id": song_id,
                "video_id": vid,
                "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle"),
                "video_title": sn.get("title"),
                "description": (sn.get("description") or "")[:500],
                "published_at": sn.get("publishedAt"),
                "query_artist": artist,
                "query_title": title,
                "video_url": f"https://www.youtube.com/watch?v={vid}",
            }
        )
    time.sleep(config.pipeline.request_sleep)
    log.info("YouTube: song_id=%s -> %s videos", song_id, len(rows))
    return rows
