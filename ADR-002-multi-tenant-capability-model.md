# ADR-002: Multi-tenant via config, niet via forks per klant

| | |
|---|---|
| **Status** | Voorgesteld (nog niet geimplementeerd of geratificeerd) |
| **Datum** | 2026-06-10 |
| **Beslisser** | Uland AI, in overleg met DGS |
| **Doelgroep** | Uland AI (engineering en productstrategie), DGS-IT |
| **Component** | DGS Optimax (`projects/dgs/alarm-dashboard`) |

> Optimax is opgezet als herbruikbaar product, maar is nu nog één installatie voor één klant (DGS). Zodra het bij meerdere klanten gaat draaien, verschilt elke klant: de een heeft geen pallets, de ander geen robotarm, de databases hebben andere tabellen en kolommen. Deze ADR legt vast hoe we die variatie opvangen met configuratie in plaats van met een aparte codebase per klant. Het is een richting, geen uitgevoerde beslissing; vandaar status Voorgesteld.

---

## 1. Context

[ADR-001](ADR-001-deployment-edge-vs-cloud.md) legde vast dat Optimax edge-first draait: per klant op een lokaal edge-device, naast hun eigen Postgres. De volgende vraag dient zich aan zodra er meer klanten komen (verwachting: richting 5).

De klanten verschillen wezenlijk, en op twee verschillende manieren:

- **Een heel datadomein ontbreekt.** De ene klant heeft geen `palletstatus`-tabel, dus geen pallet-functionaliteit.
- **Een domein bestaat wel, maar heeft een andere vorm.** Bij DGS is het productiemodel "robot legt af op lijn 1/4, overflow op lijn 2/3". Een klant met een simpele lijn telt gewoon stuks per lijn, zonder dat robot/overflow-concept. Aantal lijnen, ploegtijden en kolomnamen verschillen ook.

**Het risico:** als elk verschil zijn eigen code krijgt, ontstaan vijf losse projecten. Dan schalen de kosten lineair (elke klant = volledige bouw plus onderhoud, en één bugfix = vijf keer fixen) en lopen de codebases uit elkaar. Dat is precies wat we willen vermijden.

## 2. Het onderscheid: product versus projecten

Verschillende tabjes per klant maakt het nog geen meerdere projecten. De scheidslijn is: **komt elk tabje uit gedeelde bouwblokken, of wordt het per klant met de hand gebouwd?**

Vergelijk Grafana, Home Assistant of Shopify-winkels: twee installaties zien er totaal anders uit, andere panelen, andere tabs, en toch is het één product met één codebase. De variatie zit in *wat je samenstelt uit dezelfde blokken*, niet in de code.

De echte vraag is dus niet "verschillen de tabs" (dat doen ze sowieso), maar "hoeveel echt unieke module-types heb je over alle klanten?". Industriele monitoring convergeert naar een kleine, eindige set: alarmen, productie-telling, OEE/beschikbaarheid, trends, status-van-assets, een flow/topologie-weergave, chat. Een nieuwe klant is meestal een nieuwe *combinatie* van bestaande blokken, zelden een echt nieuw blok.

Ook de twee lastige voorbeelden generaliseren netjes als je ze op het juiste niveau bouwt:

- **Pallets** is geen pallet-ding maar "toon de status van N losse stations, elk in een van M toestanden, over tijd". Datzelfde widget bedient ook ovenplekken, inpak-bays, bufferposities of AGV-docks.
- **Robotarm-flow** is "toon doorvoer door een proces-topologie met splitsing en samenvoeging", een generieke flow-weergave.

Bouw je ze als `pallet6000` en `robot-lijn-1`, dan zijn ze bespoke en krijg je forks. Bouw je ze als generieke capability-types, dan zijn ze herbruikbaar.

## 3. Besluit

**Optimax wordt een config-gedreven product, geen codebase per klant.**

Elke klant wordt beschreven door een **klant-profiel** (configuratie), opgebouwd uit twee lagen:

