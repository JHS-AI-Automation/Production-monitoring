# DEPLOY — DGS Optimax op een Linux ARM64 edge-device

Stappen om de app in een container te draaien op het ARM64-apparaat. Voor dagelijkse operatie
zie [RUNBOOK.md](RUNBOOK.md); voor architectuur [ARCHITECTURE.md](ARCHITECTURE.md).

## 0. Vereisten

- Docker + docker compose op het apparaat (`docker --version`, `docker compose version`).
- Toegang tot de database die de PLC-pijplijn vult (Node-RED → PostgreSQL), of een eigen DB.
- Netwerk naar OpenRouter als de chat gebruikt wordt (optioneel).

## 1. Code op het apparaat

**Aanbevolen: via git** (niet een rauwe map-kopie):

```bash
git clone <repo-url> optimax && cd optimax
```

Waarom geen map-kopie? Een kopie sleept `node_modules`/`.venv` (Windows/x64-binaries),
`static/` (oude build) en vooral een ingevulde `.env` met secrets mee. De `.dockerignore`
houdt die uit het image, maar een schone `git clone` voorkomt verwarring en secret-lekken.

## 2. Configuratie (`.env`)

`.env` staat NIET in de repo (secrets). Maak hem aan:

```bash
cp .env.example .env
```

Vul minimaal in:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — de database (zie stap 3).
- Optioneel: `OPENROUTER_API_KEY` + `CHAT_DB_USER/PASSWORD` (chat), `DASHBOARD_AUTH_USER/PASSWORD`
  (toegangsbeveiliging), `CHAT_CA_BUNDLE` (TLS achter SSL-inspectie).

> De app stopt direct met een duidelijke melding als verplichte DB-variabelen ontbreken (fail-fast).

## 3. Welke database? (belangrijkste keuze)

**Optie A — verbind met de echte DGS-database (productie).** Zet in `.env`:
```
DB_HOST=192.168.23.254
DB_PORT=5432
```
De compose gebruikt dan die host. De meegeleverde `db`-service is dan niet nodig
(start alleen `dashboard`, of laat `db` ongebruikt).

**Optie B — meegeleverde Postgres-container (demo/standalone).** Laat `DB_HOST` leeg → default `db`.
Let op: die container is **leeg** (geen tabellen/data). Vul hem eerst, anders geven de
datapagina's fouten ("relation ... does not exist"):
```bash
# tabellen + dummy-data (vlak schema):
python scripts/generate_dummy_data.py --sql-only | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"
```
Voor de chat is een read-only rol nodig (zie [CLAUDE.md](CLAUDE.md) → "Lokale ontwikkeling").

> Zonder een database met het juiste schema draait de app wél, maar geven de datapagina's fouten.
> "Geen fouten" hangt dus af van een correct gekoppelde, gevulde database.

## 4. Bouwen voor ARM64

De `Dockerfile` is multi-stage (Node-build → Python-runtime) en bouwt schoon op ARM64 (geverifieerd
via een `linux/arm64` cross-build). Twee manieren:

**Op het apparaat zelf:**
```bash
docker compose up -d --build
```
Werkt, maar de frontend-build (npm + vite) is zwaar op een EMMC/ARM-device; reken op enkele minuten.

**Sneller: elders cross-builden en overzetten** (aanrader voor productie):
```bash
# op een dev-machine / CI:
docker buildx build --platform linux/arm64 --build-arg APP_COMMIT=$(git rev-parse --short HEAD) \
  -t optimax:latest --output type=docker,dest=optimax-arm64.tar .
# overzetten en op het apparaat laden:
docker load -i optimax-arm64.tar
docker compose up -d           # zonder --build
```

## 5. Verifiëren na deploy

```bash
curl -s http://localhost:8080/api/health   | jq   # status healthy, db_pool gevuld
curl -s http://localhost:8080/api/version  | jq   # versie + commit
docker ps                                         # dashboard = healthy (healthcheck)
```
Open daarna `http://<device-ip>:8080` en controleer een datapagina (Overzicht/Productie).

## 6. Checklist "wat moet er nog gebeuren"

- [ ] `.env` aanmaken en invullen (DB verplicht).
- [ ] DB-keuze maken (echte DGS-DB of meegeleverde db vullen).
- [ ] Bij meegeleverde db: schema + (dummy-)data laden, `chat_readonly`-rol aanmaken.
- [ ] Beslissen over `DASHBOARD_AUTH_*` (toegangsbeveiliging op het netwerk).
- [ ] Chat: `OPENROUTER_API_KEY` + TLS-aanpak (`CHAT_CA_BUNDLE` achter SSL-inspectie).
- [ ] Image bouwen (op device of cross-build + load).
- [ ] Healthcheck/monitoring: eventueel `scripts/healthcheck_alert.py` op cron.
- [ ] Logs-volume (`./logs`) schrijfbaar; rotatie staat ingesteld (5 MB × 5).

## Bekende aandachtspunten

- De app is een **read-consumer** van de DB; de PLC → Node-RED → Postgres-pijplijn staat buiten
  deze repo en moet draaien voor live data.
- In-process cache/rate-limit zijn per-proces; draai voorlopig **één** worker (de default CMD).
- Auth is een minimale Basic-gate; voor echte beveiliging hoort SSO/reverse-proxy.
