"""Thin wrapper to invoke dbt from Python so the CLI and the Airflow DAG share
one code path. dbt lives in the same image; we shell out to its CLI.
"""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger("pipeline.dbt")

DBT_DIR = "/app/dbt/massivemusic"
PROFILES_DIR = "/app/dbt/massivemusic"


def run(command: str = "build") -> None:
    cmd = [
        "dbt", command,
        "--project-dir", DBT_DIR,
        "--profiles-dir", PROFILES_DIR,
    ]
    log.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log.info(proc.stdout)
    if proc.returncode != 0:
        log.error(proc.stderr)
        raise RuntimeError(f"dbt {command} failed (exit {proc.returncode})")
