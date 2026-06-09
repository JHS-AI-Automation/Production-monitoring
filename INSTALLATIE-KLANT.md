# Optimax bij de klant op de logger zetten — installatie- en go-live-handleiding

Voor degene die Optimax installeert op de IXrouter5 ("de logger") bij de klant (DGS).
Geschreven om te volgen zonder de code te kennen. Voor de gedetailleerde build-stappen:
zie ook [DEPLOY-ixrouter.md](DEPLOY-ixrouter.md). Voor het draaien/troubleshooten: [RUNBOOK.md](RUNBOOK.md).

> **Belangrijk om te weten vooraf.** De router kan een app bij het starten geen instellingen
> meegeven. Daarom worden alle instellingen (database, wachtwoorden, OpenRouter-sleutel) vóór het
> uploaden in het pakket "gebakken". Wil je later iets wijzigen (ander wachtwoord, andere
> database), dan bouw en upload je het pakket opnieuw. Dit betekent ook: **de wachtwoorden zitten
> in het pakket** dat op de router staat. Houd het pakket dus niet breder beschikbaar dan de router.

---

## Deel A — Voorbereiding: wat moet er geregeld zijn vóór je begint

Vink af. Dit zijn de voorwaarden voor een veilige go-live (uit de security-review van 2026-06-09).

- [ ] **Toegang tot de router**: je kunt bij de beheerpagina `http://<router-ip>:8080` en weet het router-IP (bevestigd: `192.168.23.254`).
- [ ] **Build-pc met Docker** (Docker Desktop met buildx) waarop je het pakket bouwt.
- [ ] **Database-gegevens** van de klant: host, naam, gebruiker, wachtwoord.
- [ ] **Database-gebruiker staat op alleen-lezen** (zie Deel B-2). Dit is belangrijk: omdat de
      wachtwoorden in het pakket zitten, mag een eventueel uitgelekt wachtwoord hooguit data kunnen
      *lezen*, nooit wijzigen.
- [ ] **OpenRouter-sleutel**: een aparte sleutel speciaal voor deze klant, met een **uitgavenlimiet**
      ingesteld in het OpenRouter-dashboard (bv. 10-25 euro/maand). Niet de algemene JHS-sleutel.
- [ ] **VPN/netwerk**: het dashboard is alleen bereikbaar via de beveiligde verbinding (IXON-VPN /
      het interne netwerk), niet open op internet. Bevestig dit met de IT van de klant.
- [ ] **AVG-akkoord** (organisatorisch): is afgesproken dat het dashboard voor proces-/machine-inzicht
      is en niet voor het beoordelen van individuele medewerkers? Zie de security-review §7. Bij twijfel:
      eerst met de klant (en eventueel een jurist) afstemmen.

---

## Deel B — Accounts en wachtwoorden aanmaken

Er zijn **drie** soorten toegang. Lees dit deel goed: zonder de juiste instellingen **start de app niet**.

### B-1. Inloggen op het dashboard (wie mag het dashboard zien)

Het dashboard is beveiligd met **één gedeelde gebruikersnaam + wachtwoord** (HTTP Basic Auth). Iedereen
die het dashboard mag gebruiken, gebruikt dezelfde login. Dat is bewust simpel gehouden.

> **Let op:** dit is dus **één gedeelde login**, geen apart account per persoon. Voor losse accounts
> per medewerker is een volgende stap nodig (een inlog-koppeling/SSO via een reverse-proxy). Dat staat
> op de "nog te doen"-lijst (Deel F). Voor nu: één login die je deelt met de mensen die toegang krijgen.

Zo stel je hem in (in het bestand `.ixrouter.env`, zie Deel C):

```
DASHBOARD_AUTH_USER=dgs
DASHBOARD_AUTH_PASSWORD=<een sterk, willekeurig wachtwoord van minstens 16 tekens>
```

- Genereer een sterk wachtwoord (bv. via een wachtwoordmanager). Geen woordenboekwoord.
- **Als je deze twee leeg laat, weigert de app te starten** (veilige standaard). Dat is met opzet:
  een dashboard met de fabrieksdata + AI-chat mag niet zonder login op een bedrijfsnetwerk staan.
- Bewaar de login op een veilige plek en deel hem alleen met wie toegang nodig heeft.

> Alleen voor een **interne test** (op je eigen machine, niet bij de klant) mag je de login overslaan
> door `ALLOW_NO_AUTH=1` te zetten. **Nooit bij de klant doen.**

### B-2. Database-rollen (alleen-lezen)

De app en de chat mogen de database **alleen lezen**. Stel op de database twee dingen in (de SQL
staat in [CLAUDE.md](CLAUDE.md) onder "Chat read-only rol"):

1. **De hoofd-gebruiker** (`DB_USER`) krijgt alleen `SELECT`-rechten op de 4 tabellen, geen
   schrijfrechten. Zo kan een uitgelekt wachtwoord niets kapotmaken.
2. **Een aparte chat-rol** `chat_readonly` met alleen `SELECT` op diezelfde 4 tabellen. Vul die in als
   `CHAT_DB_USER` / `CHAT_DB_PASSWORD`.

> Zonder de chat-rol schakelt de chat zichzelf **uit** bij de klant (in plaats van als de
> schrijf-gebruiker te draaien). Dat is veilig, maar dan werkt de chat niet. Stel de rol dus in als
> je de chat wilt gebruiken.

