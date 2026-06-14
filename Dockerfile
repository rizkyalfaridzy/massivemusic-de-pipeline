FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; psycopg2-binary ships its own libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application code, dbt project and seed data.
COPY src/ /app/src/
COPY dbt/ /app/dbt/
COPY data/ /app/data/

ENV PYTHONPATH=/app/src \
    DBT_PROFILES_DIR=/app/dbt/massivemusic

# Default to the full pipeline; overridable in docker-compose.
ENTRYPOINT ["python", "-m", "pipeline.cli"]
CMD ["run-all"]
