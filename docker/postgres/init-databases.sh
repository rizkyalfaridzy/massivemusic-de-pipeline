#!/bin/bash
set -e

# The default POSTGRES_DB (warehouse) is created automatically by the image.
# Here we add a second database for Airflow metadata so one Postgres instance
# serves both purposes during local development.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
EOSQL

echo "Postgres init complete: warehouse + airflow databases ready."
