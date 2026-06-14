# Architecture

## 1. Overview

An automated pipeline retrieves song/video metadata from **Spotify** and
**YouTube**, cleans and conforms it, and stores it in a query-friendly
warehouse so analysts can answer two questions:

1. **How many videos does each song have on YouTube?**
2. **How many ISRCs does each song have on Spotify?**

```
                ┌──────────────┐
 Google Sheet ──▶  EXTRACT     │  Python jobs (catalog, Spotify, YouTube)
 Spotify API ───▶  (ingestion) │  retries + backoff, quota guard, mock mode
 YouTube API ───▶              │
                └──────┬───────┘
                       ▼
                ┌──────────────┐   raw schema  (landing, full JSON-ish rows
                │   LOAD       │                + _ingested_at / _source / audit)
                └──────┬───────┘
                       ▼
                ┌──────────────┐   staging schema (clean, standardize, dedup,
                │  TRANSFORM   │                   validate — dbt views)
                │   (dbt)      │   marts schema   (dim_song, fct_*, business marts)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │   SERVE      │   PostgreSQL warehouse → BI / SQL / data science
                └──────────────┘

 Orchestration: Airflow DAG (daily) runs each stage as a DockerOperator task.
```

## 2. Why this stack

| Concern | Choice | Reason |
|---|---|---|
| Ingestion | Python (`spotipy`, `google-api-python-client`) | Official-ish SDKs, easy retries/backoff with `tenacity`. |
| Transform | **dbt** | SQL-first, versioned, tested transformations; lineage + docs for free; what analysts can read and extend. |
| Storage | **PostgreSQL** (medallion schemas) | Runs anywhere via Docker; ANSI-SQL identical to a cloud warehouse, so models lift-and-shift to BigQuery/Snowflake/Redshift unchanged. |
| Orchestration | **Airflow** (optional profile) | Industry standard scheduling, retries, observability; DAG separates orchestration from execution. |
| Packaging | **Docker Compose** | One command to reproduce the whole environment on any machine. |

## 3. Medallion layers

- **raw** — exact landing of each source, plus `_ingested_at`, `_source`, and a
  `raw._load_audit` row per load (lineage & freshness).
- **staging** — one cleaned view per source: trim/standardize casing, type-cast
  safely, deduplicate on natural keys, flag invalid values (e.g. ISRC format).
- **marts** — `dim_song` (conformed dimension), `fct_spotify_tracks` /
  `fct_youtube_videos` (facts), and the business marts that answer the two
  questions, plus `mart_song_overview`.

## 4. Data quality & validation strategy

Implemented as **dbt tests** that run on every build (`dbt build` = run + test):

- **Uniqueness / not-null** on every primary key (`song_id`, `spotify_track_id`,
  `video_id`) — catches duplicates and missing keys.
- **Referential integrity** — `relationships` tests ensure every fact row maps
  to a real `dim_song`.
- **Format validation** — `is_valid_isrc` flags ISRCs that don't match
  `CC-XXX-YY-NNNNN`; a singular test surfaces malformed-but-present ISRCs as
  anomalies.
- **Range / sanity** — singular test asserting metric counts are never negative.
- **Deduplication** — `row_number()` windows in staging keep the latest row per
  natural key.
- **Missing data** — rows without a title/artist (catalog) or without a track/
  video id are dropped at staging; `LEFT JOIN` in marts means a song with zero
  matches still appears with a count of 0 rather than vanishing.

**Corruption / anomaly handling:** the `raw._load_audit` table records row
counts per load, so a sudden drop (e.g. an upstream API change returning empty)
is detectable. dbt test failures stop the pipeline (`dbt build` is fail-fast),
and Airflow marks the run failed and alerts. Raw is kept immutable so any
transform bug is replayable without re-hitting the APIs.

## 5. Storage layer design & justification

- **Schemas as access tiers:** analysts query `marts`; `raw`/`staging` stay for
  engineering. Grants can be scoped per schema.
- **Read-optimized marts:** marts are materialized **tables** (not views) so BI
  queries are fast; staging stays as cheap views.
- **Cloud mapping:** because everything is plain SQL on Postgres, moving to a
  columnar cloud warehouse is a profile change, not a rewrite:
  - **BigQuery** — serverless, partition `fct_*` by ingestion date, cluster by
    `song_id`; great for spiky analytical load.
  - **Snowflake** — separation of storage/compute, auto-suspend warehouses.
  - **Redshift** — if already on AWS; distkey on `song_id`.
  At scale, `fct_*` tables become **incremental** dbt models (append new
  ingest dates) and are **partitioned/clustered** on `song_id` + date.

## 6. Pipeline monitoring & maintenance

**Monitoring**
- Airflow UI: per-task status, duration, logs; retries with exponential backoff
  (3 attempts). Configure email/Slack on-failure callbacks.
- dbt test results gate the run; failures block marts from publishing stale data.
- `raw._load_audit` gives row-count trends per source for freshness/volume
  alerts (e.g. alert if a load returns 0 rows).
- API quota: `MAX_SONGS` caps YouTube search calls (100 units each, 10k/day).

**Maintenance**
- Idempotent full-refresh by default; switch `fct_*` to incremental as volume
  grows.
- Schema evolution handled in staging (flexible header mapping in
  `catalog.py`), so upstream sheet changes don't break downstream models.
- `dbt docs generate` produces a browsable catalog + lineage graph.
- Secrets via env/`.env` (never committed); rotate API keys without code change.
- Caching/snapshotting raw responses enables re-runs without burning API quota.

## 7. Known assumptions & next steps

- The internal Google Sheet schema is mapped flexibly; adjust `SYNONYMS` in
  `src/pipeline/catalog.py` to your exact headers.
- "Videos per song" = distinct YouTube search hits for `title + artist`. A
  production refinement would add relevance filtering (channel allow-list,
  Official Artist Channel, fuzzy title match) to reduce false positives.
- "ISRCs per song" = distinct valid ISRCs across all matched Spotify tracks.
- Next: incremental models, great-expectations-style freshness SLAs, and a
  reconciliation step that links Spotify ISRC ↔ catalog ISRC.