- een **data-mapping-laag**: waar staat de data (welke tabellen en kolommen van deze klant horen bij welke Optimax-KPI-input),
- een **capability-laag**: wat heeft deze klant (welke modules bestaan en met welke parameters).

De applicatie zelf bestaat uit een **generieke core** plus **optionele, capability-gated modules**. De klant-specifieke eigenaardigheden zitten in modules en config, niet in de core.

## 4. De mechanismen

### 4.1 Capability-manifest per klant (config, geen code)

Bovenop de data-mapping-laag komt een capability-laag die zegt wat een klant heeft:

```yaml
features:    { alarms: true, production: true, pallets: false, robotFlow: false, chat: true }
production:  { lines: 2, model: "flat" }        # of "robot-overflow" bij DGS
shift:       { start: "06:00", end: "22:00" }   # of leeg = geen shift-concept
```

Mapping zegt *waar* de data staat, capabilities zeggen *wat er bestaat*. Samen vormen ze het klant-profiel. Geen `if (klant === "dgs")` in de code: alle variatie loopt via dit manifest.

### 4.2 Data-mapping-laag (de grootste gemiste stap)

Dit is het echte productisatie-gat, en groter dan deployment. De app is nu hard bedraad op het DGS-schema: 4 tabellen, `counter0` = lijn 1 robot, `incomingstate` 0/1, palletcodes 100/200/300, shift 05:00-23:00. Bij klant 2 ziet die Postgres er gegarandeerd anders uit: andere tabelnamen, andere kolommen, ander aantal lijnen, andere ploegtijden. Zonder mapping-laag wordt elke klant een code-fork en lopen de codebases uit elkaar.

Per klant dus een configuratiebestand dat zegt: deze tabel of kolom van de klant hoort bij deze KPI-input die Optimax verwacht. De `brand.ts` regelt nu het uiterlijk met één bestand, dat is het goede instinct, maar hij regelt alleen cosmetica. Hetzelfde principe hoort er te zijn voor de dáta. Dat is de echte white-label.

### 4.3 Detecteer automatisch waar het kan

Niet alles handmatig invullen. Bij provisioning of opstart tast de app de database af: bestaat `palletstatus` en zit er data in? Heeft het counter-model een robot/overflow-splitsing of gewoon N platte tellers? Daaruit leid je de capabilities grotendeels zelf af, en de config bevestigt of overschrijft. Voordeel: je voorkomt "module staat aan maar er is geen data". Het dashboard toont wat de data ondersteunt, niet wat iemand hoopte.

### 4.4 Scheid generieke KPI's van domein-visualisaties

Het belangrijkste inzicht. Kijk je naar wat ontbreekt bij die klanten, dan zijn pallets en de robotarm-flow vooral de bespoke visualisatie-laag, niet de kern-waarde. Het grootste deel van de waarde is juist generiek:

- **Generiek (werkt voor bijna elke klant met tellers plus alarmen):** alarmen, throughput, stilstand, OEE, MTTR, trends, chat. OEE is `Availability × Performance × Quality`, dat werkt voor elke lijn met een teller en een storingssignaal, robot of niet.
- **Klant- of branche-specifiek (modulair, capability-gated):** de pallet-stations, het geanimeerde robot-flow-diagram, alles wat uniek is.

De DGS-eigenaardigheden (robot legt af op 1/4, overflow op 2/3, het SVG-fabrieksschema) horen dus in een klant- of branche-module, niet in de core. Core = stabiel en voor iedereen, modules = optioneel inplugbaar. Dat is precies de scheiding die nu nog mist.

### 4.5 Hoe het door de stack loopt

