# Optimax: werk-index (TODO)

| | |
|---|---|
| **Doel** | Eén startpunt voor al het openstaande werk aan Optimax, met verwijzingen naar de gedetailleerde bronnen. |
| **Laatst bijgewerkt** | 2026-06-10 |
| **Status** | Werkdocument, geen klant-deliverable. |

> Dit is de **index**, niet de detail-administratie. Het knoopt drie werkstromen aan elkaar: security, productisatie (multi-tenant) en productie-deploy. Per item staat waar het detail leeft. Niet hier dupliceren, bijwerken bij de bron.
>
> Relatie met andere docs:
> - [docs/optimax-backlog.md](docs/optimax-backlog.md) = de 100 gedetailleerde deploy/productie-taken (werkstroom 3).
> - [docs/optimax-stappenplan.md](docs/optimax-stappenplan.md) = de 30 directe deploy-stappen.
> - [ADR-001](ADR-001-deployment-edge-vs-cloud.md) / [ADR-002](ADR-002-multi-tenant-capability-model.md) / [ADR-003](ADR-003-fleet-operations.md) = de architectuurbesluiten (werkstroom 2).
> - Security-review (in de Uland-monorepo, buiten deze repo): `output/dgs/alarm-dashboard-security-review-20260609.md` + sessie-map `output/sessions/20260609-dgs-optimax-security-review/`.

Legenda: `[ ]` open, `[x]` gedaan. `[code]` = code-fix, `[deploy]` = router/infra, `[beslissing]` = Thomas/DGS.

---

## Werkstroom 1: Security (blokkeert klant-go-live)

Volledige onderbouwing met `bestand:regel` per item: zie het security-review-rapport (§3 findings, §8 roadmap, §9 changelog). Eindoordeel review: **NO-GO tot must-fixes klaar, daarna conditionele GO**.

### 1a. Ronde 1: gefixt en geverifieerd op 2026-06-09

Bewijs: `pytest` 24 passed / 4 skipped, plus `verify_security_fixes.py` 9/9 PASS (script in de sessie-map).

- [x] SEC-01 auth verplicht bij start in productie (escape `ALLOW_NO_AUTH=1` voor interne test)
- [x] SEC-02 + SEC-13 Grafana anon-admin uit, observability-poorten naar loopback
- [x] SEC-03 container draait als non-root `appuser`
- [x] SEC-04 chat valt niet meer terug op de schrijf-pool (uit in productie zonder read-only rol)
- [x] SEC-05 chat-DB-rol versmald naar exact de 4 tabellen (setup-SQL in [CLAUDE.md](CLAUDE.md))
- [x] SEC-06 read-only hoofd-DB-rol gedocumenteerd als mitigatie van baked secrets
- [x] SEC-07 `/api/client-log` body-cap 16 KB + CRLF-strip
- [x] SEC-12 `mem_limit`, `pids_limit`, `no-new-privileges` op de app-container
- [x] SEC-18 dagelijks chat-token-budget (503 bij overschrijding)
- [x] SEC-27 metrics tellen op begrensd route-label (geen geheugen-DoS)
- [x] SEC-28 Prometheus-label volledig ge-escaped

### 1b. Ronde 2: open code-fixes

- [x] **SEC-08** `[code]` security-response-headers (CSP same-origin, X-Frame-Options DENY, nosniff, Referrer-Policy) op elke response incl. 401/500-paden (2026-06-11). Daarmee zijn alle must-fix-code-items toegepast; TLS zelf = go-voorwaarde, zie 1c.
- [x] SEC-09 `[code]` SQL-sanitizer-hardening: CTE's toegestaan, afgedwongen buiten-LIMIT via subquery-wrap, blocklist uitgebreid (INTO/SET/COPY/DO/CALL/...), multi-statements geweigerd (2026-06-11)
- [ ] SEC-10 `[code]` brute-force-lockout op Basic Auth
- [x] SEC-11 `[code/deploy]` Postgres-poort in compose gebonden aan loopback (host-toegang blijft, LAN niet) (2026-06-11)
- [ ] SEC-14 `[code]` Promtail redaction-stage (indien observability-stack meegaat)
- [x] SEC-15 `[code]` certs via BuildKit bind-mount i.p.v. COPY: certificaat belandt nooit meer in een image-laag (2026-06-11; build-verificatie via CI)
- [x] SEC-16 `[code]` `.ixrouter.env`, `*.tar`, `db/seed.sql`, `backend/tests/` in `.dockerignore` (`.env`-patroon matchte `.ixrouter.env` niet) (2026-06-11)
- [x] SEC-17 `[code]` `message` max-length (2000) + anti-injectie-instructie in de system-prompt (2026-06-11)
- [x] SEC-22 `[code]` startup-waarschuwing bij `CHAT_TLS_VERIFY=false` (zat al in `_resolve_tls_verify`, geverifieerd 2026-06-11)
- [x] SEC-23 `[code]` `args.get("query","")` tegen KeyError bij malformed tool-call, incl. JSON-decode-vangnet (2026-06-11)
- [x] SEC-24 `[code]` chat-historie naar sessionStorage (weg bij sluiten tabblad; oude localStorage-historie wordt eenmalig gewist) (2026-06-11)
- [ ] SEC-25 `[deploy]` sha256-verificatie bij overdracht van `optimax-arm64.tar`
- [x] SEC-29 `[code]` chat-availability-DoS: wall-clock-deadline (60s) per conversatie + begrensde wachttijd (10s) op een LLM-slot (2026-06-11; samen met SEC-18 = volledige chat-DoS-mitigatie). Budget-melding klantvriendelijk gemaakt.
- [ ] OBS-1 `[code]` base-images op digest pinnen
- [x] OBS-2 `[code]` SCHEMA_CONTEXT counter-labels gecorrigeerd (lijn 1/4 = robot-output, lijn 2/3 = overflow) (2026-06-11)
- [ ] `[code]` `verify_security_fixes.py` promoveren tot vaste pytest-regressietests

