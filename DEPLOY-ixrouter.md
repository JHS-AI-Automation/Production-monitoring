# Optimax draaien op de IXrouter5 ("de logger")

Stap-voor-stap, in gewone taal. De IXrouter5 is een ARM64 edge-router met een eigen
Docker-"app-winkel" (registry) en een beheerpagina in de browser.

> **Bevestigd (IXON developer-docs, juni 2026):** de SecureEdge Pro host een insecure
> Docker-registry op **poort 5000**, default device-IP **`192.168.140.1`**. Je pusht je
> ARM64-image daarheen, en maakt er een container van via de beheerpagina of de Docker-API
> (`POST /api/v1/docker/containers`, starten via `/api/v1/docker/containers/<naam>/start`),
> op het `machine-builder`-netwerk. De registry-aanpak in deze gids is dus de officiele methode.
> Bron: developer.ixon.cloud/docs/secure-edge-api-docker.

## Wat moet er nog gebeuren (status 2026-06-09)

De code-kant is klaar; dit zijn de openstaande stappen voordat Optimax op de logger draait:

- [ ] **Bedrijfs-root-CA** in `certs/` leggen + `INSTALL_CORP_CA=1` in `.ixrouter.env`
      (nodig om op het DGS-netwerk te bouwen achter SSL-inspectie). Het root-certificaat is
      openbaar; vraag IT om "de root-CA van onze SSL-inspectie als .crt/.pem", of exporteer
      hem via de browser (slotje op pypi.org -> certificeringspad -> root -> Base-64 exporteren).
- [x] **Router-IP bevestigd: `192.168.23.254`** (registry `GET /v2/` -> `{}`). Staat ingevuld in
      `.ixrouter.env` en `buildkitd-ixrouter5.toml`. (Niet `192.168.140.1`, dat was de IXON-default.)
- [ ] **Docker `insecure-registries`** op `<router-ip>:5000` zetten (Docker Desktop -> Settings ->
      Docker Engine -> toevoegen -> Apply & Restart).
- [ ] **IXON-VPN actief en routerend** naar de SecureEdge (registry :5000) en de DB
      (`192.168.23.254:5432`). Snelle test: `curl http://<router-ip>:5000/v2/` (verwacht 200 of 401).
- [ ] **Bouwen + pushen:** `INSTALL_CORP_CA=1 ./scripts/build-ixrouter.sh` (de `INSTALL_CORP_CA` alleen als de CA er is).
- [ ] **Container aanmaken** in de beheerpagina (of via de API): image `optimax`, poort **9000**,
      named volume `optimax-logs` -> `/app/logs`, netwerk `machine-builder`.
- [ ] **Verifieren:** `curl http://<router-ip>:9000/api/health` -> `healthy`; daarna de UI openen op `http://<router-ip>:9000`.

Al klaar: app + config-baked Dockerfile, build/push-script, healthcheck, CA-mechanisme (default uit),
en `.ixrouter.env` met DB- en OpenRouter-waarden (gitignored, niet gedeeld).

## Hoe het werkt (kort)

1. Je bouwt op je eigen pc een app-pakket (Docker-image) en **upload** dat naar de winkel van
   de router (`<router-ip>:5000`).
2. Op de **beheerpagina** (`<router-ip>:8080`) maak je daar een draaiend exemplaar (container) van.
3. Instellingen (database-adres, wachtwoorden, OpenRouter-sleutel) geef je op als
   **environment-variabelen bij het aanmaken van de container** (IXON-portaal / Edge App Management).
   Het pakket zelf is daardoor **secret-vrij**. Wijzig je een instelling, dan maak je de container
   opnieuw aan met de nieuwe env-waarden; opnieuw bouwen is niet nodig.
4. De router draait op een **ARM64/v8-chip**; we bouwen expliciet daarvoor (anders: "exec format error").

> Waarom niet inbakken: de winkel (registry, poort 5000) staat open op het lokale netwerk en een
> image is uitleesbaar met `docker history`/`docker inspect`. Ingebakken wachtwoorden zou iedereen
> op het netwerk kunnen terugzien. Env-vars bij container-creatie blijven binnen het afgeschermde
> IXON-beheer.

## Eenmalige voorbereiding (op je eigen pc)

1. Zorg dat Docker met **buildx** draait (Docker Desktop heeft dit).
2. Vertel Docker dat de router-winkel via HTTP mag. Voeg in `/etc/docker/daemon.json` toe
   (vervang het IP door dat van jullie router) en herstart Docker:
   ```json
   { "insecure-registries": ["192.168.140.1:5000"] }
   ```
   (Op Windows/Docker Desktop: Settings → Docker Engine → dit toevoegen → Apply & Restart.)
3. Kopieer `.ixrouter.env.example` naar `.ixrouter.env` en vul de build-instellingen in
   (router-IP, poort, eventueel CA). De app-config en secrets horen hier NIET meer in;
   die geef je op bij het aanmaken van de container (zie hieronder).

## Let op: bouwen achter SSL-inspectie

