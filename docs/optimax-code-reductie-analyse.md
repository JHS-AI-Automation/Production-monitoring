# Optimax code-reductie-analyse: kan het met minder code, net zo goed?

> Datum: 2026-06-10. Analyse over de volledige codebase (~6.040 regels: backend 2.078,
> frontend 2.741, scripts 876, infra 343). Vraag van Jasper: "kunnen we het net zo goed met
> minder code doen?" Eis daarbij: geen functionaliteit, veiligheid of leesbaarheid inleveren.

## Eindoordeel vooraf

De codebase is **al behoorlijk lean**. Eerdere dedupe-rondes zijn zichtbaar: gedeelde
datum-validatie (`timewindow.py`), één pool-factory (`create_db_pool`), de `_line_payload`-helper,
de `useApi`-hook met cache, en herbruikbare componenten (KPICard, ErrorBanner, EmptyState,
LoadingSpinner). De "dikke" stukken zijn grotendeels bewust: documentatie (per regel
"code zonder uitleg is niet toegestaan"), security-checks in de chat, en het met de hand
gebouwde SVG-fabrieksschema (dat IS de feature).

**Realistisch reductiepotentieel zonder kwaliteitsverlies: ~250-300 regels (4-5%).
Met milde trade-offs: ~550-650 regels (9-11%). Meer dan dat kost functionaliteit,
leesbaarheid of veiligheid.** Regels tellen is bovendien de verkeerde maat: een
regel SQL-kolomherhaling is goedkoper in onderhoud dan een slimme generator die
niemand meer durft aan te passen.

## Concrete kansen, gerangschikt op aanbeveling

### A. Aanbevolen (winst zonder echte trade-off, ~250-300 regels)

| # | Wat | Waar | Besparing | Toelichting |
|---|---|---|---|---|
| A1 | `insert_direct()`-pad schrappen uit de dummy-data-generator | `scripts/generate_dummy_data.py` (regels 290-376) | ~110 | Het script heeft twee routes: SQL naar stdout (`--sql-only`) en direct inserten via psycopg2. De directe route dupliceert alle DDL + insert-logica en vereist een extra dependency (psycopg2). Alle huidige flows (docker-seed, prod-spiegel via `seed_partitioned.py`, Edge-image) gebruiken de SQL-route. Schrappen = -110 regels en een dependency minder. Documentatie-impact: CLAUDE.md "Lokale ontwikkeling" wijzigt naar `--sql-only \| psql`-pipe. |
| A2 | Pallet-SQL genereren uit de `STATIONS`-lijst | `backend/routers/pallets.py` (regels 63-104, 133-151) | ~45 | 4 stations x 3 statussen = 12 vrijwel identieke `ROUND(100.0 * COUNT(*) FILTER ...)`-blokken, en nogmaals 4 in hourly. De `STATIONS`-constante bestaat al; de SELECT-kolommen daaruit opbouwen (vaste lijst, geen user-input, dus geen injectie-risico) maakt 1 bron van waarheid. Leesbaarheid blijft gelijk of wordt beter. |
| A3 | Build-arg-konfiguratie uit de Dockerfile slopen | `Dockerfile` (config-blok ~regels 40-60) + `scripts/build-ixrouter.sh` | ~35 | Sinds vandaag is de beslissing: config via env-vars bij container-creatie, niet inbakken. Het hele ARG/ENV-blok (DB_*, OPENROUTER, DASHBOARD_AUTH, CHAT_*) plus de bijbehorende build-arg-doorgifte in het build-script kan weg. Veiliger (geen secrets-in-image-pad meer) én minder code. |
| A4 | Dubbele Overview-elementen | `frontend/src/pages/Overview.tsx` | ~15 | De pagina toont top-alarmen 2x (BarChart + AlarmTable onderaan) en heeft een dubbele empty-state (regel 291 naast de per-blok EmptyStates). Eén van beide schrappen na keuze welke DGS wil houden. |
| A5 | Frontend page-scaffold-hook | alle 5 pages | ~60-80 | Elke pagina herhaalt: `useState(yesterday)` + N useApi-calls + `loading = a.loading \|\| b.loading...` + `error = ...` + retry-bundeling + header-met-DatePicker. Een `usePageData({stats: fetcher, ...})`-hook die {data, loading, error, retryAll} bundelt scheelt 12-16 regels per pagina en maakt nieuwe pagina's goedkoper. |

### B. Te overwegen (werkt, maar met milde trade-offs, ~250-350 regels extra)