### 1c. Harde go-voorwaarden (Thomas/DGS, geen code)

Afvinkbaar, geen voetnoot: de conditionele GO leunt hierop. Detail in rapport §4 en §7.

- [ ] `[beslissing]` DB-rolrechten geverifieerd op de echte DGS-DB: hoofd-`DB_USER` strikt read-only, `chat_readonly` alleen SELECT op de 4 tabellen (draagt SEC-04/05/06)
- [ ] `[beslissing]` VPN-traject bevestigd versleuteld, of TLS via reverse-proxy (draagt SEC-06/08)
- [ ] `[beslissing]` baked-secrets-acceptatie + dedicated budget-gelimiteerde OpenRouter-key + segmentatie poort 5000 + rotatieprocedure (SEC-06)
- [ ] `[beslissing]` AVG-weging (procesoptimalisatie, geen werknemersbeoordeling; mogelijk OR art. 27) + EU AI Act-classificatie chat (SEC-26 / §7)

### 1d. Buiten Optimax (apart oppakken)

- [ ] OBS-3 `[deploy]` Ridder IQ-credentials roteren + uit git-history opschonen (staan cleartext in de monorepo, los van Optimax)

---

## Werkstroom 2: Productisatie naar multi-tenant

Besluit en onderbouwing: [ADR-002](ADR-002-multi-tenant-capability-model.md) (product/data-model) en [ADR-003](ADR-003-fleet-operations.md) (fleet-operatie). **Niet nu bouwen**: de ADR's zijn bewust de plan-deliverable. Speculatief bouwen vanuit alleen DGS is premature abstractie. Faseren op echte klant-vraag.

- [ ] **Laag 1: capability-gating** (~2 tot 4 dagen). Profiel-config + nav/routes/endpoints/KPI-kaarten gaten op een manifest + chat-schema-context uit het manifest. Lost "klant zonder pallets/robot" op door de module uit te zetten. **Trigger: zodra klant 2 concreet wordt.**
- [ ] **Laag 2: data-mapping-laag** (~2 tot 4 weken). Router-SQL van hardgecodeerde DGS-kolommen naar queries gegenereerd uit een per-klant mapping; frontend-pagina's parameter-gedreven. De echte white-label. **Trigger: pas als het schema van klant 2/3 echt bekend is**, incrementeel.
- [ ] **Laag 3: fleet-operatie** (~1 tot 2 weken + 1 onbekende). Eén image met N configs (runtime-config), dunne centrale beheerlaag (deploy + telemetrie), edge als cattle. **Eerste te toetsen aanname:** ondersteunt de IXON-router runtime-config/volume, of is een provisioning-omweg nodig (ADR-003 §3.1)? **Trigger: bij een echte vloot.**

---

## Werkstroom 3: Productie-deploy en overdracht (DGS)

De volledige takenlijst staat in [docs/optimax-backlog.md](docs/optimax-backlog.md) (100 taken, 11 categorieen) en [docs/optimax-stappenplan.md](docs/optimax-stappenplan.md). Niet hier dupliceren. De backlog heeft een eigen prioritering; de blokkerende clusters:

- [ ] Live krijgen + data tonen: backlog A1-A8 (deploy/router), B9-B14 (views/datalaag), D38-D39 (health/uptime)
- [ ] Voor klant-go-live: backlog C23-C26 + C31 (security, overlapt werkstroom 1), I85-I92 (docs/overdracht), J93-J98 (compliance/governance)
- [ ] Daarna: F (tests), G (UX-polish), D/E (monitoring/ops), H (chat aanzetten)
- [ ] Roadmap: K99-K100 (edge-AI anomaly-detection, predictive maintenance)

> Let op: de security-review (werkstroom 1) is gedetailleerder en recenter dan backlog-categorie C. Bij conflict is het review-rapport leidend voor security.

---

## Werkstroom 4: Betrouwbaarheid en KPI-correctheid (architectuur-review 2026-06-10)

Volledige onderbouwing met bestand-verwijzingen: [ARCHITECTURE.md](ARCHITECTURE.md) sectie 12, blok "Onafhankelijke architectuur-review (2026-06-10)". Dit zijn geen security-issues maar betrouwbaarheids- en correctheids-punten; de drie HIGH-items horen vóór klant-go-live opgelost.

