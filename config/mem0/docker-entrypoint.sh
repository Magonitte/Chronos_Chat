#!/bin/sh
set -e

python3 <<'PY'
import os
import time

import psycopg

host = os.environ.get("POSTGRES_HOST", "mem0-postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
user = os.environ.get("POSTGRES_USER", "mem0")
password = os.environ.get("POSTGRES_PASSWORD", "mem0")
main_db = os.environ.get("POSTGRES_DB", "mem0")
app_db = os.environ.get("APP_DB_NAME", "mem0_app")

for attempt in range(30):
    try:
        conn = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=main_db,
            connect_timeout=3,
        )
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("Postgres not reachable")

conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (app_db,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{app_db}"')
conn.close()
PY

alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port 8000