### B-3. Inloggen op de monitoring (Grafana) — alleen als je de logging meeneemt

De monitoring (Grafana/Loki/Prometheus, om op afstand te zien waarom er iets stukging) heeft een
**eigen** login. Stel een admin-wachtwoord in via een `.env`-bestand naast
`docker-compose.observability.yml`:

```
GRAFANA_ADMIN_PASSWORD=<sterk wachtwoord>
```

- Zonder dit wachtwoord start de monitoring-stack niet (geen anonieme toegang meer).
- **Hier kun je wél losse accounts per persoon maken**: log in als admin in Grafana, ga naar
  `Administration > Users` en nodig collega's uit met hun eigen login.
- De monitoring is bewust alleen lokaal/loopback bereikbaar; benader Grafana via een SSH-tunnel of de
  VPN, niet open op het netwerk.

---

## Deel C — Instellingen invullen (`.ixrouter.env`)

Op de build-pc, in de projectmap:

1. Kopieer `.ixrouter.env.example` naar `.ixrouter.env` (dit bestand wordt **niet** in git opgeslagen).
2. Vul alle `CHANGE_ME`-waarden in: router-IP, database, OpenRouter-sleutel, de chat-rol (B-2) en de
   dashboard-login (B-1). Het dagelijkse chat-budget staat standaard op 300.000 tokens; aanpassen mag.
3. Bouw je achter SSL-inspectie (DGS-netwerk)? Zet `INSTALL_CORP_CA=1` en leg het bedrijfs-root-CA als
   `.crt` in de map `certs/`. Zie DEPLOY-ixrouter.md.

---

## Deel D — Bouwen en op de logger zetten

1. Eenmalig: zet de router-registry als "insecure" in Docker (zie DEPLOY-ixrouter.md, "Eenmalige voorbereiding").
2. Bouw en upload het pakket:
   ```
   ./scripts/build-ixrouter.sh
   ```
   (Achter SSL-inspectie: `INSTALL_CORP_CA=1 ./scripts/build-ixrouter.sh`.)
3. Open de router-beheerpagina `http://<router-ip>:8080`, ververs, en maak een container van het
   `optimax`-image:
   - poort **9000**
   - named volume **`optimax-logs`** gekoppeld aan `/app/logs`
   - netwerk `machine-builder`
4. Start de container.

---

## Deel E — Controleren na installatie

- [ ] `http://<router-ip>:9000/api/health` geeft `"status":"healthy"` (database bereikbaar).
- [ ] `http://<router-ip>:9000/api/version` toont de versie + commit.
- [ ] Het dashboard `http://<router-ip>:9000` vraagt om **inloggen** (Deel B-1) en toont daarna data.
- [ ] De chat werkt (als je de chat-rol hebt ingesteld) en toont per antwoord de gebruikte SQL + data.
- [ ] (Monitoring meegenomen?) Grafana vraagt om inloggen, geen anonieme toegang.

---

## Deel F — Beheer (later iets wijzigen)

- **Wachtwoord of database wijzigen:** pas `.ixrouter.env` aan en draai `./scripts/build-ixrouter.sh`
  opnieuw. Verwijder daarna de oude container in de beheerpagina en maak een nieuwe van het bijgewerkte
  image (named volume `optimax-logs` mag je hergebruiken). Dit komt doordat de instellingen in het
  pakket gebakken zitten.
- **Persoon toegang geven tot het dashboard:** geef diegene de gedeelde login (B-1). (Losse accounts
  per persoon = toekomst, zie hieronder.)
- **Persoon toegang geven tot de monitoring:** maak een account in Grafana (B-3).
- **Chat uitzetten:** laat `OPENROUTER_API_KEY` leeg in `.ixrouter.env` en herbouw.

---

## Deel G — Nog te doen vóór een volledig veilige go-live

Uit de security-review van 2026-06-09. De onderstaande zijn al gedaan in de code (ronde 1): inlog
verplicht, container draait niet meer als beheerder, chat draait alleen-lezen, geheugen- en
kosten-limieten, monitoring dicht. Wat er **nog** moet gebeuren:

**Door de klant / Thomas (geen code):**
- [ ] Database-gebruiker(s) écht op alleen-lezen zetten op de productie-database (Deel B-2).
- [ ] Uitgavenlimiet op de OpenRouter-sleutel + aparte sleutel per klant (Deel A).
- [ ] Bevestigen dat het dashboard alleen via de beveiligde verbinding/VPN bereikbaar is.
- [ ] AVG-afspraak vastleggen (proces-inzicht, niet personeelsbeoordeling).

**Aanbevolen volgende code-ronde (JHS, niet blokkerend maar wel netjes vóór bredere uitrol):**
- [ ] HTTPS (versleutelde verbinding) i.p.v. gewoon HTTP, plus beveiligings-headers.
- [ ] Losse accounts per persoon voor het dashboard (inlog-koppeling/SSO via reverse-proxy) i.p.v.
      één gedeelde login.
- [ ] Beveiliging tegen ongelimiteerd wachtwoord-raden op de login.
- [ ] Extra dichttimmeren van de chat-SQL-controle en een paar kleinere punten.

> De volledige, technische lijst met onderbouwing staat in de security-review:
> `output/dgs/alarm-dashboard-security-review-20260609.md` (in de Uland-workspace).
