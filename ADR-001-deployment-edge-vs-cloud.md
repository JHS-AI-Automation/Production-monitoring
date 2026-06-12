# ADR-001: Deployment edge-first, niet alles-op-de-cloud

| | |
|---|---|
| **Status** | Geaccepteerd |
| **Datum** | 2026-06-10 |
| **Beslisser** | Uland AI, in overleg met DGS |
| **Doelgroep** | DGS-IT en betrokkenen bij de Optimax-infrastructuur |
| **Component** | DGS Optimax (`projects/dgs/alarm-dashboard`) |

> Dit document legt vast waarom Optimax lokaal op een edge-device in de fabriek draait en niet volledig in de cloud. Het besluit is al geimplementeerd; deze ADR maakt de afweging expliciet zodat de vraag "kunnen we dit niet gewoon in de cloud zetten" een vast, navolgbaar antwoord heeft.

---

## 1. Context

Vanuit DGS-IT kwam de vraag of de Optimax-architectuur niet volledig in de cloud kan draaien. Dat is een logische vraag (minder eigen hardware, makkelijker beheer), maar hij botst met hoe de data fysiek tot stand komt. De relevante feiten, zoals vastgelegd in [ARCHITECTURE.md](ARCHITECTURE.md) en [CLAUDE.md](CLAUDE.md):

- **De volledige datapijplijn staat al lokaal en bij elkaar.** PLC produceert data, een OPC UA-server ontsluit die, Node-RED transformeert en schrijft naar PostgreSQL. PostgreSQL, Node-RED, Grafana en Adminer draaien **als Docker-containers op hetzelfde edge-device** (Ixon SecureEdge Pro, Linux ARM64, 32GB) in de fabriek. De "loggers" en Node-RED zitten dus letterlijk op dezelfde machine als de database.
- **Het is realtime, hoogfrequente machinedata.** Sample rate ongeveer 250ms, batch-writes minimaal elke 100ms, retentie 90 dagen, productie-shift 18 uur per dag (05:00 tot 23:00).
- **De database is intern.** `db_dgs_01` op `192.168.23.254:5432`, op het DGS-netwerk, van buiten alleen bereikbaar via de Ixon VPN-tunnel.
- **De applicatie weet dat de verbinding kan wegvallen.** Optimax is een pure read-consument en is bewust gebouwd met graceful degradation: bij een onbereikbare database start de app toch en rapporteert `unhealthy` in plaats van te crashen. Dat is een expliciete erkenning dat een tunnel-verbinding niet altijd betrouwbaar is.
- **Er is al precies een cloud-component, en die is optioneel.** De AI-chat vertaalt natuurlijke taal naar SQL via een extern LLM (OpenRouter). Valt die weg, dan blijft de rest van het dashboard gewoon werken.

## 2. Wat fysiek vastligt versus wat een vrije keuze is

Niet alles in deze stack is een voorkeur. Een deel ligt vast door de techniek:

- **OPC UA plus 250ms-sampling is praktisch LAN-gebonden.** Dit verkeer over het internet of een VPN trekken geeft latency, firewall-complexiteit en geen realtime-garantie. De data-acquisitie hoort naast de machines.
- **Node-RED en de database-write horen bij de machines** en staan al op de edge-box. Ze daarvan losweken levert geen winst op, alleen een extra netwerkschakel.
- **Uitval-tolerantie is een harde eis.** De fabriek mag niet "blind" worden voor zijn eigen productie- en alarmdata als het internet of de VPN even wegvalt. Lokale data plus lokale app betekent: storing buiten de deur raakt de fabrieksvloer niet.
- **Datagovernance.** Machinedata continu de fabriek uit naar een cloud pompen roept extra vragen op over waar data staat en wie erbij kan. DGS heeft hier eerder bewust over nagedacht (zie [advies dataveiligheid Claude vs Copilot](../docs/advies-dataveiligheid-claude-vs-copilot.md)). Lokaal houden is hier de eenvoudigste verdedigbare keuze.

Vrije keuze is vooral: waar draait het dashboard zelf, waar draait monitoring, en hoe schalen we naar meerdere locaties.

## 3. Overwogen opties

### Optie A: Volledig in de cloud

Database, dashboard en (idealiter) data-acquisitie in een cloud-omgeving (Azure/AWS).

- Voordeel: geen eigen hardware op locatie, centraal beheer, eenvoudig op te schalen in rekenkracht.
- Nadeel: de OPC UA-/PLC-data moet alsnog lokaal opgehaald worden, dus de acquisitie-laag blijft hoe dan ook op de fabriek. Je splitst dan een nu samenhangende stack op en pompt 250ms-data continu de fabriek uit. De fabriek wordt afhankelijk van de internetverbinding voor het zien van zijn eigen data. Egress-kosten en latency lopen op. Dit is de optie die de meeste nadelen introduceert voor de minste winst.

### Optie B: Edge-first, on-premise (huidige situatie)

Acquisitie, database en dashboard-app lokaal op het edge-device; LLM-chat als enige optionele cloud-afhankelijkheid.

