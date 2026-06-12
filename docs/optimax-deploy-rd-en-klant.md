# Optimax deploy-stappenplannen: R&D-logger en klant-go-live

Twee stappenplannen naast elkaar: (1) de demo op de DGS R&D-logger afronden en (2) de echte deploy bij een klant, inclusief het per-klant-model (eigen OpenRouter-account dat je opwaardeert + eigen database per klant). Juni 2026.

## Het per-klant-model (de afspraak)

Elke klant krijgt zijn eigen, gescheiden setje:

- **Eén eigen OpenRouter-account per klant.** Daarop zet je prepaid tegoed en waardeer je periodiek op. Voordelen: de chatkosten per klant zijn exact zichtbaar (door te belasten), een uitgelekte sleutel raakt alleen die ene klant, en op = op (het tegoed is zelf de harde kostengrens, bovenop het dagelijkse token-budget in de app).
- **Eén eigen database per klant.** Dit volgt vanzelf uit het edge-model: elke klant heeft zijn eigen logger met zijn eigen PostgreSQL erop. De regel die ertoe doet: **nooit** wachtwoorden, sleutels of rollen hergebruiken tussen klanten. Per klant verse database-rollen, verse dashboard-login, verse OpenRouter-sleutel.
- **Per-klant administratie:** houd per klant een (niet in git getrackt) overzicht bij met router-IP, accountnamen en waar de wachtwoorden staan (wachtwoordmanager), plus de stand van het OpenRouter-tegoed. Secrets zelf nooit in git of in dit document.

---

## Stappenplan 1: R&D-logger (DGS SecureEdge, demo met dummy-data)

Doel: de demo zichtbaar krijgen op `http://192.168.23.254:9000`. De images staan al in de registry van het apparaat; de enige blokkade is het aanmaken van de containers.

### De rechten-situatie (status juni 2026, eerst dit oplossen)

**Jasper heeft op dit moment NIET de juiste IXON-rechten.** In IXON Cloud is het Edge-app-/containerbeheer voor de "DGS R&D Logger" niet zichtbaar of klikbaar. Belangrijk om het onderscheid te snappen:

- **De registry-push werkt al** (bewezen: beide images staan erop). De registry op poort 5000 staat open op het LAN/VPN en vereist geen IXON-rechten.
- **Het aanmaken van containers is de geblokkeerde stap.** Daarvoor is één van deze drie routes nodig:

| Route | Wat is er nodig | Wie regelt het |
|---|---|---|
| **1. Rechten krijgen (voorkeur)** | De **Edge App Management-module** moet actief zijn in de IXON-company van DGS, en Jasper moet als gebruiker toegang krijgen tot Studio > Developer > Edge Apps voor dit apparaat. Aanvragen bij de IXON-beheerder van DGS. | DGS IXON-beheerder |
| **2. Beheerder installeert** | De beheerder die de rechten al heeft voert stap 2-3 hieronder zelf uit; alles staat klaar in [optimax-ixon-handover.md](optimax-ixon-handover.md) (paar minuten werk). | DGS IXON-beheerder, met onze handover |
| **3. Lokale Docker-API** | Containers aanmaken kan ook buiten IXON Cloud om, via de lokale API van het apparaat (`POST /api/v1/docker/containers`). Vereist een access-token uit de lokale beheerpagina (`http://192.168.23.254:8080`); let op: zo'n token is 30 dagen geldig. Werkt alleen als Jasper wél op de lokale beheerpagina kan inloggen. | Jasper, mits lokale login |

> Concreet eerstvolgende actie: bij DGS (Marc/Tim of hun IXON-beheerder) vragen om route 1 of 2. Formuleer het als: "de twee app-pakketten staan al op het apparaat klaar; er hoeft alleen iemand met Edge App Management-rechten twee containers aan te maken volgens onze eenpagina-instructie."

### Waar staan we in de officiële IXON-flow (start guide / MVP)

De officiële IXON-route voor eigen Docker-apps op de SecureEdge Pro bestaat uit deze stappen. Zo zie je precies wat al af is en wat nog moet:

