"""Command-line entrypoint for the pipeline.

Usage (inside the container):
    python -m pipeline.cli init
    python -m pipeline.cli extract-catalog
    python -m pipeline.cli extract-spotify
    python -m pipeline.cli extract-youtube
    python -m pipeline.cli dbt-build
    python -m pipeline.cli run-all          # everything, in order
    python -m pipeline.cli show-results     # print the two business answers
"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import text

from . import catalog, config, db, dbt_runner, extract

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("pipeline")


def show_results() -> None:
    queries = {
        "Spotify: distinct ISRCs per song (top 10)": """
            SELECT song_title, artist_name, distinct_isrc_count
            FROM marts.mart_song_spotify_isrc_counts
            ORDER BY distinct_isrc_count DESC LIMIT 10
        """,
        "YouTube: video count per song (top 10)": """
            SELECT song_title, artist_name, youtube_video_count
            FROM marts.mart_song_youtube_video_counts
            ORDER BY youtube_video_count DESC LIMIT 10
        """,
    }
    with db.engine().connect() as conn:
        for title, q in queries.items():
            print(f"\n=== {title} ===")
            for r in conn.execute(text(q)).mappings():
                print("  ", dict(r))


def run_all() -> None:
    db.init_schemas()
    catalog.load_catalog()
    extract.extract_spotify()
    extract.extract_youtube()
    dbt_runner.run("build")
    show_results()


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in [
        "init", "extract-catalog", "extract-spotify", "extract-youtube",
        "dbt-build", "dbt-test", "run-all", "show-results",
    ]:
        sub.add_parser(name)

    args = parser.parse_args()
    cmd = args.cmd

    if cmd == "init":
        db.init_schemas()
    elif cmd == "extract-catalog":
        catalog.load_catalog()
    elif cmd == "extract-spotify":
        extract.extract_spotify()
    elif cmd == "extract-youtube":
        extract.extract_youtube()
    elif cmd == "dbt-build":
        dbt_runner.run("build")
    elif cmd == "dbt-test":
        dbt_runner.run("test")
    elif cmd == "run-all":
        run_all()
    elif cmd == "show-results":
        show_results()


if __name__ == "__main__":
    main()
