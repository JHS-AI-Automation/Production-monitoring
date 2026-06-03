# RUNBOOK — DGS Optimax

Operationele gids voor wie het dashboard draaiend houdt en problemen diagnosticeert.
Voor de architectuur: zie [ARCHITECTURE.md](ARCHITECTURE.md).

## Snel statuscheck

| Wat | Hoe | Gezond resultaat |
|---|---|---|
| Draait de app + DB? | `GET /api/health` | `200` met `"status":"healthy"`, `db_pool` gevuld |
| Welke build draait? | `GET /api/version` | naam, versie, commit, starttijd |
| Hoe druk / hoeveel fouten? | `GET /api/metrics` | requests/fouten per endpoint, latency, pool-gebruik |

```bash
curl -s http://localhost:8080/api/health | jq
curl -s http://localhost:8080/api/metrics | jq
```

`/api/health` geeft `503` als de database onbereikbaar is. De app blijft dan draaien
(de pagina's tonen nette foutmeldingen), maar levert geen data tot de DB terug is.

## Logs lezen

- **Locatie:** `logs/dashboard.log` (JSON, roteert bij 5 MB, 5 bestanden bewaard). In Docker
  ook via `docker compose logs dashboard` (in productie staat `LOG_FORMAT=json`).
- **Request-correlatie:** elke regel heeft een `request_id`. Datzelfde id staat in de
  `X-Request-ID` response-header en, bij een 500, in de response-body. Vraag een gebruiker dus
  om het request-id (of pak het uit de netwerk-tab) en grep erop:

```bash
grep '"request_id": "ab12cd34ef56"' logs/dashboard.log
```

- **Niveaus:** `LOG_LEVEL` (default `INFO`). Fouten (`ERROR`) bevatten het type en de traceback.
  4xx/5xx-responses worden als `WARNING` gelogd met methode, pad, status en duur.

## Veelvoorkomende problemen

| Symptoom | Waarschijnlijke oorzaak | Actie |
|---|---|---|
| Pagina toont "failed to fetch" | Backend draait niet / niet bereikbaar | Check `GET /api/health`; herstart de container/uvicorn; check poort 8080 |
| `/api/health` = 503 | DB onbereikbaar (VPN, DB down) | Check VPN/`192.168.23.x`; `db_pool` is `null` in health; herstart pas zinvol na DB-herstel |
| Alle pagina's leeg, geen fout | Geen data voor de gekozen datum | Kies een datum met data; default = gisteren |
| Chat geeft 503 | `OPENROUTER_API_KEY` ontbreekt | Zet de sleutel in `.env` (rest van het dashboard werkt gewoon door) |
| Chat geeft 500 / "Connection error" | TLS naar OpenRouter faalt (SSL-inspectie) | Zet `CHAT_CA_BUNDLE` naar de bedrijfs-CA, of tijdelijk `CHAT_TLS_VERIFY=false` |
| Chat geeft 429 | Rate-limit (30/min per IP; kantoor-NAT deelt dit) | Even wachten; structureel: `RATE_LIMIT_MAX` verhogen in `chat.py` |
| Pool-gebruik (`in_use`) zit tegen `max_size` | Veel gelijktijdige zware queries | `max_size` verhogen in `database.py`, of query-load spreiden |
| Wit scherm in de browser | Onverwachte UI-fout | De ErrorBoundary toont normaal een melding; check browser-console (F12) en herlaad |

## Herstarten

- **Docker (productie):** `docker compose restart dashboard` (de container heeft een healthcheck;
  `docker ps` toont `healthy`/`unhealthy`). Bij codewijziging: `docker compose up -d --build`.
- **Lokaal:** stop uvicorn (Ctrl+C) en start opnieuw, of zie [README](README.md) → Lokaal met nep-DB.

## Deploy-verificatie

Na een deploy: `GET /api/version` controleren (commit/versie), daarna `GET /api/health` (200) en
een steekproef op een datapagina. `APP_COMMIT` kan via de build worden meegegeven zodat
`/api/version` de exacte commit toont.

## Toegangsbeveiliging (optioneel)

HTTP Basic Auth is env-gated en standaard **uit**. Zet `DASHBOARD_AUTH_USER` én
`DASHBOARD_AUTH_PASSWORD` om alle routes achter een login te zetten (behalve `/api/health`,
dat vrij blijft voor de container-healthcheck). Dit is een minimale gate; voor productie is
SSO of proxy-auth de betere keuze.

## Alerting

`scripts/healthcheck_alert.py` pollt `/api/health` en stuurt een melding naar een webhook als de
app onbereikbaar/ongezond is. Draai het buiten de app (cron/scheduled task):

```bash
ALERT_WEBHOOK_URL=https://... python scripts/healthcheck_alert.py --url http://localhost:8080
```

## Observability-stack (optioneel)

```bash
docker compose -f docker-compose.observability.yml up -d
```

Brengt Prometheus (scrapet `/api/metrics/prometheus`), Loki + Promtail (leest de JSON-logs) en
Grafana (http://localhost:3000, datasources al ingericht) omhoog. Kant-en-klaar geconfigureerd.

## Tests

```bash
pip install -r backend/requirements-dev.txt
pytest          # DB-tests worden overgeslagen als de nep-DB niet draait
```

## Belangrijke configuratie (zie `.env.example`)

- DB: `DB_HOST/PORT/NAME/USER/PASSWORD` (verplicht, fail-fast bij ontbreken).
- App: `APP_PORT/HOST`, `DASHBOARD_AUTH_USER/PASSWORD` (optionele auth), `APP_COMMIT` (build).
- Logging: `LOG_FORMAT` (`text`/`json`), `LOG_LEVEL`.
- Chat: `OPENROUTER_API_KEY`, `CHAT_MODEL`, `CHAT_DB_USER/PASSWORD`, `CHAT_TLS_VERIFY`, `CHAT_CA_BUNDLE`.
