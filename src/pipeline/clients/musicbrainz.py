"""MusicBrainz client — a free, no-account source of ISRC codes.

Used as a fallback for the "ISRCs per song" metric when the Spotify Web API is
unavailable (since Feb 2026 Spotify requires the app owner to hold a Premium
subscription, even for metadata/search).

Flow per song:
  1. search recordings matching title + artist
  2. for each recording (capped), look up its ISRCs (inc=isrcs)
  3. emit one row per (recording, isrc), schema-compatible with raw.spotify_tracks

MusicBrainz asks for ~1 request/second and a descriptive User-Agent; both are
honored via config (MB_SLEEP, MUSICBRAINZ_USER_AGENT).
"""
from __future__ import annotations

import logging
import time

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .. import config

log = logging.getLogger("pipeline.musicbrainz")

BASE = "https://musicbrainz.org/ws/2"


def _headers() -> dict:
    return {"User-Agent": config.musicbrainz.user_agent, "Accept": "application/json"}


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
)
def _get(path: str, params: dict) -> dict:
    resp = requests.get(f"{BASE}{path}", params=params, headers=_headers(), timeout=25)
    if resp.status_code == 503:  # MusicBrainz rate-limit -> retry
        raise requests.HTTPError("503 Service Unavailable (rate limited)")
    resp.raise_for_status()
    return resp.json()


def _artist_name(recording: dict, fallback: str) -> str:
    credit = recording.get("artist-credit") or []
    name = "".join(
        (c.get("name", "") + c.get("joinphrase", ""))
        for c in credit
        if isinstance(c, dict)
    )
    return name.strip() or fallback


def search_isrcs_for_song(song_id: str, title: str, artist: str) -> list[dict]:
    """Return rows compatible with raw.spotify_tracks, populated from MusicBrainz."""
    artist = (artist or "").strip()
    query = (f'recording:"{title}" AND artist:"{artist}"'
             if artist else f'recording:"{title}"')
    time.sleep(config.musicbrainz.sleep)
    data = _get("/recording", {"query": query, "fmt": "json",
                               "limit": config.musicbrainz.search_limit})
    recordings = data.get("recordings", []) or []

    rows: list[dict] = []
    processed = 0
    for rec in recordings:
        if processed >= config.musicbrainz.max_recordings:
            break
        rec_id = rec.get("id")
        if not rec_id:
            continue
        time.sleep(config.musicbrainz.sleep)
        try:
            detail = _get(f"/recording/{rec_id}", {"inc": "isrcs", "fmt": "json"})
        except Exception as exc:  # noqa: BLE001
            log.warning("MB isrc lookup failed for %s: %s", rec_id, exc)
            continue
        isrcs = detail.get("isrcs", []) or []
        processed += 1
        for code in isrcs:
            rows.append(
                {
                    "song_id": song_id,
                    # globally-unique key (song + recording + isrc)
                    "spotify_track_id": f"mb:{song_id}:{rec_id}:{code}",
                    "isrc": code,
                    "track_name": rec.get("title"),
                    "album_name": None,
                    "release_date": None,
                    "artist_name": _artist_name(rec, artist),
                    "popularity": None,
                    "duration_ms": rec.get("length"),
                    "explicit": None,
                    "spotify_url": f"https://musicbrainz.org/recording/{rec_id}",
                }
            )
    log.info("MusicBrainz: song_id=%s -> %s isrc rows (%s recordings)",
             song_id, len(rows), processed)
    return rows
