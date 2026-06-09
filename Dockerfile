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
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/static ./static/

# Git-commit meegeven aan de build zodat /api/version de exacte deploy toont:
#   docker build --build-arg APP_COMMIT=$(git rev-parse --short HEAD) .
ARG APP_COMMIT=unknown
ENV APP_COMMIT=${APP_COMMIT}

# --- Optioneel config inbakken voor platforms zonder runtime-env (bv. IXrouter5) ---
# Defaults leeg: de normale docker-compose-build blijft ongewijzigd, want compose
# overschrijft deze ENV bij het draaien (env_file/environment). Voor de router worden
# ze via --build-arg gevuld (zie scripts/build-ixrouter.sh). Let op: secrets komen zo
# in het image - bewuste tradeoff voor de MVP-router (lokale registry).
ARG DB_HOST=""
ARG DB_PORT=""
ARG DB_NAME=""
ARG DB_USER=""
ARG DB_PASSWORD=""
ARG OPENROUTER_API_KEY=""
ARG CHAT_MODEL=""
ARG CHAT_DB_USER=""
ARG CHAT_DB_PASSWORD=""
ARG CHAT_TLS_VERIFY=""
ARG CHAT_CA_BUNDLE=""
ARG DASHBOARD_AUTH_USER=""
ARG DASHBOARD_AUTH_PASSWORD=""
ARG LOG_FORMAT=""
ARG LOG_LEVEL=""
ENV DB_HOST=${DB_HOST} \
    DB_PORT=${DB_PORT} \
    DB_NAME=${DB_NAME} \
    DB_USER=${DB_USER} \
    DB_PASSWORD=${DB_PASSWORD} \
    OPENROUTER_API_KEY=${OPENROUTER_API_KEY} \
    CHAT_MODEL=${CHAT_MODEL} \
    CHAT_DB_USER=${CHAT_DB_USER} \
    CHAT_DB_PASSWORD=${CHAT_DB_PASSWORD} \
    CHAT_TLS_VERIFY=${CHAT_TLS_VERIFY} \
    CHAT_CA_BUNDLE=${CHAT_CA_BUNDLE} \
    DASHBOARD_AUTH_USER=${DASHBOARD_AUTH_USER} \
    DASHBOARD_AUTH_PASSWORD=${DASHBOARD_AUTH_PASSWORD} \
    LOG_FORMAT=${LOG_FORMAT} \
    LOG_LEVEL=${LOG_LEVEL}

# Poort instelbaar via build-arg. De router-web-UI draait zelf op 8080; kies voor de
# router bijv. APP_PORT=9000 om botsing te voorkomen. Default blijft 8080 (compose).
ARG APP_PORT=8080
ENV APP_PORT=${APP_PORT}
EXPOSE ${APP_PORT}

# Healthcheck zodat de Docker-/router-UI de status (healthy/unhealthy) toont.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('APP_PORT','8080'))" || exit 1

# Shell-vorm zodat ${APP_PORT} wordt ingevuld bij het starten.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${APP_PORT:-8080}"]
