"""Spotify client (Client-Credentials flow).

For each internal song we search Spotify and collect every matching track,
keeping its ISRC and core metadata. The business metric (distinct ISRCs per
song) is computed later in dbt from this raw track-level data.
"""
from __future__ import annotations

import logging
import time

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
)

from .. import config

log = logging.getLogger("pipeline.spotify")


def _client() -> spotipy.Spotify:
    if not (config.spotify.client_id and config.spotify.client_secret):
        raise RuntimeError("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set.")
    auth = SpotifyClientCredentials(
        client_id=config.spotify.client_id,
        client_secret=config.spotify.client_secret,
    )
    return spotipy.Spotify(client_credentials_manager=auth, requests_timeout=15)


@retry(
    retry=retry_if_exception_type(spotipy.SpotifyException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _search(sp: spotipy.Spotify, query: str) -> list[dict]:
    res = sp.search(
        q=query, type="track", limit=config.spotify.search_limit,
        market=config.spotify.market,
    )
    return res.get("tracks", {}).get("items", [])


def is_available() -> bool:
    """Quick probe: returns False if Spotify rejects with 401/403 (e.g. the
    Feb-2026 'Premium app owner required' restriction), so callers can fall
    back to a free source. Other errors are treated as transient -> available.
    """
    try:
        sp = _client()
        sp.search(q='track:"test"', type="track", limit=1, market=config.spotify.market)
        return True
    except spotipy.SpotifyException as exc:
        if exc.http_status in (401, 403):
            log.warning("Spotify unavailable (HTTP %s): %s", exc.http_status, exc.msg)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Spotify probe error (assuming available): %s", exc)
        return True


def search_tracks_for_song(song_id: str, title: str, artist: str) -> list[dict]:
    """Return one record per matching Spotify track for an internal song."""
    sp = _client()
    artist = (artist or "").strip()
    query = f'track:"{title}" artist:"{artist}"' if artist else f'track:"{title}"'
    items = _search(sp, query)
    rows: list[dict] = []
    for t in items:
        rows.append(
            {
                "song_id": song_id,
                "spotify_track_id": t.get("id"),
                "isrc": (t.get("external_ids") or {}).get("isrc"),
                "track_name": t.get("name"),
                "album_name": (t.get("album") or {}).get("name"),
                "album_id": (t.get("album") or {}).get("id"),
                "release_date": (t.get("album") or {}).get("release_date"),
                "artist_name": ", ".join(a["name"] for a in t.get("artists", [])),
                "artist_id": (t.get("artists") or [{}])[0].get("id"),
                "popularity": t.get("popularity"),
                "duration_ms": t.get("duration_ms"),
                "explicit": t.get("explicit"),
                "spotify_url": (t.get("external_urls") or {}).get("spotify"),
            }
        )
    time.sleep(config.pipeline.request_sleep)
    log.info("Spotify: song_id=%s -> %s tracks", song_id, len(rows))
    return rows
