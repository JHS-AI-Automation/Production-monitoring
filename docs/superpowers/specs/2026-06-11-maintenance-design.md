# Ontwerp: Maintenance-sectie (predictive maintenance op motor-stroom)

Datum: 2026-06-11. Status: goedgekeurd, skelet op synthetische data. Feature-branch
`feature/maintenance`, achter vlag (standaard uit op `main`).

## Doel en context

DGS wil straks uit de PLC-data de stroomsterkte (Ampère) van alle motoren in de lijn zien,
en automatisch slijtage detecteren: een motor die normaal dagelijks tot ~3 A piekt maar over
weken langzaam naar ~3,5 A kruipt, moet als onderhoudssignaal verschijnen ("controleer motor 50").

**De echte PLC-data en tabelnamen zijn nog onbekend.** Daarom bouwen we nu een volledig werkend
skelet op **synthetische data**, met één duidelijke naad waar de echte bron later inplugt. Zo is
het idee end-to-end te zien en te demonstreren zonder op de data te wachten.

## Scope (deze iteratie)

- Navigatie-splitsing: **Inzicht** (Overzicht, Productie, Pallets, Alarmen, Trends, Chat) en
  **Maintenance** (nieuw, eronder).
- Eén Maintenance-pagina **Motoren**: raster van motoren met statuskleur, trendgrafiek per motor
  (dagelijkse piekstroom over weken), en een paneel **Onderhoudssignalen**.
- Detectie van langzame opwaartse drift, in-dashboard signalenlijst (geen e-mail).
- Alles geïsoleerd: eigen `maintenance/`-namespace voor- en achterkant, achter een feature-vlag.

## Niet in scope (bewust)

Echte PLC-query (data onbekend → synthetisch achter de naad), e-mail naar TD (alleen lijst),
ML, achtergrond-taak (detectie draait op verzoek). Dit zijn de logische vervolgstappen zodra de
echte data en tabelnamen er zijn.

## Architectuur

### Backend (`backend/maintenance/`)
- **`data.py` — DE NAAD.** `get_motors()` en `get_motor_history(motor_id, days)` geven nu
  synthetische series (deterministisch, seeded): ~12 motoren, dagstart ~0,05 A, dagpiek ~3 A met
  ruis; 1-2 motoren krijgen een trage opwaartse trend over weken. Dit is het enige bestand dat
  later wordt omgezet naar een echte query op de PLC-tabel. Interface blijft gelijk.
- **`wear.py` — detectie.** Pure functie `detect_wear(histories) -> list[Signal]`. Regel
  (transparant, geen ML): vergelijk het gemiddelde van de laatste 7 dagdagpieken met een
  basislijn (eerste 7-14 dagen). Is de stijging > drempel (relatief en absoluut) én de trend
  consistent opwaarts, dan een signaal met motor-id, basislijn, huidige waarde, %-stijging,
  sinds-wanneer en advies. Read-only, op verzoek.
- **`backend/routers/maintenance.py`** (`/api/maintenance`): `GET /motors`,
  `GET /motors/{id}/history?days=N`, `GET /signals`. Geregistreerd in `main.py` naast de
  andere routers (read-only, mock-data, dus onschadelijk als de vlag uit staat in de UI).

### Frontend (`frontend/src/pages/maintenance/`)
- **`features.ts`**: `export const FEATURES = { maintenance: true }` (op `main`: false).
- **`maintenanceApi.ts`**: fetchers voor de 3 endpoints, met `AbortSignal` (zelfde patroon als `api.ts`).
- **`MotorOverview.tsx`**: motoren-raster (statuskleur groen/oranje/rood), per-motor trendgrafiek
  (Recharts), signalen-paneel, plus een banner "In ontwikkeling, synthetische data". Hergebruikt
  `useApi`/`combineApi`, `KPICard`, `EmptyState`, `brand`.
- **`Layout.tsx`**: nav als twee groepen (Inzicht incl. Chat, daaronder Maintenance, alleen
  zichtbaar als `FEATURES.maintenance`).
- **`App.tsx`**: route `/maintenance` (gated achter de vlag).

## Datacontract (voorlopig, tot de echte tabel bekend is)

- Motor: `{ id, name, line, baseline_a, current_a, peak_a, status }` met `status` in `ok|warn|alarm`.
- History-punt: `{ date, start_a, peak_a }` per dag.
- Signal: `{ motor_id, motor_name, baseline_a, current_a, increase_pct, since_days, advice }`.

## Testen

- Backend units (`test_maintenance.py`): stabiele motor → geen signaal; kruipende motor → precies
  één signaal met juiste velden; te weinig data → geen signaal. Endpoint-vorm-tests voor de 3 routes.
- Frontend: kleine test op de status-kleur-logica; `tsc`+`vite build` groen.

## Isolatie en latere echte data

Eén naad (`data.py`) bevat alle data-aannames. Zodra de PLC-tabel + kolomnamen bekend zijn, wordt
alleen daar de synthetische generator vervangen door een SQL-query (via de bestaande asyncpg-pool);
detectie, endpoints, grafieken en pagina blijven ongewijzigd. De feature-vlag bepaalt of de sectie
zichtbaar is; tot go-live blijft hij in `main` uit.
