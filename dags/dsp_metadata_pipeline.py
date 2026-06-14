"""MassiveMusic DSP pipeline — Airflow orchestration.

Each stage runs the massivemusic/pipeline image as a DockerOperator task, so
orchestration (Airflow) stays cleanly separated from execution (the image).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

ENV = {
    "WAREHOUSE_HOST": "postgres",
    "WAREHOUSE_PORT": "5432",
    "WAREHOUSE_DB": "warehouse",
    "WAREHOUSE_USER": "warehouse",
    "WAREHOUSE_PASSWORD": "warehouse",
    "SPOTIFY_CLIENT_ID": os.getenv("SPOTIFY_CLIENT_ID", ""),
    "SPOTIFY_CLIENT_SECRET": os.getenv("SPOTIFY_CLIENT_SECRET", ""),
    "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY", ""),
    "ISRC_SOURCE": os.getenv("ISRC_SOURCE", "auto"),
    "MAX_SONGS": os.getenv("MAX_SONGS", "25"),
}

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}


def task(task_id: str, command: str) -> DockerOperator:
    return DockerOperator(
        task_id=task_id,
        image="massivemusic/pipeline:latest",
        command=command,
        environment=ENV,
        network_mode="massivemusic-de_default",
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
    )


with DAG(
    dag_id="dsp_metadata_pipeline",
    description="Ingest Spotify/YouTube metadata, transform with dbt, build marts.",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["massivemusic", "dsp"],
) as dag:
    extract_catalog = task("extract_catalog", "extract-catalog")
    extract_spotify = task("extract_spotify", "extract-spotify")
    extract_youtube = task("extract_youtube", "extract-youtube")
    dbt_build = task("dbt_build", "dbt-build")
    dbt_test = task("dbt_test", "dbt-test")

    extract_catalog >> [extract_spotify, extract_youtube] >> dbt_build >> dbt_test
