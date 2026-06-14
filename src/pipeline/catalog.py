"""Load the internal song catalog (exported from the Google Sheet) into raw.

The real Google Sheet schema is provided to candidates at runtime; to stay
robust we normalize header names and map common synonyms. The only hard
requirement is a song title + artist. A stable `song_id` is derived if the
sheet does not provide one.
"""
from __future__ import annotations

import hashlib
import logging
import re

import pandas as pd

from . import config, db

log = logging.getLogger("pipeline.catalog")

# Map many possible sheet headers -> our canonical column names.
SYNONYMS = {
    "song_id": {"song_id", "id", "track_id", "catalog_id", "song id", "code"},
    "song_title": {"song_title", "title", "song", "recording_title", "track",
                   "song name", "song title"},
    "artist_name": {"artist_name", "artist", "artists", "performer",
                    "main artist", "original artist"},
    "album": {"album", "album_name", "release", "release_title"},
    "isrc": {"isrc", "isrc_code"},
    "release_date": {"release_date", "released", "date"},
}


def _canonical(col: str) -> str | None:
    key = re.sub(r"[^a-z0-9 _]", "", col.strip().lower())
    for canonical, variants in SYNONYMS.items():
        if key in variants:
            return canonical
    return None


def _stable_id(title: str, artist: str) -> str:
    raw = f"{(title or '').strip().lower()}|{(artist or '').strip().lower()}"
    return "song_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def load_catalog(csv_path: str | None = None) -> pd.DataFrame:
    path = csv_path or config.pipeline.catalog_csv
    log.info("Reading internal catalog from %s", path)
    df = pd.read_csv(path, dtype=str).fillna("")

    rename = {}
    for col in df.columns:
        canon = _canonical(col)
        if canon:
            rename[col] = canon
    df = df.rename(columns=rename)

    if "song_title" not in df.columns:
        raise ValueError(
            "Catalog must contain a song title column. "
            f"Found columns: {list(df.columns)}. Adjust SYNONYMS in catalog.py "
            "to match your sheet headers."
        )

    # Optional columns: ensure they always exist so downstream models are stable.
    for optional in ("artist_name", "album", "isrc", "release_date", "song_id"):
        if optional not in df.columns:
            df[optional] = ""

    # Derive a stable song_id only for rows missing one (keep the real CODE).
    df["song_id"] = df.apply(
        lambda r: (r["song_id"].strip() if str(r["song_id"]).strip()
                   else _stable_id(r["song_title"], r["artist_name"])),
        axis=1,
    )

    # Drop fully-empty rows (e.g. trailing blank line) and dedup on song_id.
    df = df[df["song_title"].str.strip() != ""]
    keep = [c for c in SYNONYMS if c in df.columns]
    df = df[keep].drop_duplicates(subset=["song_id"]).reset_index(drop=True)

    db.init_schemas()
    db.load_dataframe(df, table="catalog", schema="raw", source="internal_google_sheet")
    return df
