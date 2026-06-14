"""Extraction orchestration.

Reads the internal catalog from raw.catalog and, for each song (up to
MAX_SONGS), fetches Spotify tracks and YouTube videos, then loads the
collected rows into raw.spotify_tracks / raw.youtube_videos.

If API credentials are absent, an offline MOCK generator is used so the whole
pipeline (load -> dbt -> marts) can still be demonstrated end-to-end.
"""
from __future__ import annotations

import logging
import random

import pandas as pd
from sqlalchemy import text

from . import config, db
from .clients import musicbrainz as mb_client
from .clients import spotify as spotify_client
from .clients import youtube as youtube_client

log = logging.getLogger("pipeline.extract")

# Explicit column schemas so the raw tables always exist with the right columns,
# even when a source returns zero rows (e.g. Spotify 403 or sparse MusicBrainz).
SPOTIFY_COLUMNS = [
    "song_id", "spotify_track_id", "isrc", "track_name", "album_name",
    "album_id", "release_date", "artist_name", "artist_id", "popularity",
    "duration_ms", "explicit", "spotify_url",
]
YOUTUBE_COLUMNS = [
    "song_id", "video_id", "channel_id", "channel_title", "video_title",
    "description", "published_at", "query_artist", "query_title", "video_url",
]


def _spotify_df(rows: list[dict]) -> "pd.DataFrame":
    return pd.DataFrame(rows, columns=SPOTIFY_COLUMNS)


def _youtube_df(rows: list[dict]) -> "pd.DataFrame":
    return pd.DataFrame(rows, columns=YOUTUBE_COLUMNS)


def _catalog_rows(limit: int) -> list[dict]:
    with db.engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT song_id, song_title, artist_name "
                "FROM raw.catalog LIMIT :n"
            ),
            {"n": limit},
        ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- mock helpers
def _mock_spotify(song):
    n = random.randint(1, 4)
    return [
        {
            "song_id": song["song_id"],
            "spotify_track_id": f"mock_sp_{song['song_id']}_{i}",
            "isrc": f"US{random.choice(['ABC','XYZ','QED'])}{random.randint(1000000,9999999)}",
            "track_name": song["song_title"],
            "album_name": f"Album {i}",
            "album_id": f"alb_{i}",
            "release_date": "2020-01-01",
            "artist_name": song["artist_name"],
            "artist_id": "art_mock",
            "popularity": random.randint(0, 100),
            "duration_ms": random.randint(120000, 300000),
            "explicit": False,
            "spotify_url": "https://open.spotify.com/track/mock",
        }
        for i in range(n)
    ]


def _mock_youtube(song):
    n = random.randint(0, 6)
    return [
        {
            "song_id": song["song_id"],
            "video_id": f"mock_yt_{song['song_id']}_{i}",
            "channel_id": f"chan_{i}",
            "channel_title": f"Channel {i}",
            "video_title": f"{song['song_title']} (Official Video {i})",
            "description": "mock",
            "published_at": "2021-05-01T00:00:00Z",
            "query_artist": song["artist_name"],
            "query_title": song["song_title"],
            "video_url": "https://youtube.com/watch?v=mock",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------- extractors
def _collect_musicbrainz(songs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for s in songs:
        try:
            rows += mb_client.search_isrcs_for_song(
                s["song_id"], s["song_title"], s["artist_name"]
            )
        except Exception as exc:  # noqa: BLE001
            log.error("MusicBrainz failed for %s: %s", s["song_id"], exc)
    return rows


def _collect_spotify(songs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for s in songs:
        try:
            rows += spotify_client.search_tracks_for_song(
                s["song_id"], s["song_title"], s["artist_name"]
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Spotify failed for %s: %s", s["song_id"], exc)
    return rows


def extract_spotify(use_mock: bool | None = None) -> int:
    """Populate raw.spotify_tracks (the ISRC source).

    Routing (config.pipeline.isrc_source):
      * musicbrainz -> always MusicBrainz (free)
      * spotify     -> Spotify (mock if no credentials)
      * auto        -> Spotify if its credentials actually work, otherwise the
                       free MusicBrainz source; mock only if neither is usable.
    """
    songs = _catalog_rows(config.pipeline.max_songs)
    source = (config.pipeline.isrc_source or "auto").lower()
    has_creds = bool(config.spotify.client_id and config.spotify.client_secret)

    if use_mock is True:
        rows = [r for s in songs for r in _mock_spotify(s)]
        return db.load_dataframe(_spotify_df(rows), "spotify_tracks", "raw", source="spotify_mock")

    if source == "musicbrainz":
        rows = _collect_musicbrainz(songs)
        return db.load_dataframe(_spotify_df(rows), "spotify_tracks", "raw", source="musicbrainz")

    if source == "spotify":
        if not has_creds:
            log.warning("ISRC_SOURCE=spotify but no credentials -> MOCK data.")
            rows = [r for s in songs for r in _mock_spotify(s)]
            return db.load_dataframe(_spotify_df(rows), "spotify_tracks", "raw", source="spotify_mock")
        rows = _collect_spotify(songs)
        return db.load_dataframe(_spotify_df(rows), "spotify_tracks", "raw", source="spotify_api")

    # ---- auto ----
    if has_creds and spotify_client.is_available():
        log.info("Using Spotify Web API for ISRCs.")
        rows = _collect_spotify(songs)
        return db.load_dataframe(_spotify_df(rows), "spotify_tracks", "raw", source="spotify_api")

    log.warning("Spotify unavailable -> falling back to MusicBrainz (free) for ISRCs.")
    rows = _collect_musicbrainz(songs)
    return db.load_dataframe(_spotify_df(rows), "spotify_tracks", "raw", source="musicbrainz_fallback")


def extract_youtube(use_mock: bool | None = None) -> int:
    use_mock = _should_mock(use_mock, config.youtube.api_key)
    songs = _catalog_rows(config.pipeline.max_songs)
    rows: list[dict] = []
    for s in songs:
        try:
            if use_mock:
                rows += _mock_youtube(s)
            else:
                rows += youtube_client.search_videos_for_song(
                    s["song_id"], s["song_title"], s["artist_name"]
                )
        except Exception as exc:  # noqa: BLE001
            log.error("YouTube failed for %s: %s", s["song_id"], exc)
    df = _youtube_df(rows)
    return db.load_dataframe(df, "youtube_videos", "raw",
                             source="youtube_mock" if use_mock else "youtube_api")


def _should_mock(explicit: bool | None, credential: str | None) -> bool:
    if explicit is not None:
        return explicit
    mock = credential in (None, "", "changeme")
    if mock:
        log.warning("No credential present -> using MOCK data for this source.")
    return mock