| # | Stap uit de IXON-guide | Status bij ons |
|---|---|---|
| 1 | Docker-omgeving met buildx, ARM64-image bouwen (apparaat is linux/arm64v8) | KLAAR (build-script, ARM64 bevestigd) |
| 2 | Docker daemon: registry van het apparaat als insecure-registry instellen (eenmalig) | KLAAR |
| 3 | Image pushen naar de registry van het apparaat (`<router-ip>:5000`) | KLAAR (optimax + optimax-db staan erop) |
| 4 | Container aanmaken: via Edge App Management (Studio > Developer > Edge Apps) of de lokale Docker-API | **GEBLOKKEERD op rechten** (zie hierboven) |
| 5 | Poort/volume/netwerk/env-vars configureren bij het aanmaken | VOORBEREID (exacte waarden in de handover en in stap 2-3 hieronder) |
| 6 | Starten en controleren | Wacht op stap 4 |

Bron: [Edge Apps explained](https://developer.ixon.cloud/docs/what-is-an-edge-app) en [How to interact with Docker](https://developer.ixon.cloud/docs/secure-edge-api-docker) (IXON developer-docs).

**Stap 0: voorwaarden (eenmalig, grotendeels al gedaan)**

- [x] Router-IP bevestigd: `192.168.23.254` (registry antwoordt op `GET /v2/`)
- [x] Docker Desktop: `192.168.23.254:5000` als insecure-registry ingesteld
- [x] Images gebouwd (ARM64) en gepusht: `optimax-db:latest` (Postgres + 3 maanden dummy-data) en `optimax:latest` (dashboard, secret-vrij)
- [ ] IXON-VPN aan en routerend naar het apparaat
- [ ] **Rechten-blokkade opgelost** via route 1, 2 of 3 hierboven

**Stap 1: images verversen (alleen bij nieuwe code, ~10 min)**

```bash
./scripts/build-ixrouter.sh
```

Bouwt voor ARM64 en pusht naar `192.168.23.254:5000`. Achter SSL-inspectie (DGS-netwerk): eerst de bedrijfs-root-CA in `certs/` leggen en `INSTALL_CORP_CA=1` meegeven. Buiten het DGS-netwerk (hotspot/thuis) is dat niet nodig.

**Stap 2: database-container aanmaken (IXON-portaal, ~5 min)**

- Image `192.168.23.254:5000/optimax-db:latest`, netwerk `machine-builder`
- Volume `optimax-db-data` op `/var/lib/postgresql/data`, géén gepubliceerde poort
- Eerste start vult 1-2 minuten dummy-data; daarna pas stap 3 starten

**Stap 3: dashboard-container aanmaken (IXON-portaal, ~5 min)**

- Image `192.168.23.254:5000/optimax:latest`, zelfde netwerk `machine-builder` (vindt `optimax-db` dan op naam)
- Poort `9000` publiceren, volume `optimax-logs` op `/app/logs`
- Environment-variabelen (dít is waar de instellingen leven, het image is secret-vrij):

```text
DB_HOST=optimax-db          DB_PORT=5432        DB_NAME=db_dgs_01
DB_USER=optimax             DB_PASSWORD=optimax_demo
DASHBOARD_AUTH_USER=dgs     DASHBOARD_AUTH_PASSWORD=<sterk wachtwoord, 16+ tekens>
LOG_FORMAT=json             LOG_LEVEL=INFO
```

Voor de demo bewust GEEN `OPENROUTER_API_KEY`: de chat schakelt zichzelf dan netjes uit en er kunnen geen kosten ontstaan. Wil je de chat tóch demonstreren: gebruik een sleutel met klein prepaid tegoed en zet ook `CHAT_DB_USER`/`CHAT_DB_PASSWORD`.

**Stap 4: controleren (~5 min)**

- [ ] `curl http://192.168.23.254:9000/api/health` geeft `"status":"healthy"` met gevulde `db_pool`
- [ ] `curl http://192.168.23.254:9000/api/version` toont de verwachte commit
- [ ] Browser: login wordt afgedwongen, datapagina's tonen dummy-cijfers (kies een datum binnen de laatste ~3 maanden)

**Stap 5 (optioneel, latere fase): demo omzetten naar live-data**

Zelfde dashboard-container opnieuw aanmaken met andere env-vars: `DB_HOST=192.168.23.254` plus de echte read-only rollen. Vereist eerst: rollen aangemaakt op de live-DB (zie [CLAUDE.md](../CLAUDE.md)), en de timezone-probe gedraaid (`SELECT now(), max(time) FROM readstartstop3`, het open punt uit [TODO.md](../TODO.md) werkstroom 4). De demo-DB-container kan daarna weg; het volume `optimax-db-data` mag blijven of opgeruimd worden.

**Updaten (terugkerend):** nieuwe code = stap 1 opnieuw, daarna in het portaal de oude dashboard-container verwijderen en opnieuw aanmaken met dezelfde env-vars (volume `optimax-logs` hergebruiken). De database-container blijft gewoon staan.

---

## Stappenplan 2: echte deploy bij een klant (go-live)

Doel: Optimax in productie op de logger van een klant, op echte data, beheerd en betaald per klant. Reken op 1-2 dagdelen verspreid over een paar dagen (wachten op klant-IT zit er meestal tussen).

### Fase A: intake en netwerk (vóór er iets gebouwd wordt)

- [ ] **Logger-gegevens**: router-IP, bevestiging dat het een ARM64 SecureEdge is met genoeg vrije RAM (~600 MB voor Optimax) en schijfruimte
- [ ] **IXON-rechten vooraf geregeld** (de les van de R&D-logger: dit is de stap die weken kan kosten als je hem vergeet): is de Edge App Management-module actief in de IXON-company van de klant, en wie mag containers aanmaken? Regel vóór de installatie-dag dat wij die rechten hebben, of plan de installatie samen met de beheerder van de klant
- [ ] **Netwerk-tests vanaf de logger**: registry bereikbaar (`curl http://<router-ip>:5000/v2/`), database bereikbaar op 5432, en **uitgaand HTTPS naar `openrouter.ai`** (nodig voor de chat; corporate firewalls blokkeren dit soms, dan allowlisten of chat uit)
- [ ] **SSL-inspectie check** op het klant-netwerk: zo ja, root-CA opvragen voor de build (of buiten dat netwerk bouwen)
- [ ] **Bereikbaarheid afspreken**: dashboard alleen via LAN/VPN, niets open op internet (bevestiging klant-IT)
- [ ] **AVG-afspraak vastleggen**: dashboard is voor proces-/machine-inzicht, niet voor beoordeling van individuele medewerkers
- [ ] **Data-afspraken**: welke tabellen/kolommen, wat betekenen ze (kolom-mapping), wat zijn de shift-tijden. Dit voedt ook de vertaallaag (views) en de chat-fabriekskennis

### Fase B: accounts aanmaken (per klant, niets hergebruiken)

- [ ] **OpenRouter-account voor déze klant** aanmaken, prepaid tegoed erop (start bv. 10-25 euro), uitgavenlimiet instellen, één API-sleutel genereren. Sleutel direct in de wachtwoordmanager onder de klantnaam
- [ ] **Database-rollen (alleen-lezen)** op de klant-DB: de app-rol (`DB_USER`) en de chat-rol (`CHAT_DB_USER`), beide alleen `SELECT` op precies de tabellen die nodig zijn. SQL-voorbeeld: [CLAUDE.md](../CLAUDE.md) sectie "Chat read-only rol". Zodra het views-schema `optimax` bestaat: per rol één extra GRANT op dat schema
- [ ] **Dashboard-login**: sterke gedeelde login genereren (16+ tekens), in de wachtwoordmanager, alleen delen met wie toegang krijgt
- [ ] **Klant-administratie** aanmaken: één overzicht met router-IP, accountnamen, verwijzing naar wachtwoordmanager-items, OpenRouter-tegoedstand en opwaardeer-ritme

### Fase C: data-verificatie (de stap die je niet wilt overslaan)

- [ ] **Timezone-probe** op de klant-DB: `SELECT now(), max(time) FROM <meest recente tabel>`. Loopt `max(time)` 1-2 uur achter op de muurklok, dan schrijft de pipeline UTC en moeten de shift/piekuur-queries daarop afgestemd worden vóór go-live (anders kloppen de KPI's structureel niet)
- [ ] **Steekproef met de klant**: komen de tellers/alarmen in de database overeen met wat de klant op de machine ziet? Eén middag meelopen voorkomt maanden discussie over "het dashboard klopt niet"
- [ ] Bij beschikbare kolom-mapping: views aanmaken (schema `optimax`) en de GRANTs uit fase B zetten

### Fase D: bouwen en installeren

- [ ] Build-pc: insecure-registry `<router-ip>:5000` instellen (eenmalig), `.ixrouter.env` invullen met het klant-router-IP
- [ ] `./scripts/build-ixrouter.sh` (met `INSTALL_CORP_CA=1` indien SSL-inspectie)
- [ ] Container aanmaken in het IXON-portaal: poort `9000`, volume `optimax-logs` op `/app/logs`, netwerk `machine-builder`, en de env-vars met de fase-B-waarden:

```text
DB_HOST=<klant-db>          DB_PORT=5432        DB_NAME=<klant-db-naam>
DB_USER=<app-rol>           DB_PASSWORD=<...>
CHAT_DB_USER=<chat-rol>     CHAT_DB_PASSWORD=<...>
OPENROUTER_API_KEY=<klant-sleutel>
DASHBOARD_AUTH_USER=<...>   DASHBOARD_AUTH_PASSWORD=<...>
LOG_FORMAT=json             LOG_LEVEL=INFO
```

Het image is secret-vrij: alle klant-specifieke waarden leven alleen in deze container-configuratie. `MAINTENANCE_ENABLED` weglaten (de maintenance-module blijft uit tot die op echte data staat).

### Fase E: verificatie en go-live-checklist

- [ ] `/api/health` healthy, `/api/version` toont de bedoelde commit
- [ ] Login afgedwongen; fout wachtwoord 10x = tijdelijke blokkade (lockout werkt)
- [ ] KPI-sanity met de klant: productie-aantallen en alarmen van gisteren naast de eigen administratie leggen
- [ ] Chat: stelt read-only vragen, toont SQL + data, en de kosten verschijnen op het klant-OpenRouter-account
- [ ] Datumgrens-check rond middernacht doorstaan (timezone, fase C)
- [ ] **Thomas-ratificatie**: go-live bij een klant valt onder de klant-uitlevering-regel; Thomas keurt vóór livegang

### Fase F: monitoring en nazorg

- [ ] **Minimaal bij elke klant** (uit [optimax-monitoring-opties.md](optimax-monitoring-opties.md)): self-heal staat al aan (healthcheck + restart), IXON device-offline-alarm aanzetten in het portaal, en een heartbeat (Node-RED pingt elke 5 min een externe check-dienst; stopt het pingen = alarm). Egress voor het heartbeat-domein vooraf testen
- [ ] **Beheer-afspraken**: wie de gedeelde login beheert, wie updates uitvoert (nieuwe image push + container re-create), en het opwaardeer-ritme van het OpenRouter-tegoed (bv. maandelijks checken; de chat meldt zelf vriendelijk wanneer het dagbudget op is)
- [ ] **Overdracht**: [RUNBOOK.md](../RUNBOOK.md) delen met wie het dagelijks beheer doet

### De verschillen in één oogopslag

| | R&D-logger (demo) | Klant (productie) |
|---|---|---|
| Data | Dummy (eigen Postgres-container) | Echte klant-DB op de logger |
| Chat | Uit (geen sleutel) | Aan, eigen klant-OpenRouter-account met prepaid tegoed |
| DB-rollen | Demo-credentials | Verse read-only rollen, per klant |
| Timezone-probe | Niet nodig | Verplicht vóór go-live |
| Monitoring | Niet nodig | IXON-alarm + heartbeat minimaal |
| Goedkeuring | Niet nodig | Thomas-ratificatie vóór go-live |

## Bronnen

- Build-detail en registry-werking: [DEPLOY-ixrouter.md](../DEPLOY-ixrouter.md)
- Demo-overdracht aan de IXON-beheerder: [optimax-ixon-handover.md](optimax-ixon-handover.md)
- Accounts/rollen-detail en go-live-voorwaarden: [INSTALLATIE-KLANT.md](../INSTALLATIE-KLANT.md)
- Monitoring-keuzehulp: [optimax-monitoring-opties.md](optimax-monitoring-opties.md)
- Dagelijks beheer en troubleshooting: [RUNBOOK.md](../RUNBOOK.md)
