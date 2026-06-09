#!/usr/bin/env bash
# Bouwt Optimax voor de IXrouter5 (ARM64/v8) met ingebakken config en pusht naar de
# router-registry. De router kan geen env-variabelen bij het starten meegeven, dus alle
# config wordt hier in het image gebakken via --build-arg.
#
# Vooraf (eenmalig) op de buildmachine:
#   - /etc/docker/daemon.json bevat:  {"insecure-registries":["<ROUTER_IP>:5000"]}
#   - docker buildx beschikbaar (Docker Desktop heeft dit)
#   - kopieer .ixrouter.env.example -> .ixrouter.env en vul in (NIET committen)
#
# Gebruik:  ./scripts/build-ixrouter.sh   (of:  ./scripts/build-ixrouter.sh pad/naar/env)
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="${1:-.ixrouter.env}"
[ -f "$ENV_FILE" ] || { echo "FOUT: $ENV_FILE niet gevonden. Kopieer .ixrouter.env.example en vul in."; exit 1; }
set -a; . "$ENV_FILE"; set +a

: "${ROUTER_IP:?ROUTER_IP ontbreekt in $ENV_FILE}"
: "${DB_HOST:?DB_HOST ontbreekt}"; : "${DB_NAME:?DB_NAME ontbreekt}"
: "${DB_USER:?DB_USER ontbreekt}"; : "${DB_PASSWORD:?DB_PASSWORD ontbreekt}"

APP_PORT="${APP_PORT:-9000}"
IMAGE="${ROUTER_IP}:5000/optimax:latest"

# Builder met de insecure-registry-config (faalt stil als hij al bestaat).
docker buildx create --name ixrouter5 --config buildkitd-ixrouter5.toml 2>/dev/null || true
docker buildx use ixrouter5

echo "Bouwen en pushen naar ${IMAGE} (linux/arm64/v8, poort ${APP_PORT})..."
docker buildx build --platform linux/arm64/v8 \
  --build-arg DB_HOST="$DB_HOST" \
  --build-arg DB_PORT="${DB_PORT:-5432}" \
  --build-arg DB_NAME="$DB_NAME" \
  --build-arg DB_USER="$DB_USER" \
  --build-arg DB_PASSWORD="$DB_PASSWORD" \
  --build-arg OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
  --build-arg CHAT_MODEL="${CHAT_MODEL:-anthropic/claude-sonnet-4}" \
  --build-arg CHAT_DB_USER="${CHAT_DB_USER:-}" \
  --build-arg CHAT_DB_PASSWORD="${CHAT_DB_PASSWORD:-}" \
  --build-arg CHAT_TLS_VERIFY="${CHAT_TLS_VERIFY:-true}" \
  --build-arg CHAT_CA_BUNDLE="${CHAT_CA_BUNDLE:-}" \
  --build-arg CHAT_DAILY_TOKEN_BUDGET="${CHAT_DAILY_TOKEN_BUDGET:-300000}" \
  --build-arg DASHBOARD_AUTH_USER="${DASHBOARD_AUTH_USER:-}" \
  --build-arg DASHBOARD_AUTH_PASSWORD="${DASHBOARD_AUTH_PASSWORD:-}" \
  --build-arg LOG_FORMAT="${LOG_FORMAT:-json}" \
  --build-arg LOG_LEVEL="${LOG_LEVEL:-INFO}" \
  --build-arg APP_PORT="$APP_PORT" \
  --build-arg INSTALL_CORP_CA="${INSTALL_CORP_CA:-0}" \
  --build-arg APP_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  -t "$IMAGE" --push .

echo ""
echo "Klaar. ${IMAGE} staat in de router-registry."
echo "Volgende stappen (zie DEPLOY-ixrouter.md):"
echo "  1. Open de router-web-UI: http://${ROUTER_IP}:8080"
echo "  2. Maak een container van het 'optimax'-image, koppel named volume 'optimax-logs' -> /app/logs"
echo "  3. Open daarna het dashboard: http://${ROUTER_IP}:${APP_PORT}"
