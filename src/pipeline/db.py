"""Warehouse access helpers (PostgreSQL).

Responsibilities:
  * create the `raw`, `staging`, `marts` schemas
  * (re)load raw tables from pandas DataFrames in a safe, idempotent way
  * keep a `_load_metadata` audit row for every raw load (lineage / monitoring)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text

from . import config

log = logging.getLogger("pipeline.db")

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(config.warehouse.sqlalchemy_url, pool_pre_ping=True)
    return _engine


def init_schemas() -> None:
    """Create the medallion schemas + an audit table. Idempotent."""
    ddl = """
    CREATE SCHEMA IF NOT EXISTS raw;
    CREATE SCHEMA IF NOT EXISTS staging;
    CREATE SCHEMA IF NOT EXISTS marts;

    CREATE TABLE IF NOT EXISTS raw._load_audit (
        load_id      BIGSERIAL PRIMARY KEY,
        table_name   TEXT        NOT NULL,
        row_count    INTEGER     NOT NULL,
        source       TEXT        NOT NULL,
        loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        details      JSONB
    );
    """
    with engine().begin() as conn:
        for stmt in filter(str.strip, ddl.split(";")):
            conn.execute(text(stmt))
    log.info("Schemas raw/staging/marts ensured.")


def load_dataframe(
    df: pd.DataFrame,
    table: str,
    schema: str = "raw",
    source: str = "unknown",
    if_exists: str = "replace",
) -> int:
    """Write a DataFrame to <schema>.<table> and record an audit row.

    `if_exists="replace"` keeps the demo idempotent (full refresh). In
    production these raw loads would be append/merge with a load watermark.
    """
    if df is None:
        df = pd.DataFrame()
    if df.empty:
        log.warning("No rows for %s.%s (creating empty table with its columns)", schema, table)

    # Add ingestion metadata columns for lineage.
    df = df.copy()
    df["_ingested_at"] = datetime.now(timezone.utc)
    df["_source"] = source

    # When replacing, drop dependent objects (e.g. dbt staging views) first.
    # pandas' own DROP TABLE has no CASCADE, which breaks idempotent re-runs.
    if if_exists == "replace":
        with engine().begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{table}" CASCADE'))

    df.to_sql(
        table,
        engine(),
        schema=schema,
        if_exists="append" if if_exists == "replace" else if_exists,
        index=False,
        method="multi",
        chunksize=500,
    )

    with engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw._load_audit (table_name, row_count, source, details) "
                "VALUES (:t, :n, :s, CAST(:d AS jsonb))"
            ),
            {
                "t": f"{schema}.{table}",
                "n": len(df),
                "s": source,
                "d": json.dumps({"columns": list(df.columns)}),
            },
        )
    log.info("Loaded %s rows into %s.%s", len(df), schema, table)
    return len(df)
