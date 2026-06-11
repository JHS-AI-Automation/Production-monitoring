# Optimax demo op de SecureEdge: overdracht voor de IXON-beheerder

Voor wie **IXON Edge App Management-rechten** heeft op de "DGS R&D Logger" (SecureEdge Pro,
`192.168.23.254`). Alles is voorbereid; dit is alleen nog de installatie-stap (paar minuten).

## Context (kort)
Dit is een **demo** van het Optimax productie-/alarmdashboard, met **dummy-data** (geen echte
monitoring). Het draait als twee containers op de SecureEdge. De images staan al klaar in de
lokale registry van het apparaat:

- `192.168.23.254:5000/optimax-db:latest` — Postgres met ~3 maanden dummy-data (seedt zichzelf bij eerste start)
- `192.168.23.254:5000/optimax:latest` — het dashboard (secret-vrije image; config via env-vars)

## Wat te doen
Installeer een Edge App met de twee containers uit `docker-compose.edgeapp.yml` (in deze repo).
Belangrijke instellingen:

**Container 1 — optimax-db**
- Image: `192.168.23.254:5000/optimax-db:latest`
- Netwerk: `machine-builder`
- Volume: `optimax-db-data` -> `/var/lib/postgresql/data`
- Geen gepubliceerde poort
- Start als eerste; bij eerste start vult hij ~1-2 min lang de dummy-data.

**Container 2 — optimax** (start na optimax-db)
- Image: `192.168.23.254:5000/optimax:latest`
- Netwerk: `machine-builder` (zelfde, zodat hij `optimax-db` op naam vindt)
- Poort: `9000` -> `9000` (TCP)
- Volume: `optimax-logs` -> `/app/logs`
- Environment variables:
  ```
  DB_HOST=optimax-db
  DB_PORT=5432
  DB_NAME=db_dgs_01
  DB_USER=optimax
  DB_PASSWORD=optimax_demo
  DASHBOARD_AUTH_USER=dgs
  DASHBOARD_AUTH_PASSWORD=<door Jasper aan te leveren>
  LOG_FORMAT=json
  LOG_LEVEL=INFO
  ```

## Controleren
- `curl http://192.168.23.254:9000/api/health` -> `"status":"healthy"`, `db_pool` gevuld.
- Browser: `http://192.168.23.254:9000`, inloggen met `dgs` + het wachtwoord. Datapagina's tonen
  dummy-cijfers op een datum binnen de afgelopen ~3 maanden.

## Aandachtspunten
- Demo met dummy-data; niet verwarren met echte productie-monitoring.
- Tweede Postgres naast de bestaande; RAM op de IX6000 is beperkt (~2-3 GB voor Docker), maar
  deze dataset is licht. Eigen volume (`optimax-db-data`), raakt de bestaande DB niet.
- Voor de echte (live-data) productieversie volgt later een aparte stap (views over de ruwe
  tabellen of nette tabellen op de live-DB); dit is bewust eerst de demo.

## Alternatief: rechten geven
In plaats van zelf installeren kun je ook Jasper (of Uland AI) tijdelijk Edge App Management-rechten
geven op dit apparaat; dan ronden wij het zelf af.
