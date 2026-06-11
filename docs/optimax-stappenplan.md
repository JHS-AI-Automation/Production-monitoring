# Optimax op de logger: stappenplan (wat nog moet)

Fijnmazig afvinklijstje om Optimax live te krijgen op de IXON SecureEdge ("DGS R&D Logger",
`192.168.23.254`). 30 stappen in 5 fases. `[jij]` = handeling op jouw machine of in het IXON-portaal,
`[ik]` = doe ik (scriptbaar), `[samen]` = beslissing/controle samen.

Laatst bijgewerkt: 2026-06-10.

## Al gedaan (context, telt niet mee)

- App + Dockerfile met config-in-image, build/push-script, healthcheck, CA-mechanisme (optioneel, staat uit).
- `.ixrouter.env` ingevuld: DB (`192.168.23.254:5432`, db_dgs_01), OpenRouter-sleutel, dashboard-login. Gitignored, niet gedeeld.
- Router-IP bevestigd: `192.168.23.254`, Docker-registry op `:5000`.
- Deployable image gebouwd: `optimax-ixrouter.tar` (62 MB), build werkt zonder CA.
- Code + gids gepusht naar de JHS-repo (`Production-monitoring`).
- Dashboard-login: gebruiker `dgs`, wachtwoord staat in `.ixrouter.env` (bewaar in wachtwoordmanager).

---

## Fase 1 — Image op de router krijgen (push)

1. [jij] VPN naar het DGS-net aanzetten en stabiel houden (Docker Desktop laten draaien).
2. [jij] Registry-test: `curl.exe http://192.168.23.254:5000/v2/` moet `{}` geven (niet hangen).
3. [ik] Push-methode kiezen: (a) `./scripts/build-ixrouter.sh` (build + push, build uit cache) als de build met VPN aan werkt, anders (b) het al-gebouwde `optimax-ixrouter.tar` pushen.
4. [jij, alleen bij methode b] In Docker Desktop `192.168.23.254:5000` als "insecure registry" zetten (Settings -> Docker Engine -> toevoegen -> Apply & Restart).
5. [ik] Image pushen naar `192.168.23.254:5000/optimax:latest`.
6. [ik] Push verifiëren: `curl.exe http://192.168.23.254:5000/v2/optimax/tags/list` toont `latest`.

## Fase 2 — Container aanmaken op de SecureEdge (IXON-portaal)

7. [jij] Inloggen op IXON Cloud, device "DGS R&D Logger" openen.
8. [jij] Naar Edge App Management / Docker-beheer van het apparaat.
9. [jij] Image-lijst verversen; `optimax:latest` verschijnt vanuit de registry.
10. [jij] Nieuwe container aanmaken met naam `optimax`.
11. [jij] Poort publiceren: host `9000` -> container `9000` (TCP).
12. [jij] Netwerk koppelen: `machine-builder` (zo kan hij de DB-container bereiken).
13. [jij] Volume koppelen: named volume `optimax-logs` -> `/app/logs`.
14. [jij] Restart-policy op `unless-stopped` (indien instelbaar).
15. [jij] Container starten.

## Fase 3 — Controleren dat hij draait

16. [jij/ik] Healthcheck: `curl.exe http://192.168.23.254:9000/api/health` -> `"status":"healthy"`.
17. [jij/ik] Versie: `curl.exe http://192.168.23.254:9000/api/version` -> versie + commit.
18. [jij] Browser: `http://192.168.23.254:9000`, inloggen met `dgs` + het wachtwoord.
19. [jij] Pagina's doorklikken: Overzicht, Alarmen, Productie, Pallets, Trends.

## Fase 4 — Data echt laten zien (de grootste open kwestie)

> De live-DB heeft nu de ruwe tabellen (`readconfig2`, `readstartstop3`, `test024`), niet de
> nette tabellen die het dashboard verwacht (`plc_alarms`, `capacity_perminutev2`, `palletstatus`).
> Tot dit is opgelost laden de pagina's wel, maar tonen ze fouten/leeg op de data.

20. [samen] Beslissen: krijgt de live-DB de nette tabellen, of bouwen we een vertaallaag (SQL-views) vanuit de ruwe tabellen?
21. [ik, bij vertaallaag] SQL-views maken die de ruwe tabellen omzetten naar wat het dashboard verwacht.
22. [samen] Verifiëren dat de datapagina's nu echte cijfers tonen.
23. [jij/DBA] Read-only rol `chat_readonly` in Postgres aanmaken (SQL staat in CLAUDE.md).
24. [ik] `CHAT_DB_PASSWORD` invullen, image herbouwen + opnieuw pushen, container hermaken -> chat aan.

## Fase 5 — Productie-nazorg

25. [jij] Dashboard-wachtwoord in een wachtwoordmanager zetten.
26. [jij] Spend-limit op de OpenRouter-API-sleutel instellen (kosten-/misbruik-rem).
27. [jij] Controleren dat het logs-volume schrijfbaar is en de rotatie loopt (5 MB x 5).
28. [optioneel] Monitoring: `scripts/healthcheck_alert.py` op een schema (Task Scheduler/cron).
29. [ik] Update-procedure vastleggen: nieuw image -> pushen -> container hermaken (volume blijft, logs/config behouden).
30. [ik] `DEPLOY-ixrouter.md` + wiki bijwerken met de definitieve waarden en status "live".

---

## Afhankelijkheden (kort)

- Fase 1 hangt op stap 1-2 (VPN/registry bereikbaar). Alles daarvoor staat klaar.
- Fase 2 vereist jouw IXON-login (kan ik niet doen).
- Fase 3 kan zodra de container draait.
- Fase 4 is nodig voor échte data; het dashboard draait al zonder, maar toont dan geen cijfers.
- Fase 5 is nazorg, kan deels later.

## Eerstvolgende actie

Stap 1 + 2: VPN naar het DGS-net aan, dan `curl.exe http://192.168.23.254:5000/v2/`. Geeft dat `{}`,
zeg het me, dan pak ik stap 3-6 (de push) meteen op.
