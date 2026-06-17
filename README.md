# DGS Optimax

Optimax: interactief productie- en alarmdashboard voor de DGS-fabriek. Leest uit dezelfde PostgreSQL database als het bestaande alarm-report, maar biedt een interactieve UI in plaats van een dagelijkse e-mail.

**Features:**
- **Overzicht** met KPI-kaarten, OEE, top-alarmen bar chart en severity pie chart
- **Alarmen** doorzoekbare lijst met filters (severity, zoektekst), paginering en openstaande alarmen
- **Productie** dag-KPI's, OEE per lijn, lijnverdeling-diagram en alarm-impact
- **Pallets** bezettingsgraad per station (status 100/200/300) en per uur
- **Trends** alarmen per dag (7/14/30 dagen)
- **Chat** natuurlijke-taal vragen over de data (LLM vertaalt naar read-only SQL)

> Voor architectuur, dataflow, pool-model en schaalbaarheid: zie [ARCHITECTURE.md](ARCHITECTURE.md).
> Waarom Optimax lokaal op een edge-device draait en niet volledig in de cloud: zie [ADR-001](ADR-001-deployment-edge-vs-cloud.md).
> Openstaand werk, backlog en projectnotities: interne werkmap `docs-intern/` (lokaal, bewust niet in git).

---

## Voorbereiding

Kopieer het voorbeeld-bestand en vul de database credentials in:

```bash
cp .env.example .env
```

De database-instellingen zijn identiek aan die van het alarm-report (`192.168.23.254`, `db_dgs_01`).

---

## Draaien met Docker (aanbevolen)

**Vereisten:** Docker Desktop geinstalleerd en draaiend.

```bash
docker compose up --build
```

Open `http://localhost:8080` (of `http://<machine-ip>:8080` vanuit het netwerk).

---

## Lokaal ontwikkelen

**Vereisten:** Python 3.12+, Node.js 20+

### Backend

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8080
```

### Frontend (aparte terminal)

```bash
cd frontend
npm install
npm run dev
```

De Vite dev server draait op `http://localhost:5173` en proxied `/api` naar de backend op poort 8080.

---

## Lokaal met een nep-database

Voor ontwikkelen zonder VPN naar de DGS-fabriek draait er een **nep-database in Docker** die
de productie-database nabootst. Productie gebruikt **per-dag gepartitioneerde tabellen**
(RANGE op `time`), dus de lokale prod-spiegel doet dat ook.

```bash
# 1. Prod-spiegel starten (gepartitioneerd, poort 5434) of de simpele dev-DB (poort 5433)
#    De prod-spiegel container heet dgs-db-local.

# 2. Partitie-bewust seeden (maakt dagpartities + vult alarms/capacity/pallets + indexen)
python scripts/seed_partitioned.py --days 14 --clear > seed.sql
docker exec -i dgs-db-local psql -U dgs -d db_dgs_01 < seed.sql

# 3. .env naar de nep-DB wijzen (DB_HOST=localhost, DB_PORT=5434, DB_USER=dgs) en starten
uvicorn backend.main:app --reload --port 8080
```

- `scripts/seed_partitioned.py` is voor de **gepartitioneerde** prod-spiegel.
- `scripts/generate_dummy_data.py` is voor een **vlakke** dev-DB (geen partities).
- Beide gebruiken statuscodes 100/200/300 voor pallets (matcht de queries).

Voor de chat is een aparte read-only rol nodig (zie env-variabelen hieronder):

```sql
CREATE ROLE chat_readonly LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE db_dgs_01 TO chat_readonly;
GRANT USAGE ON SCHEMA public TO chat_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO chat_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO chat_readonly;
```

---

## Environment-variabelen

Zie `.env.example`. Belangrijkste:

| Variabele | Doel |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Hoofd-databaseconnectie |
| `APP_PORT` / `APP_HOST` | Waar de app luistert |
| `DASHBOARD_AUTH_USER` / `DASHBOARD_AUTH_PASSWORD` | Optionele HTTP Basic Auth (beide leeg = uit) |
| `APP_COMMIT` | Git-commit voor `/api/version` (via `docker build --build-arg`) |
| `LOG_FORMAT` (`text`/`json`) / `LOG_LEVEL` | Logging |
| `OPENROUTER_API_KEY` | Sleutel voor de chat-functie (leeg = chat uit) |
| `CHAT_MODEL` | LLM-model via OpenRouter (default `anthropic/claude-sonnet-4`) |
| `CHAT_DB_USER` / `CHAT_DB_PASSWORD` | Read-only DB-rol voor AI-SQL (leeg = chat deelt hoofd-pool) |
| `CHAT_TLS_VERIFY` | TLS naar OpenRouter (default `true`; `false` alleen achter SSL-inspectie) |
| `CHAT_CA_BUNDLE` | Pad naar bedrijfs-CA-bundle (aanbevolen alternatief voor `CHAT_TLS_VERIFY=false`) |