Sommige bedrijfsnetwerken (waaronder dit) doen **SSL-inspectie**: ze onderscheppen HTTPS met een
eigen certificaat. Tijdens de build haalt `pip` Python-pakketten van `pypi.org`; die TLS-verificatie
faalt dan met `CERTIFICATE_VERIFY_FAILED` en de build stopt. Connectiviteit is prima, alleen het
certificaat wordt niet vertrouwd. Oplossingen (kies er één):

1. **Bouw op een netwerk zonder SSL-inspectie** (bv. een gast-/thuisnetwerk of hotspot). Simpelst.
2. **Voeg de bedrijfs-root-CA toe aan de build** (nette oplossing in een DGS-omgeving): lever de CA
   mee en installeer hem in het image vóór `pip install`. Vraag mij dit toe te voegen als dat nodig is.
3. **Laatste redmiddel (onveilig):** `pip --trusted-host pypi.org --trusted-host files.pythonhosted.org`
   slaat de verificatie over. Niet aanbevolen; alleen voor een snelle test.

## Bouwen + uploaden

Eén commando regelt het bouwen (ARM64) en uploaden naar de router:
```bash
./scripts/build-ixrouter.sh
```
Dit gebruikt `buildkitd-ixrouter5.toml` (HTTP-registry) en de waarden uit `.ixrouter.env`, en pusht
`<router-ip>:5000/optimax:latest` naar de winkel.

## Container aanmaken op de router

> Dit vereist **IXON Edge App Management-rechten** (zie `docs-intern/optimax-ixon-handover.md`).

1. Maak een container van het `optimax`-image (registry `<router-ip>:5000`).
2. Koppel een **named volume** voor de logs: naam `optimax-logs`, pad in de container `/app/logs`.
3. Netwerk: `machine-builder`. Publiceer poort **9000** (de waarde van `APP_PORT`). De app draait
   bewust niet op 8080, want dat is de beheerpagina van de router zelf.
4. Geef de **environment-variabelen** op (hier zitten de secrets, niet in het image):
   ```
   DB_HOST=...            DB_PORT=5432         DB_NAME=db_dgs_01
   DB_USER=...            DB_PASSWORD=...
   DASHBOARD_AUTH_USER=...           DASHBOARD_AUTH_PASSWORD=...   (verplicht, anders start de app niet)
   OPENROUTER_API_KEY=... CHAT_DB_USER=... CHAT_DB_PASSWORD=...    (alleen als de chat aan moet)
   LOG_FORMAT=json        LOG_LEVEL=INFO
   ```
   Voor de demo-opstelling met de dummy-database: zie `docker-compose.edgeapp.yml`
   (DB_HOST=optimax-db met de demo-credentials).
5. Start de container.

## Integriteit bij tar-overdracht (SEC-25)

De normale route is de registry-push (buildx print dan een `sha256:`-digest en het
pull-mechanisme verifieert die automatisch). Draag je een image tóch als `.tar` over
(USB-stick, mail, fileshare), verifieer dan de hash aan beide kanten vóór `docker load`:

- Windows (PowerShell): `Get-FileHash optimax-arm64.tar -Algorithm SHA256`
- Linux/Git Bash: `sha256sum optimax-arm64.tar`

Komen de waarden niet overeen, dan is het bestand beschadigd of vervangen: niet laden.

## Controleren

- `curl http://<router-ip>:9000/api/health` → `"status":"healthy"` en `db_pool` gevuld (DB bereikbaar).
- `curl http://<router-ip>:9000/api/version` → versie + commit.
- Open in de browser `http://<router-ip>:9000` → de pagina's tonen data; de chat werkt.

## Eerst even checken op het apparaat (onbekend tot je het ziet)

- **Laat de beheerpagina poort-mapping toe?** Zo niet: de router publiceert (zoals in de IXON-gids)
  de EXPOSE-poort van het image (9000) automatisch op het router-IP. Dan bereik je `<router-ip>:9000`.
- **Is de database bereikbaar vanaf de router?** Test het DB-IP op poort 5432 vanaf de router.
  Zonder DB starten de pagina's wel, maar tonen ze fouten.
- **Wat is het echte router-IP?** De gids gebruikt `192.168.140.1` als voorbeeld; vul jullie IP in
  (`.ixrouter.env` en `buildkitd-ixrouter5.toml` en `daemon.json`).

## Iets wijzigen (ander wachtwoord, andere DB, chat uit)

Pas `.ixrouter.env` aan en draai opnieuw `./scripts/build-ixrouter.sh`. Verwijder daarna in de
beheerpagina de oude container en maak een nieuwe van het bijgewerkte image (named volume `optimax-logs`
mag je hergebruiken; de logs blijven bewaard).

## Toekomst (als de router env-variabelen of bestandsvolumes ondersteunt)

Dan kan de config uit het image en in een (named volume-)configbestand of env-variabelen, zodat je
niet meer per wijziging hoeft te herbouwen. De app leest config nu al uit env-variabelen
([backend/config.py](backend/config.py)); dat sluit daar naadloos op aan.
