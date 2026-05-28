# DGS Optimax

## Project

Optimax: interactief productie- en alarmdashboard voor DGS productielijn. FastAPI backend + React frontend.
Database: `db_dgs_01` op `192.168.23.254:5432` (DGS intern netwerk, bereikbaar via Ixon VPN-tunnel).

## MCP Server

De `dgs-postgres` MCP server geeft Claude read-only SQL-toegang tot de database.
Connection string staat in `.env` als `DGS_DB_CONNECTION_STRING`.

## Database Schema (db_dgs_01)

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
- `counter0` (int): productieteller Lijn 1 (overflow)
- `counter1` (int): productieteller Lijn 2 (invoer)
- `counter2` (int): productieteller Lijn 3 (invoer)
- `counter3` (int): productieteller Lijn 4 (overflow)

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

## Security

- MCP server: alleen SELECT-queries. Geen INSERT, UPDATE, DELETE, DROP.
- Database user: read-only account (credentials in `.env`, niet in repo)
