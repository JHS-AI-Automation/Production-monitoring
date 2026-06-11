#!/usr/bin/env bash
# Bouwt Optimax voor de IXrouter5/SecureEdge (ARM64/v8) en pusht naar de router-registry.
#
# Het image is SECRET-VRIJ: alle app-config (DB_*, OPENROUTER_API_KEY, DASHBOARD_AUTH_*,
# CHAT_*, LOG_*) geef je op als environment-variabelen bij het aanmaken van de container
# in het IXON-portaal. Zie DEPLOY-ixrouter.md en docker-compose.edgeapp.yml.
#
# Vooraf (eenmalig) op de buildmachine:
#   - Docker Desktop: Settings > Docker Engine: {"insecure-registries":["<ROUTER_IP>:5000"]}
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

APP_PORT="${APP_PORT:-9000}"
IMAGE="${ROUTER_IP}:5000/optimax:latest"

# Builder met de insecure-registry-config (faalt stil als hij al bestaat).
docker buildx create --name ixrouter5 --config buildkitd-ixrouter5.toml 2>/dev/null || true
docker buildx use ixrouter5

echo "Bouwen en pushen naar ${IMAGE} (linux/arm64/v8, poort ${APP_PORT})..."
docker buildx build --platform linux/arm64/v8 \
  --build-arg APP_PORT="$APP_PORT" \
  --build-arg INSTALL_CORP_CA="${INSTALL_CORP_CA:-0}" \
  --build-arg APP_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  -t "$IMAGE" --push .

echo ""
echo "Klaar. ${IMAGE} staat in de router-registry (secret-vrij)."
echo "Volgende stappen (zie DEPLOY-ixrouter.md):"
echo "  1. Maak in het IXON-portaal een container van het 'optimax'-image."
echo "  2. Geef daar de env-vars op: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,"
echo "     DASHBOARD_AUTH_USER, DASHBOARD_AUTH_PASSWORD (en optioneel OPENROUTER_API_KEY/CHAT_*)."
echo "  3. Poort ${APP_PORT}, netwerk machine-builder, named volume optimax-logs -> /app/logs."
echo "  4. Open daarna het dashboard: http://${ROUTER_IP}:${APP_PORT}"
