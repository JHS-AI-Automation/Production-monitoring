# ADR-003: Fleet-operatie, één image met N configs en een dunne beheerlaag

| | |
|---|---|
| **Status** | Voorgesteld (nog niet geimplementeerd of geratificeerd) |
| **Datum** | 2026-06-10 |
| **Beslisser** | Uland AI, in overleg met DGS |
| **Doelgroep** | Uland AI (engineering en operatie), DGS-IT |
| **Component** | DGS Optimax (`projects/dgs/alarm-dashboard`) |

> [ADR-001](ADR-001-deployment-edge-vs-cloud.md) koos edge-first (per klant lokaal). [ADR-002](ADR-002-multi-tenant-capability-model.md) koos config-gedreven multi-tenant in plaats van forks. Deze ADR gaat over de derde dimensie: zodra Optimax bij meerdere klanten draait, moet je vijf of meer losse edge-installaties kunnen uitrollen, updaten en beheren zonder dat het handwerk lineair meegroeit. Richting, geen uitgevoerde beslissing; vandaar status Voorgesteld.

---

## 1. Context

Met edge-first (ADR-001) plus een config-gedreven product (ADR-002) ontstaat een vloot: N edge-devices, elk met dezelfde container-stack en een eigen klant-profiel. De huidige MVP-aanpak voor deployment knelt zodra die vloot groeit.

**Hoe het nu gaat (uit de IXON-deploy-aanpak):** alle instellingen plus wachtwoorden worden vóór de build in het ARM-image gebakken, omdat het IXON-router-MVP bij het starten geen env-vars of volumes kan meegeven. Voor één klant is dat een prima, pragmatische workaround.

**Waarom het bij 5 klanten breekt:**

- Elke wachtwoord-rotatie of config-wijziging betekent: cross-compilen, pushen naar de registry, en de container opnieuw aanmaken via de web-UI van die router. Keer vijf.
- Eén lekkend image betekent klant-secrets op straat, want de secrets zitten erin gebakken.
- Updates uitrollen is per router handwerk; er is geen centraal overzicht van wat waar draait of gezond is.

## 2. Besluit

Drie samenhangende keuzes, los van de data (de data blijft lokaal, zie ADR-001):

1. **Één image, N configs.** Config en secrets bij het starten inladen, niet in het image bakken.
2. **Een dunne centrale beheerlaag, vanaf dag één.** Voor uitrollen, updaten en monitoren van de hele vloot. Alleen telemetrie verlaat de fabriek, niet de ruwe data.
3. **Edge-device als "cattle", niet als "pet".** Gestandaardiseerde stack, per-klant config in git, reproduceerbare provisioning.

## 3. De mechanismen

### 3.1 Eén image met N configs (grootste ops-winst)

Config en secrets bij het starten inladen via een gemounte env-file of config-volume, of een kleine provisioning-stap. Resultaat: één image dat bij alle klanten hetzelfde is, met per klant alleen een ander config-bestand ernaast.

Wat dit oplevert:

- Wachtwoord roteren of config wijzigen = config aanpassen en herstarten, geen rebuild plus cross-compile plus push.
- Geen secrets meer in het image; een gelekt image bevat geen klant-wachtwoorden.
- Het klant-profiel uit ADR-002 (mapping plus capabilities) is precies zo'n config-bestand: dat hoort naast het image, niet erin.

**Randvoorwaarde om te verifieren:** de baked-image-aanpak bestond juist omdat de IXON-router bij containerstart geen env-vars of volumes meegaf. Voordat dit kan, moet bevestigd worden of die beperking echt en blijvend is, of te omzeilen via een config-volume dan wel een lichte provisioning-stap op de router. Dit is de eerste te toetsen aanname, geen gegeven.

### 3.2 Een dunne centrale beheerlaag (grootste schaal-winst)

Niet voor de data, wel voor de operatie:

- centraal images uitrollen en updaten naar alle sites, in plaats van per router handmatig,
- gezondheid en metrics van alle sites in één overzicht (alleen telemetrie verlaat de fabriek, de ruwe machinedata blijft lokaal),
- centrale logs voor support.

**Proportionele toolkeuze.** Voor ongeveer 5 sites is een lichte fleet-manager passend (denk Balena of Portainer Edge), geen zwaar platform. Azure IoT Edge of Azure Arc is denkbaar (DGS leunt op Microsoft), maar is voor dit aantal waarschijnlijk te zwaar. De app heeft al een `/api/health`, `/api/metrics` en `/api/metrics/prometheus`, plus een optionele Prometheus/Loki/Grafana-stack; de beheerlaag bouwt daarop voort in plaats van iets nieuws te verzinnen.

### 3.3 Edge-device als "cattle", niet als "pet"

Gestandaardiseerde container-stack, per-klant config versioneerd in git, reproduceerbare provisioning. Een device is dan vervangbaar en herbouwbaar, geen handgemaakt unicum. Klant nummer 6 onboarden wordt "config invullen en uitrollen", geen apart bouwproject. Dit sluit direct aan op de onboarding-stappen uit ADR-002 (wijs naar de Postgres, vul de mapping, bevestig capabilities, brand-config, uitrollen).

## 4. Gevolgen

- **Secrets-rotatie en config-wijziging worden goedkoop** (config plus herstart, geen rebuild).
- **Updates gaan vlootbreed** vanuit één plek, met zicht op wat waar draait.
- **Support krijgt één ruit** op gezondheid, metrics en logs van alle sites.
- **Onboarding versnelt** en wordt voorspelbaar.
- **Trade-off:** investering vooraf in provisioning en de beheerlaag, en de beheerlaag is zelf iets dat draait en onderhoud vraagt. Daarom bewust dun houden.

## 5. Eerlijke grenzen en wat NIET te doen

- **Geen data centraliseren.** De beheerlaag verwerkt telemetrie (health, metrics, logs) en deployment, niet de ruwe machinedata. Dat onderscheid is de kern van ADR-001 en blijft staan.
- **Niet over-engineeren.** Voor 5 sites is een lichte fleet-manager genoeg. Volledige Kubernetes of een zwaar IoT-platform is overkill en wordt zelf een onderhoudslast.
- **Eerste aanname toetsen.** De runtime-config op de IXON-router (zie 3.1) is de blokkerende onbekende; begin daar voordat je de rest bouwt.

## 6. Referenties

- [ADR-001](ADR-001-deployment-edge-vs-cloud.md), edge-first en de scheiding data lokaal versus beheer centraal
- [ADR-002](ADR-002-multi-tenant-capability-model.md), het klant-profiel (mapping plus capabilities) dat als config naast het image leeft
- [ARCHITECTURE.md](ARCHITECTURE.md), sectie 4 (deployment), sectie 10 (observability)
- [DEPLOY-ixrouter.md](DEPLOY-ixrouter.md), de huidige baked-image-aanpak die deze ADR wil vervangen
