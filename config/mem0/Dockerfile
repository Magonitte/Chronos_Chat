# Build amd64 — mem0/mem0-api-server no Docker Hub é linux/arm64 apenas.
# Código-fonte: https://github.com/mem0ai/mem0/tree/main/server

FROM python:3.12-slim

ARG MEM0_GIT_REF=main

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --depth 1 --branch "${MEM0_GIT_REF}" https://github.com/mem0ai/mem0.git /tmp/mem0 \
    && cp -a /tmp/mem0/server/. /app/ \
    && rm -rf /tmp/mem0

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "psycopg[binary]>=3.2.8"

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
