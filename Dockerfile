# syntax=docker/dockerfile:1
# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime with FastAPI
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt ./

# Optionele bedrijfs-CA voor builds achter SSL-inspectie (default UIT).
# Leg het root-certificaat als .crt in certs/ en bouw met --build-arg INSTALL_CORP_CA=1.
# De certs komen binnen via een BuildKit bind-mount (SEC-15): anders dan met COPY
# belandt het certificaat dan NOOIT in een image-laag, ook niet bij een gewone build
# terwijl er toevallig een .crt in certs/ ligt.
ARG INSTALL_CORP_CA=0
RUN --mount=type=bind,source=certs,target=/tmp/corp-certs \
    if [ "$INSTALL_CORP_CA" = "1" ]; then \
        mkdir -p /usr/local/share/ca-certificates/corp && \
        cp /tmp/corp-certs/*.crt /usr/local/share/ca-certificates/corp/ && \
        apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
        update-ca-certificates && rm -rf /var/lib/apt/lists/* && \
        pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt -r requirements.txt; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

COPY backend/ ./backend/
COPY --from=frontend-build /app/static ./static/

# Git-commit meegeven aan de build zodat /api/version de exacte deploy toont:
#   docker build --build-arg APP_COMMIT=$(git rev-parse --short HEAD) .
ARG APP_COMMIT=unknown
ENV APP_COMMIT=${APP_COMMIT}

# App-config (DB_*, OPENROUTER_API_KEY, DASHBOARD_AUTH_*, CHAT_*, LOG_*) komt bij RUNTIME
# binnen als environment-variabelen: via docker-compose (env_file/environment) of, op de
# SecureEdge, via de env-vars die bij het aanmaken van de container in het IXON-portaal
# worden opgegeven. Er wordt bewust NIETS ingebakken: dit image staat in een open lokale
# registry en mag dus geen secrets bevatten (uitleesbaar via docker history/inspect).

# Fabriekstijd: logs, healthcheck-tijden en alles dat naive "nu" gebruikt rekent in
# Amsterdam-tijd i.p.v. UTC. De API-datumdefaults gebruiken daarnaast expliciet
# zoneinfo (backend/timewindow.py), dus die kloppen ook zonder deze ENV.
ENV TZ=Europe/Amsterdam

# Poort instelbaar via build-arg. De router-web-UI draait zelf op 8080; kies voor de
# router bijv. APP_PORT=9000 om botsing te voorkomen. Default blijft 8080 (compose).
# Runtime-override kan ook: APP_PORT als env-var bij het starten (CMD leest hem uit env).
ARG APP_PORT=8080
ENV APP_PORT=${APP_PORT}
EXPOSE ${APP_PORT}

# Draai als non-root (CIS Docker 4.1). De app is een pure read-consumer en heeft geen
# root nodig; zo blijft de schade beperkt als de app of een dependency ooit gecompromitteerd raakt.
# /app/logs moet schrijfbaar zijn voor deze user (named volume erft de eigenaar bij eerste mount).
RUN useradd --system --uid 10001 --no-create-home appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app
USER appuser

# Healthcheck zodat de Docker-/router-UI de status (healthy/unhealthy) toont.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('APP_PORT','8080'))" || exit 1

# Shell-vorm zodat ${APP_PORT} wordt ingevuld bij het starten; exec zorgt dat uvicorn
# PID 1 wordt en SIGTERM direct ontvangt (nette shutdown i.p.v. 10s docker-kill).
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${APP_PORT:-8080}"]