### HIGH (voor go-live)

- [ ] `[code]` **DB-reconnect**: lazy re-init met backoff in `database.py` zodat de app herstelt als Postgres later op is dan het dashboard (stroomuitval-scenario op de IXrouter, geen compose-`depends_on` daar)
- [x] `[code]` **Frontend-timeout gefixt**: `signal` wordt doorgegeven aan fetch in `api.ts` (alle 13 fetchers + 12 call-sites) en abort-door-timeout toont nu een echte foutmelding i.p.v. een eeuwige spinner (2026-06-11)
- [ ] `[code/beslissing]` **Timezone eenduidig**: vaststellen of Node-RED lokale tijd of UTC schrijft, daarna één conversiestrategie voor shift-venster, piekuur en alarm-impact + `TZ=Europe/Amsterdam` in de container + `date.today()`-default fixen

### MEDIUM (eerste patch na go-live)

- [ ] `[code]` Ontbrekende minuten als downtime tellen (generate_series-raster) of datagaten expliciet rapporteren in OEE/stilstand
- [ ] `[code]` Alarm-impact op alarm-intervallen (trigger tot resolve) i.p.v. alleen de trigger-minuut
- [x] `[code]` Chat: outer-LIMIT afgedwongen via subquery-wrap, resultset begrensd op 1000 rijen (2026-06-11, onderdeel SEC-09)
- [x] `[code]` Chat: CTE's (`WITH ... SELECT`) toegestaan in de sanitizer (2026-06-11, onderdeel SEC-09)
- [ ] `[code]` Chat: conversatie-historie (laatste N berichten) meesturen naar de backend voor vervolgvragen
- [x] `[code]` Alarmenlijst: page geclampt vóór de data-query (geen zinloze OFFSET-scan) + `%`/`_`/`\` ge-escaped in de ILIKE-zoekterm (2026-06-11)

### LOW (opportunistisch)

- [x] `[code]` SPA-caching: `no-cache` op index.html/SPA-fallback, `immutable` (1 jaar) op gehashte assets (2026-06-11)
- [ ] `[code]` DST-dagen: shift-minuten berekenen i.p.v. hardcoded 1080
- [x] `[code]` `exec` in de container-CMD: uvicorn is PID 1 en ontvangt SIGTERM direct (2026-06-11)
- [x] `[code]` 401's meetellen in metrics (brute-force zichtbaar; auth-weigering werd niet geteld) (2026-06-11)
- [ ] `[code]` `load_dotenv(override=False)` overwegen (precedence-verrassing)
- [ ] `[code]` Chat: alle uitgevoerde SQL's tonen bij multi-query-antwoorden

---

## Waar beginnen (suggestie)

1. **Security afronden** voor klant-go-live: SEC-08 (1b) + de vier go-voorwaarden (1c). Dit is de echte blocker.
1b. **Betrouwbaarheid afronden** voor klant-go-live: de drie HIGH-items uit werkstroom 4 (DB-reconnect, frontend-timeout, timezone-eenduidigheid).
2. **Live krijgen**: deploy-clusters A/B/D uit de backlog (werkstroom 3).
3. **Overdracht + compliance**: backlog I + J, plus Thomas-akkoord op klant-uitlevering.
4. **Should-fix security** (rest van 1b) als eerste patch na go-live.
5. **Productisatie laag 1** zodra klant 2 in zicht komt, daarna laag 2/3 op echte vraag.

---

## Governance

- Optimax-output richting DGS valt onder de klant-uitlevering-regel: Thomas ratificeert vóór verzending of go-live (backlog J98, security-rapport `status: needs-thomas-approval`).
- ADR-002 en ADR-003 staan op status **Voorgesteld**: nog niet geratificeerd. Als ze als officiele productisatie-richting met DGS gedeeld worden, eerst Thomas laten meelezen.

## Bronnen-index

- Architectuur: [ARCHITECTURE.md](ARCHITECTURE.md), [CLAUDE.md](CLAUDE.md)
- Besluiten: [ADR-001](ADR-001-deployment-edge-vs-cloud.md), [ADR-002](ADR-002-multi-tenant-capability-model.md), [ADR-003](ADR-003-fleet-operations.md)
- Deploy: [DEPLOY.md](DEPLOY.md), [DEPLOY-ixrouter.md](DEPLOY-ixrouter.md), [INSTALLATIE-KLANT.md](INSTALLATIE-KLANT.md), [RUNBOOK.md](RUNBOOK.md)
- Taken: [docs/optimax-backlog.md](docs/optimax-backlog.md), [docs/optimax-stappenplan.md](docs/optimax-stappenplan.md), [docs/optimax-ixon-handover.md](docs/optimax-ixon-handover.md)
- Security (Uland-monorepo, buiten deze repo): `output/dgs/alarm-dashboard-security-review-20260609.md`, `output/sessions/20260609-dgs-optimax-security-review/`
