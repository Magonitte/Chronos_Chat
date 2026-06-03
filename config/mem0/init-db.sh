#!/bin/bash
set -e

# Cria DB de app (auth/logs). Vector store usa POSTGRES_DB principal.
APP_DB="${MEM0_APP_DB_NAME:-mem0_app}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  SELECT 'CREATE DATABASE ${APP_DB}'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${APP_DB}')\gexec
EOSQL
