# DGS Optimax

## Project

Optimax: interactief productie- en alarmdashboard voor DGS productielijn. FastAPI backend + React frontend.
Database: `db_dgs_01` op `192.168.23.254:5432` (DGS intern netwerk, bereikbaar via Ixon VPN-tunnel).

## MCP Server

De `dgs-postgres` MCP server geeft Claude read-only SQL-toegang tot de database.
Connection string staat in `.env` als `DGS_DB_CONNECTION_STRING`.

## Database Schema (db_dgs_01)

**Partitionering:** productie (en de lokale prod-spiegel) gebruikt RANGE-partities **per dag**
op `time` (`plc_alarms_YYYYMMDD`, `capacity_perminutev2_YYYYMMDD`, etc.). Filter daarom altijd
sargable: `WHERE time >= $1::date AND time < $1::date + 1` (NIET `WHERE time::date = $1`, dat
breekt partition pruning en index-gebruik). Index op `time` staat op elke partitioned parent.

### Bevestigde tabellen

**plc_alarms** (hoofdtabel, gebruikt door de backend API)
- `time` (timestamp): moment dat het alarm optrad
- `incomingstate` (int 0/1): 1 = alarm geactiveerd, 0 = alarm verholpen
- `alarmmessage` (text): beschrijving van het alarm
- `severityclass` (varchar): ernst-niveau (Error, Warning, Info)

**plc_alarms_mp1** (alarmen specifiek voor MP1 machine, meer kolommen)
- `time` (timestamp): moment dat het alarm optrad
- `alarmid` (int): numeriek alarm-ID
- `alarmmessage` (text): beschrijving van het alarm
- `severityclass` (varchar): ernst-niveau
- `incomingstate` (int 0/1): 1 = actief, 0 = verholpen
- `eventid` (varchar hex): unieke event identifier

**capacity_perminutev2** (productie-tellers per minuut)
- `time` (timestamp): meetmoment
- `counter0` (int): productieteller Lijn 1 (robot legt af)
- `counter1` (int): productieteller Lijn 2 (overflow, rest na robot)
- `counter2` (int): productieteller Lijn 3 (overflow, rest na robot)
- `counter3` (int): productieteller Lijn 4 (robot legt af)

  Model: lijn 1 en 4 tellen wat de robot aflegt; lijn 2 en 3 zijn de overflow die daarna overblijft.

  **Open punt:** achter de overflow zit nog een teller (na lijn 2/3) die nog uit het DB-schema
  bepaald moet worden. In het ProductionFlowDiagram staat hiervoor een gestippeld "n.t.b."-blok.
  Kandidaat om te onderzoeken: de tabel `capacity_detected` (bestaat in db_dgs_01, gepartitioneerd
  per dag, nog niet gebruikt door de backend).

**palletstatus** (palletposities op 4 stations)
- `time` (timestamp): meetmoment
- `pallet6000` (int): status palletstation 6000 (100=geen pallet, 200=leeg, 300=klaar)
- `pallet6005` (int): status palletstation 6005
- `pallet6010` (int): status palletstation 6010
- `pallet6015` (int): status palletstation 6015

### Verwachte tabellen

- `machines` (id, name, line_id, type/location)
- `production_lines` (id, name)

### Toekomstig (niet beschikbaar)

- `sensor_data` (ES-lijn: stroom, spanning, frequentie, stuitering) - black box, data niet beschikbaar
- `maintenance_log` (storingsregistraties) - geen data beschikbaar bij klant

## Datakenmerken

- Sample rate: elke 250ms (robot moving, PLC alarms)
- Batchwrites: minimaal elke 100ms
- Shift: 18 uur per dag
- Retentie: 90 dagen
- Machines: slachtlijn, OSI, Kepak (robot-packer), filetmachine/robot

## Infrastructuur

- Server: Linux ARM64 V8, Secure-edge pro, 32GB EMMC
- Docker containers: PostgreSQL, Node-RED, Grafana, Adminer
- PLC host: OPC UA server, data via Node-RED naar PostgreSQL
- Remote toegang: Ixon VPN

## Lokale ontwikkeling (nep-DB in Docker)

Twee opties, beide zonder VPN:

- **Prod-spiegel (gepartitioneerd), poort 5434, container `dgs-db-local`** — meest representatief.
  Seeden: `python scripts/seed_partitioned.py --days 14 --clear > seed.sql` daarna
  `docker exec -i dgs-db-local psql -U dgs -d db_dgs_01 < seed.sql`.
- **Vlakke dev-DB, poort 5433** (`docker-compose.dev.yml`) — `python scripts/generate_dummy_data.py > seed.sql`
  daarna `docker exec -i <dev-container> psql -U dgs_dev -d dgs_dev < seed.sql` (het script print
  altijd SQL naar stdout; de directe psycopg2-insertroute is vervallen).

Beide schrijven palletstatus als 100/200/300 (matcht de queries). `.env` wijst lokaal naar de
gekozen poort (auth in de container is `trust`, dus wachtwoord-waarde maakt lokaal niet uit).

**Chat read-only rol** (nodig voor de chat, los van de hoofd-pool):

```sql
CREATE ROLE chat_readonly LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE db_dgs_01 TO chat_readonly;
GRANT USAGE ON SCHEMA public TO chat_readonly;
-- Least privilege (SEC-05): alleen de 4 tabellen die de chat nodig heeft, NIET alle tabellen.
GRANT SELECT ON plc_alarms, plc_alarms_mp1, capacity_perminutev2, palletstatus TO chat_readonly;
-- Bewust GEEN "GRANT SELECT ON ALL TABLES" en GEEN "ALTER DEFAULT PRIVILEGES": anders kan de
-- chat ook nieuwe/andere tabellen lezen. Voeg een tabel hier handmatig toe als de chat hem nodig heeft.
```

Zet daarna `CHAT_DB_USER` / `CHAT_DB_PASSWORD` in `.env`. Load-test: `python scripts/load_test.py --users 5`.

> **Hoofd-DB-rol read-only (SEC-06 mitigatie).** Het edge-image is secret-vrij (config via
> env-vars bij container-creatie in het IXON-portaal), maar een gelekt DB-wachtwoord moet alsnog
> zo min mogelijk schade kunnen aanrichten.
> Geef de hoofd-`DB_USER` daarom OOK alleen SELECT-rechten op de 4 tabellen (de app schrijft nooit):
> ```sql
> GRANT CONNECT ON DATABASE db_dgs_01 TO <DB_USER>;
> GRANT USAGE ON SCHEMA public TO <DB_USER>;
> GRANT SELECT ON plc_alarms, plc_alarms_mp1, capacity_perminutev2, palletstatus TO <DB_USER>;
> -- geen INSERT/UPDATE/DELETE/DDL.
> ```
> Verifieer dit op de echte DGS-DB. Node-RED gebruikt een andere (schrijf-)rol; die deelt Optimax niet.

## Security

- MCP server: alleen SELECT-queries. Geen INSERT, UPDATE, DELETE, DROP.
- Database user: read-only account (credentials in `.env`, niet in repo)
- Chat: aparte read-only rol via `CHAT_DB_USER`/`CHAT_DB_PASSWORD` (niet hardcoded), SQL-sanitizer (alleen SELECT + LIMIT), per-IP rate-limit, concurrency-semafoor.
- TLS naar OpenRouter: veilig by default; `CHAT_CA_BUNDLE` of (laatste redmiddel) `CHAT_TLS_VERIFY=false`.
