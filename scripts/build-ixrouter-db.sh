#!/usr/bin/env bash
# Bouwt de dummy-data Postgres (optimax-db) voor de IXrouter5 en pusht naar de router-registry.
# Genereert eerst ~3 maanden verse dummy-data als seed. DEMO-data, geen echte monitoring.
#
# Vooraf (eenmalig): zie scripts/build-ixrouter.sh (buildx + insecure-registry via .toml).
# Gebruik:  ./scripts/build-ixrouter-db.sh            (of: ... pad/naar/env)
#           DUMMY_DAYS=180 ./scripts/build-ixrouter-db.sh   (meer dagen)
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="${1:-.ixrouter.env}"
[ -f "$ENV_FILE" ] || { echo "FOUT: $ENV_FILE niet gevonden. Kopieer .ixrouter.env.example en vul in."; exit 1; }
set -a; . "$ENV_FILE"; set +a
: "${ROUTER_IP:?ROUTER_IP ontbreekt in $ENV_FILE}"

DAYS="${DUMMY_DAYS:-95}"   # ~3 maanden; weekenden worden overgeslagen (~65 weekdagen)
IMAGE="${ROUTER_IP}:5000/optimax-db:latest"
# Op Windows kan 'python' ontbreken in PATH; gebruik dan de project-venv:
#   PY=.venv/Scripts/python.exe ./scripts/build-ixrouter-db.sh
PY="${PY:-python}"

echo "1/3 Dummy-data genereren (~${DAYS} dagen) -> db/seed.sql ..."
mkdir -p db
"$PY" scripts/generate_dummy_data.py --days "$DAYS" > db/seed.sql
echo "    $(wc -l < db/seed.sql) regels SQL gegenereerd."

echo "2/3 Builder klaarzetten (insecure registry via buildkitd-ixrouter5.toml) ..."
docker buildx create --name ixrouter5 --config buildkitd-ixrouter5.toml 2>/dev/null || true
docker buildx use ixrouter5

echo "3/3 Bouwen (linux/arm64/v8) + pushen naar ${IMAGE} ..."
docker buildx build --platform linux/arm64/v8 -f Dockerfile.db -t "$IMAGE" --push .

echo ""
echo "Klaar. ${IMAGE} staat in de router-registry."
echo "Vervolg (IXON-portaal):"
echo "  1. Container 'optimax-db': netwerk machine-builder, volume optimax-db-data -> /var/lib/postgresql/data (geen poort)."
echo "  2. Container 'optimax': poort 9000, netwerk machine-builder, env DB_HOST=optimax-db DB_USER=optimax DB_PASSWORD=optimax_demo DB_NAME=db_dgs_01 + DASHBOARD_AUTH_*."