- Voordeel: laagste latency, robuust bij internet-/VPN-uitval, data blijft in het pand, minst aantal bewegende schakels, sluit aan op de al bestaande container-stack.
- Nadeel: per locatie een edge-device dat beheerd moet worden; geen vanzelfsprekend centraal overzicht over meerdere fabrieken.

### Optie C: Hybride, edge-first met een dunne cloud-laag

Optie B als basis, plus een optionele cloud-laag voor monitoring en (later) cross-site rapportage.

- Voordeel: behoudt de robuustheid van edge-first, maar geeft het centrale beheer- en overzichtsvoordeel waar de cloud-vraag eigenlijk vandaan komt.
- Nadeel: iets meer opzet dan puur lokaal; de cloud-laag moet bewust beperkt blijven tot beheer/monitoring, niet de ruwe machinedata.

## 4. Besluit

**Optie B als fundament, met de deur open naar Optie C.**

Optimax draait edge-first: data-acquisitie (PLC, OPC UA, Node-RED), de PostgreSQL-database en de dashboard-applicatie staan lokaal op het edge-device in de fabriek. De AI-chat via OpenRouter is de enige verplichte externe afhankelijkheid en is bewust optioneel gehouden.

"Alles op de cloud" wordt niet gedaan. De ruwe machinedata centraliseren in de cloud weegt niet op tegen het verlies aan robuustheid, de extra latency, de egress-kosten en de governance-vragen.

## 5. Gevolgen

- **Geen cloud-database.** De ruwe machinedata blijft op het DGS-netwerk.
- **Per locatie een edge-device.** Schalen naar een nieuwe fabriek betekent een edge-device plaatsen, niet de data centraliseren (zie sectie 7).
- **De VPN is voor support, niet voor de werking.** De Ixon-tunnel is nodig voor remote beheer, monitoring en ontwikkeling, niet voor de dagelijkse werking van het dashboard op de vloer.
- **Expliciete trade-off:** we accepteren dat er hardware per locatie beheerd moet worden, in ruil voor robuustheid en data die in het pand blijft.

## 6. Wat wel naar de cloud kan of mag

Belangrijk onderscheid voor de discussie met IT: **data centraliseren in de cloud** is iets anders dan **beheer en monitoring centraliseren**. Het tweede kan prima:

- **Monitoring en observability.** De optionele observability-stack (Prometheus, Loki, Grafana) kan lokaal blijven of naar een cloud-dienst (bijvoorbeeld Grafana Cloud) gestuurd worden. Dat geeft centraal zicht op de gezondheid van alle edge-devices zonder de ruwe machinedata te verplaatsen.
- **Centrale software-distributie en remote-beheer.** Builds uitrollen en containers beheren over meerdere locaties is een legitieme cloud-/beheerlaag.
- **De AI-chat is al cloud** (OpenRouter), en blijft optioneel.

Kortom: de schaal- en beheervoordelen waar de cloud-vraag vandaan komt, zijn grotendeels te halen met een dunne cloud-beheerlaag bovenop de edge-devices, zonder de machinedata zelf naar de cloud te verplaatsen.

## 7. Multi-site en white-label (bijvoorbeeld Cellerland)

> De concrete uitwerking hiervan staat in [ADR-002](ADR-002-multi-tenant-capability-model.md) (product- en datamodel: capability-manifest plus data-mapping) en [ADR-003](ADR-003-fleet-operations.md) (fleet-operatie: uitrollen, updaten, monitoren van meerdere sites).

Optimax is opgezet als herbruikbaar product (white-label via `frontend/src/brand.ts`). Het schaalpatroon naar meerdere klanten of locaties is:

- **Repliceer het edge-device per fabriek.** Elke locatie krijgt zijn eigen lokale acquisitie plus dashboard. Dit houdt de robuustheid en de lage latency overal intact.
- **Optioneel een cloud-aggregatielaag** voor cross-site rapportage bovenop de losse edge-devices, gevoed door samenvattende data (niet de ruwe 250ms-stroom).

Eerlijk benoemd voor klanten zonder eigen edge-hardware: ook dan moet de data-acquisitie lokaal blijven, dat is techniek en geen voorkeur. Een volledig cloud-gehost dashboard is alleen denkbaar op een naar buiten gerepliceerde of gesynchroniseerde read-kopie van de data, en dan koop je de tunnel-afhankelijkheid en egress-kosten er bewust bij. Dat is een aparte beslissing per klant, geen reden om de DGS-opzet nu te veranderen.

## 8. Referenties

- [ARCHITECTURE.md](ARCHITECTURE.md), secties 2 (architectuur in een oogopslag), 4 (deployment en infrastructuur), 11 (ontwerpbeslissingen)
- [CLAUDE.md](CLAUDE.md), secties Infrastructuur en Datakenmerken
- [DEPLOY-ixrouter.md](DEPLOY-ixrouter.md), edge-device build en deploy
- [Advies dataveiligheid Claude vs Copilot](../docs/advies-dataveiligheid-claude-vs-copilot.md)
