"""Central configuration, loaded from environment variables.

All secrets and tunables live here so the rest of the code never hardcodes
credentials. Values are read from the process environment (populated by the
`.env` file via docker-compose).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _get(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class WarehouseConfig:
    host: str = _get("WAREHOUSE_HOST", "postgres")
    port: int = int(_get("WAREHOUSE_PORT", "5432"))
    db: str = _get("WAREHOUSE_DB", "warehouse")
    user: str = _get("WAREHOUSE_USER", "warehouse")
    password: str = _get("WAREHOUSE_PASSWORD", "warehouse")

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


@dataclass(frozen=True)
class SpotifyConfig:
    client_id: str | None = _get("SPOTIFY_CLIENT_ID")
    client_secret: str | None = _get("SPOTIFY_CLIENT_SECRET")
    # Cap searches to control rate-limits during the demo.
    market: str = _get("SPOTIFY_MARKET", "US")
    search_limit: int = int(_get("SPOTIFY_SEARCH_LIMIT", "10"))


@dataclass(frozen=True)
class YouTubeConfig:
    api_key: str | None = _get("YOUTUBE_API_KEY")
    # YouTube search costs 100 quota units/call (10k/day default => ~100 songs/day).
    max_results: int = int(_get("YOUTUBE_MAX_RESULTS", "50"))


@dataclass(frozen=True)
class MusicBrainzConfig:
    # Free, no account. MusicBrainz requires a descriptive User-Agent.
    user_agent: str = _get(
        "MUSICBRAINZ_USER_AGENT",
        "massivemusic-de-pipeline/1.0 ( techtest@example.com )",
    )
    search_limit: int = int(_get("MUSICBRAINZ_SEARCH_LIMIT", "25"))
    max_recordings: int = int(_get("MB_MAX_RECORDINGS", "8"))
    sleep: float = float(_get("MB_SLEEP", "1.1"))  # respect ~1 req/sec policy


@dataclass(frozen=True)
class PipelineConfig:
    # Limit how many catalog songs we process per run (protects API quota).
    max_songs: int = int(_get("MAX_SONGS", "25"))
    catalog_csv: str = _get("CATALOG_CSV", "/app/data/seed/songs_catalog.csv")
    request_sleep: float = float(_get("REQUEST_SLEEP", "0.2"))
    # ISRC source: auto | spotify | musicbrainz.
    # "auto" uses Spotify if its credentials work, else falls back to the free
    # MusicBrainz source (Spotify now requires a Premium app owner, Feb 2026).
    isrc_source: str = _get("ISRC_SOURCE", "auto")


warehouse = WarehouseConfig()
spotify = SpotifyConfig()
youtube = YouTubeConfig()
musicbrainz = MusicBrainzConfig()
pipeline = PipelineConfig()