---

## Projectstructuur

| Map/Bestand | Doel |
|---|---|
| `backend/main.py` | FastAPI app, dient API + statische frontend, logging, lifespan |
| `backend/database.py` | Async PostgreSQL pool-factory + connectie (asyncpg) |
| `backend/config.py` | Settings uit environment variabelen |
| `backend/timewindow.py` | Gedeelde datum-validatie (`validate_date`/`validate_range`) |
| `backend/routers/alarms.py` | Alarm-endpoints: stats, top, list, trends, open |
| `backend/routers/production.py` | Productie-KPI's: summary, hourly, minutely, trends, alarm-impact, OEE |
| `backend/routers/pallets.py` | Palletstatus: summary, hourly |
| `backend/routers/chat.py` | AI-chat: NL-vraag → read-only SQL → antwoord |
| `frontend/src/pages/` | Overview, AlarmList, Production, Pallets, Trends, Chat |
| `frontend/src/lib/` | Gedeelde helpers: `date.ts`, `format.ts`, `colors.ts` |
| `frontend/src/brand.ts` | Branding (kleuren, logo, namen) op één plek |
| `scripts/seed_partitioned.py` | Nep-data voor de gepartitioneerde prod-spiegel |
| `scripts/generate_dummy_data.py` | Nep-data voor een vlakke dev-DB |
| `scripts/load_test.py` | Load-test (gelijktijdige gebruikers, latency/throughput) |
| `Dockerfile` | Multi-stage build (Node + Python) |
| `docker-compose.yml` | Productie container setup |

## API Endpoints

| Methode | Pad | Omschrijving |
|---------|-----|--------------|
| GET | `/api/alarms/stats?date=YYYY-MM-DD` | KPI statistieken voor een dag |
| GET | `/api/alarms/top?date=YYYY-MM-DD&limit=10` | Top N alarmen op trigger count |
| GET | `/api/alarms/list?date=...&severity=Error&search=pomp&page=1` | Gefilterde, gepagineerde alarmenlijst |
| GET | `/api/alarms/open?date=YYYY-MM-DD` | Nog openstaande (niet-verholpen) alarmen |
| GET | `/api/alarms/trends?from=...&to=...` | Dagelijkse alarm counts voor trendgrafiek |
| GET | `/api/production/summary?date=...` | Dag-KPI's: totalen, stilstand, piekuur, lijn-balans, MTTR |
| GET | `/api/production/hourly?date=...` | Productie per lijn per uur |
| GET | `/api/production/minutely?date=...&hour=H` | Productie per minuut binnen een uur |
| GET | `/api/production/trends?from=...&to=...` | Dagelijkse productie-trend |
| GET | `/api/production/alarm-impact?date=...` | Productie tijdens vs zonder alarm + correlatie per uur |
| GET | `/api/production/oee?date=...` | OEE per lijn (Availability × Performance × Quality) |
| GET | `/api/pallets/summary?date=...` | Bezettingsgraad per palletstation |
| GET | `/api/pallets/hourly?date=...` | Bezettingsgraad (% klaar) per uur |
| POST | `/api/chat` `{"message": "..."}` | NL-vraag over de data (read-only SQL via LLM) |
| GET | `/api/health` | Gezondheidscheck (DB, versie, uptime, pool-stats) |
| GET | `/api/version` | Welke build draait (naam, versie, commit, starttijd) |
| GET | `/api/metrics` | In-process metrics (requests/fouten/latency per endpoint) als JSON |
| GET | `/api/metrics/prometheus` | Zelfde metrics in Prometheus-formaat (scrape-baar) |
| POST | `/api/client-log` | Frontend-foutrapportage (door de ErrorBoundary gebruikt) |

## Tests

```bash
pip install -r backend/requirements-dev.txt
pytest          # unit + API-tests; DB-tests worden overgeslagen als de nep-DB niet draait
```

## Observability & operatie

- **Logs:** JSON met een `request_id` per verzoek (ook in de `X-Request-ID` response-header) -
  zie [RUNBOOK.md](RUNBOOK.md) voor diagnose en veelvoorkomende problemen.
- **Metrics/health/versie:** de endpoints hierboven; `/api/health` voedt de Docker-healthcheck.
- **Alerting:** `scripts/healthcheck_alert.py` (cron, webhook) meldt als de app ongezond is.
- **Optionele stack:** `docker compose -f docker-compose.observability.yml up -d` (Prometheus +
  Loki + Promtail + Grafana, kant-en-klaar geconfigureerd).

## Troubleshooting

### Database niet bereikbaar

- Controleer of je op het DGS-netwerk zit (192.168.23.x)
- Ping de DB: `ping 192.168.23.254`
- Controleer `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` in `.env`
- Bij Docker: gebruik `host.docker.internal` als `DB_HOST` als de DB op de host draait
