#!/usr/bin/env bash
# Bootstrap Airflow reliably: migrate metadata DB, ensure an admin/admin user
# exists, then run scheduler (background) + webserver (foreground).
set -e

echo ">> Migrating Airflow metadata database..."
airflow db migrate

echo ">> Ensuring admin user (admin/admin) exists..."
airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com || echo "   (user already exists, continuing)"

echo ">> Starting scheduler + webserver..."
airflow scheduler &
exec airflow webserver
