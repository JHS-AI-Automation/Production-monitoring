# Optimax draaien op de IXrouter5 ("de logger")

Stap-voor-stap, in gewone taal. De IXrouter5 is een ARM64 edge-router met een eigen
Docker-"app-winkel" (registry) en een beheerpagina in de browser.

## Hoe het werkt (kort)

1. Je bouwt op je eigen pc een app-pakket (Docker-image) en **upload** dat naar de winkel van
   de router (`<router-ip>:5000`).
2. Op de **beheerpagina** (`<router-ip>:8080`) maak je daar een draaiend exemplaar (container) van.
3. De router kan een app bij het starten **geen instellingen** meegeven. Daarom bakken we alle
   instellingen (database-adres, wachtwoorden, OpenRouter-sleutel, poort) **in het pakket** vóór het
   uploaden. Wijzig je later iets, dan bouw + upload je opnieuw.
4. De router draait op een **ARM64/v8-chip**; we bouwen expliciet daarvoor (anders: "exec format error").

> Belangrijk: omdat instellingen in het pakket gebakken zitten, zitten ook de wachtwoorden en de
> OpenRouter-sleutel in het pakket. De winkel staat lokaal op de router; houd het pakket niet breder
> beschikbaar. Dit is een bewuste afweging zolang de router (MVP) geen env-variabelen ondersteunt.

## Eenmalige voorbereiding (op je eigen pc)

1. Zorg dat Docker met **buildx** draait (Docker Desktop heeft dit).
2. Vertel Docker dat de router-winkel via HTTP mag. Voeg in `/etc/docker/daemon.json` toe
   (vervang het IP door dat van jullie router) en herstart Docker:
   ```json
   { "insecure-registries": ["192.168.140.1:5000"] }
   ```
   (Op Windows/Docker Desktop: Settings → Docker Engine → dit toevoegen → Apply & Restart.)
3. Kopieer `.ixrouter.env.example` naar `.ixrouter.env` en vul de waarden in (DB, OpenRouter, router-IP).
   Dit bestand bevat secrets en wordt **niet** in git opgeslagen.

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

1. Open de beheerpagina: `http://<router-ip>:8080`.
2. Ververs de lijst; je ziet nu het `optimax`-image.
3. Maak er een container van. Koppel een **named volume** voor de logs:
   naam `optimax-logs`, pad in de container `/app/logs`.
4. Publiceer poort **9000** (de waarde van `APP_PORT`) als de UI dat toelaat. De app draait bewust
   niet op 8080, want dat is de beheerpagina van de router zelf.
5. Start de container.

## Controleren

- `curl http://<router-ip>:9000/api/health` → `"status":"healthy"` en `db_pool` gevuld (DB bereikbaar).
- `curl http://<router-ip>:9000/api/version` → versie + commit.
- Open in de browser `http://<router-ip>:9000` → de pagina's tonen data; de chat werkt.

## Eerst even checken op het apparaat (onbekend tot je het ziet)

- **Laat de beheerpagina poort-mapping toe?** Zo niet: de router publiceert (zoals in de IXON-gids)
  de in het image gebakken poort (9000) automatisch op het router-IP. Dan bereik je `:<router-ip>:9000`.
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
