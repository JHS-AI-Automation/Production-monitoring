# Optimax monitoring-opties (edge-deployment achter een VPN)

> Status: **startdocument / inventarisatie** (2026-06-10). Bewust nog niet uitgewerkt tot een
> gekozen oplossing. Breid uit zodra we een laag + alert-kanaal kiezen, of bij de eerste echte
> klant-deployment. Generiek bedoeld voor elke klant waar we een app op een machine (edge + VPN)
> zetten, niet alleen DGS.

## Het probleem

Zodra Optimax (+ zijn database) op een klant-SecureEdge draait, zit het achter een VPN. Je kunt er
van buitenaf niet bij om te checken of het nog leeft. Een klassieke "inkijk" uptime-monitor
(UptimeRobot, Pingdom) werkt daarom niet: die kan `:9000` niet bereiken.

**Kerninzicht:** draai het om. Niet van buiten naar binnen kijken, maar het apparaat naar buiten
laten "bellen" (push / heartbeat). Stopt het bellen, dan is er een alarm. Dat vangt zelfs een
volledig dood apparaat, wat een inkijk-monitor nooit kan. Combineer dit in lagen.

## Wat Optimax al aan boord heeft (hergebruiken, niets nieuws bouwen)

- `/api/health` (checkt ook de DB, geeft 200 of 503), `/api/version`, `/api/metrics`, en een
  kant-en-klaar Prometheus-endpoint `/api/metrics/prometheus` (zie [../backend/main.py](../backend/main.py))
- Docker `HEALTHCHECK` (elke 30s) + `restart: unless-stopped` in de [../Dockerfile](../Dockerfile)
  (crasht de container, dan herstart hij automatisch)
- JSON-logging met rotatie naar `/app/logs` (max 25 MB), request-id tracing, en `/api/client-log`
  waar de frontend render-fouten naartoe stuurt
- Een complete observability-stack staat klaar maar uit: [../observability/](../observability/)
  (prometheus.yml, grafana-datasources.yml, promtail-config.yml) plus
  [../docker-compose.observability.yml](../docker-compose.observability.yml)
- Op de SecureEdge draaien al **Node-RED en Grafana** als containers: precies de bouwstenen die we
  nodig hebben, zonder nieuwe infra te installeren

## Faalscenario's om te dekken ("wat kan er misgaan")

1. App-container gecrasht of gestopt
2. App draait, maar DB onbereikbaar, dus geen data (`/api/health` geeft 503)
3. DB-container gecrasht of het volume vol
4. Apparaat offline: stroom- of netwerkuitval
5. Schijf vol (eMMC 32 GB) door log- of DB-groei
6. Geheugendruk / OOM-kill op de IX6000
7. **Data-staleness:** de PLC/Node-RED-pipeline is stilgevallen; containers zijn "healthy" maar er
   komen geen nieuwe rijen binnen. Dit is de gevaarlijkste stille fout bij productie.

## De opties, gelaagd

### L0 — Self-heal (al ingebouwd, gratis)
Docker `HEALTHCHECK` + `restart: unless-stopped`. Transiente crashes herstellen vanzelf; de
IXON/Docker-UI toont healthy/unhealthy.
- Effort: 0 (alleen zorgen dat de restart-policy in de Edge App staat).
- Dekt: #1 (transient). Mist: alles wat kapot blijft, en het apparaat zelf.

### L1 — Heartbeat / dead-man's-switch (de ruggengraat bij VPN)
Iets op de edge belt elke paar minuten naar een dienst die je WEL ziet; stopt het bellen, dan alarm.
- Host: de al aanwezige **Node-RED**. Flow: elke 5 min `GET /api/health`, bij `healthy` een POST
  naar de heartbeat-URL; bij unhealthy of geen antwoord juist NIET pingen.
- Externe diensten: Healthchecks.io (open-source, self-host-baar, gratis tier), Better Stack,
  Cronitor, Dead Man's Snitch.
- Dekt: #1 t/m #4, **en een dood apparaat** (uniek: een inkijk-monitor merkt dat nooit). Effort: laag.
- Productie-uitbreiding: laat de heartbeat ook **data-versheid** checken (`max(time)` recent), dan
  vang je ook #7.

### L2 — On-edge metrics + alerting (rijk inzicht + trends)
Zet de bestaande observability-stack aan, met de Grafana die er al staat: Prometheus scrapet
`/api/metrics/prometheus`, Grafana-dashboards + **Grafana Alerting** (regels: error-rate, latency,
`db_pool` leeg, target down, geen nieuwe data). Notificatie via e-mail of Teams-webhook.
- Dekt: #1 t/m #3, #5 t/m #7, met trends.
- Beperking: draait óp de edge, dus de alerting heeft zelf egress nodig én valt mee om als het
  apparaat sterft. Daarom blijft L1 nodig als buitenste vangnet.
- Effort: midden (de stack bestaat al in de repo).

### L3 — On-demand (handmatig, via VPN)
`curl :9000/api/health`, `/api/metrics`, `/api/version`; logs lezen in `/app/logs`. Voor diagnose,
niet voor proactief alarm. Effort: 0.

### L4 — IXON-native device-alarm
IXON Cloud-melding "apparaat offline" plus datagebruik. Vangt stroom/netwerk op apparaat-niveau,
los van de app. Nog uit te zoeken: koppelt Edge App Management container-health aan IXON-alarmen?
- Effort: laag (portaal-config, door iemand met IXON-rechten).

## Egress-caveat (cruciaal bij klanten)

Een heartbeat naar buiten en Teams/e-mail-webhooks vereisen **uitgaande HTTPS**. Bij DGS zagen we al
corporate SSL-inspectie; bij klanten kan een firewall arbitraire HTTPS blokkeren of inspecteren.
Opties:
- (a) het heartbeat-domein laten allowlisten,
- (b) een self-hosted heartbeat-ontvanger op een adres dat de edge wél mag bereiken,
- (c) melden via het IXON-kanaal.

Test de egress altijd vooraf vanaf de edge (`curl` naar het heartbeat-domein).

## Aanbeveling per situatie (voor klant-deployments)

- **Minimaal bij elke klant:** L0 (gratis) + L4 (IXON device-offline) + L1 heartbeat met
  e-mail-alarm. Dekt "is het überhaupt up", inclusief een dood apparaat, met lage effort.
- **Bij echte productie-data:** daar bovenop L2 (Grafana-alerting) en L1 uitgebreid met
  data-versheid (#7), want "looks healthy maar geen nieuwe data" is de gevaarlijkste stille fout.
- **Alert-kanaal-advies:** e-mail als basis (werkt altijd); Teams erbij zodra de klant meekijkt
  (Microsoft-omgeving); een extern heartbeat-dashboard (Healthchecks.io) als je een statuspagina +
  onafhankelijke "apparaat-dood"-detectie wilt; IXON device-alarm altijd aan als vangnet.

## Nog uit te zoeken / later uitbreiden

- Koppelt IXON Edge App Management container-health aan device-alarmen? (L4)
- Egress-beleid per klant: mag de edge naar buiten, en wordt HTTPS geinspecteerd? (heartbeat + webhooks)
- Concrete Node-RED heartbeat-flow uitwerken (incl. data-versheidcheck) als herbruikbaar Edge App-onderdeel
- Grafana-alertregels concreet maken (drempels error-rate, latency, db_pool, staleness)
- Wie ontvangt de alarmen per klant (Uland, klant-IT, of beide) en escalatiepad
- Op termijn: een generieke versie onder `shared/references/` voor alle edge-deployments