| # | Wat | Waar | Besparing | Trade-off |
|---|---|---|---|---|
| B1 | `counter0..3`-herhaling in productie-SQL genereren | `backend/routers/production.py` (summary, hourly, minutely, trends, oee) | ~50-60 | Elke query herhaalt 4x `COALESCE(SUM(counterX),0) AS line_X` (en in oee 4x COUNT FILTER + 4x PERCENTILE). Een `_line_cols("SUM")`-helper halveert dat. MAAR: de SQL is dan niet meer copy-paste-baar naar psql/Adminer voor debugging, en juist bij partitie-debugging is dat veel waard. Alleen doen als het team SQL-debugging zelden doet. |
| B2 | `MinuteDetail` vervangen door recharts met `syncId` | `frontend/src/components/ProductionFlowDiagram.tsx` (regels 78-186) | ~70 | De handgebouwde 4-sparkline-weergave met gedeelde schaal + hover-kruisdraad kan met 4 kleine recharts LineCharts met `syncId` (gesynchroniseerde tooltips). Trade-off: het huidige gedrag (één kruisdraad over alle 4, exacte gedeelde max-schaal, supercompact) is nét anders; pixel-perfect nabouwen in recharts kost tuning. |
| B3 | Recharts-boilerplate-wrapper | Overview, Production, Trends | ~50-70 | `<SimpleBarChart data x y>`-wrapper voor de herhaalde ResponsiveContainer/XAxis/YAxis/Tooltip-setup. Trade-off: indirectie; bij elke afwijkende chart-optie groeit de wrapper-API en verlies je de winst. |
| B4 | `load_test.py` vervangen door extern tool | `scripts/load_test.py` | ~157 | `hey`, `ab` of `locust` doet hetzelfde. Trade-off: externe dependency op de dev-machine en het script kent de Optimax-endpoints al. Dit is een scope-keuze, geen kwaliteitswinst. |

### C. NIET doen (kost meer dan het oplevert)

| Wat | Waarom niet |
|---|---|
| Comments/docstrings strippen (~15% van de backend) | Bewuste keuze (coding-standards: WAAROM-commentaar verplicht). De module-docstrings van production.py (58 regels) en pallets.py (34) zijn de KPI-definities, dat is domeindocumentatie die anders in een losse doc zou staan. |
| `chat.py` "vereenvoudigen" | De dichtheid daar is security: sanitizer, rate-limit, token-budget, pool-isolatie, TLS-resolve. Elke geschrapte regel is een geschrapte verdediging. De vertakkingen in `init_chat` zijn bewuste productie-vs-intern-paden. |
| Logging/JSON-formatter vervangen door een library | `python-json-logger` of `structlog` scheelt ~30 regels maar voegt een dependency toe (tegen de regel "geen externe dependencies zonder overleg") en het eigen formattertje is triviaal. |
| TypeScript-interfaces in `api.ts` genereren uit OpenAPI | `openapi-typescript`-codegen scheelt ~140 handgeschreven interface-regels maar voegt build-tooling + generatiestap toe. Bij 4 routers is handmatig sync prima; heroverwegen als de API 2x zo groot wordt. |
| Het SVG-fabrieksschema inkorten | De ~170 regels schema in ProductionFlowDiagram zijn geen boilerplate, dat is de visuele feature zelf (robots, lijnen, overflow-pijlen). Minder regels = minder tekening. |
| `useApi` vervangen door react-query/SWR | Library scheelt ~60 eigen regels maar voegt 10-40 KB dependency toe voor exact dezelfde features (cache, abort, retry). De eigen hook is af en getest. |

## De strategische olifant: Grafana

Eerlijk benoemen: op de SecureEdge draait al **Grafana**. Puur voor "cijfers op een dashboard
achter de VPN" had ~90% van deze codebase vervangen kunnen worden door Grafana-dashboards op
dezelfde Postgres (0 regels eigen frontend, alleen SQL-panels). Dat is bewust niet gedaan, en
terecht, omdat Optimax meer is dan panels: white-label product (eigen branding/brand.js), de
AI-chat op de eigen data, het custom fabrieksschema met overflow-logica, en een verkoopbaar
geheel voor DGS-klanten. Maar voor toekomstige "alleen-monitoring"-vragen bij klanten is
"Grafana-panels in plaats van custom app" de juiste eerste vraag, dat is de echte
10x-minder-code-route wanneer productwaarde geen rol speelt.

## Samenvattende cijfers

| Pakket | Besparing | % van totaal | Kwaliteitsrisico |
|---|---|---|---|
| A (aanbevolen) | ~265-285 regels | ~4,5% | geen |
| A + B | ~580-680 regels | ~10% | mild (debugbaarheid SQL, chart-tuning) |
| Theoretisch maximum (incl. C) | ~1.200+ | ~20% | reëel verlies aan docs, veiligheid, type-safety |

## Conclusie

Het antwoord op "kan het met minder?" is: **een beetje, en vooral op drie plekken** (de dubbele
insert-route in de dummy-generator, de pallet-SQL-herhaling, en het nu overbodige
build-arg-blok in de Dockerfile). De rest van de omvang is geen vet maar spierweefsel:
domeindocumentatie, security-lagen en de visuele feature. 6.000 regels voor een white-label
dashboard met 16 API-endpoints, AI-chat, auth, metrics, observability-stack en
deployment-tooling is aan de zuinige kant; het gemiddelde vergelijkbare project zit daar
ruim boven. Aanbeveling: voer pakket A uit (een middagje werk, -280 regels, nul risico)
en laat B liggen tot er een concrete onderhouds-aanleiding is.