- **Backend:** ontbrekende module = endpoints niet gemount (of een nette "capability disabled"). KPI's die niet te berekenen zijn tonen "n.v.t.", geen verzonnen getal. De graceful-degradation die er al in zit ("start zonder DB") trek je door naar "start zonder pallet-capability".
- **Frontend:** nav, KPI-kaarten en routes worden gedreven door het manifest. Geen pallets, dan geen Pallets-tab en geen pallet-kaart op het overzicht. De app heeft al een schone pagina-structuur, dit is een uitbreiding, geen herbouw.
- **Chat (mooie bijvangst):** de text-to-SQL chat krijgt zijn schema-context nu hardcoded. Genereer die uit het mapping- en capability-manifest, dan kent de chat bij een klant zonder pallets simpelweg geen pallet-tabellen en gaat hij er ook niet over hallucineren. Capability-variatie kost de chat dan vrijwel niets extra.

## 5. Wanneer is het tóch een fork?

Een concrete toets om afdrijven te merken. Na klant 3 of 4: als een nieuwe klant om tab X vraagt, schrijf je dan **nieuwe render- of query-logica**, of **zet je een bestaande module aan en configureer je hem**? Zit je structureel in het eerste, meer dan grofweg 1 op de 5 keer, dan zijn je modules te specifiek en glijd je richting projecten. Dat is het signaal om de abstractie op te schonen.

**Convergentie-pad (eerlijk over de beginfase).** Bij klant 1 en 2 ken je het juiste abstractieniveau nog niet. De perfecte generieke modulebibliotheek bouwen vanuit één voorbeeld is premature abstractie, een eigen valkuil. Realistisch:

1. Klant 1 en 2: delen via kopieren-en-aanpassen, accepteer een project-achtige fase.
2. Rond klant 2 of 3: trek de herbruikbare kern eruit zodra je ziet wat echt terugkomt.
3. Vanaf dan: klant N is config plus af en toe een nieuwe module.

Het is een spectrum, geen knop. Het doel is "één codebase, compositie via config, af en toe een nieuwe module". De faalmodus is "vijf forks". Wat je daartussen houdt is module-discipline.

## 6. Gevolgen

- **Kostencurve buigt om.** Klant N kost richting alleen-config in plaats van een volledige bouw; een bugfix is één keer in plaats van vijf keer.
- **Onboarding wordt config, geen code.** Klant aansluiten = (1) wijs naar hun Postgres, (2) schema-probe vult de mapping, (3) auto-gedetecteerde capabilities bevestigen, (4) brand-config, (5) uitrollen.
- **De `brand.ts`-aanpak wordt doorgetrokken.** Die regelt nu het uiterlijk met één bestand. Hetzelfde principe (één bron, config-gedreven) komt er voor de dáta (mapping) en de functionaliteit (capabilities).
- **Investering vooraf.** Dit vraagt engineering aan de mapping-laag, het capability-systeem en het modulair maken van de bestaande pagina's. Dat is bewust werk, geen gratis lunch.

## 7. Eerlijke grenzen

- **Geen toverstaf.** Dit model handelt *afwezigheid en variatie van bekende features* netjes af. Een KPI die nog niemand heeft, blijft ontwikkelwerk. Het verschil is dat het dan een **additieve module** is (bestaande klanten raken niet), geen fork.
- **Abstractieniveau is de crux.** De hele aanpak valt of staat bij modules op het juiste generieke niveau bouwen (asset-status-grid, niet pallet6000). Te specifiek = alsnog forks.
- **Niet over-engineeren.** Voor 5 klanten is een capability-manifest plus een handvol optionele modules proportioneel. Een volledig plugin-platform of marketplace-architectuur is overkill op dit aantal.

## 8. Referenties

- [ADR-001](ADR-001-deployment-edge-vs-cloud.md), sectie 7 (multi-site en white-label)
- [ADR-003](ADR-003-fleet-operations.md), fleet-operatie (één image met N configs, dunne beheerlaag, cattle-not-pets). Het klant-profiel uit deze ADR is de config die ADR-003 uitrolt.
- [ARCHITECTURE.md](ARCHITECTURE.md), secties 6 (datamodel), 7 (KPI-afleidingen), 9 (frontend-modules), 11 (white-label via `brand.ts`)
- [CLAUDE.md](CLAUDE.md), datamodel en domein-semantiek (de DGS-specifieke counter- en palletcodes die generiek gemaakt moeten worden)
