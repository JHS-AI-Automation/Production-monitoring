# Optimax backlog: 100 taken

Brede backlog om Optimax van "bijna gedeployed" naar "productie-waardig, overgedragen product"
te brengen. 11 categorieen, doorlopend genummerd 1-100. Aanvulling op het deploy-stappenplan
([optimax-stappenplan.md](optimax-stappenplan.md), de 30 directe deploy-stappen); enige overlap
op data/chat is bewust.

Laatst bijgewerkt: 2026-06-10. `[jij]` = jouw/IXON/IT-handeling, `[ik]` = scriptbaar door mij, `[samen]` = beslissing.

## A. Deploy & router (1-8)

1. [ik] Twee-staps build/push-pad in `build-ixrouter.sh` (build met VPN uit, push met VPN aan) als fallback.
2. [ik] Image taggen met git-commit naast `latest` (`optimax:<commit>`) voor traceerbaarheid/rollback.
3. [ik] Image-grootte minimaliseren (`.dockerignore`-dekking, geen overbodige bestanden in `static`/backend).
4. [ik] Healthcheck-startperiode afstemmen op trage ARM/emulatie-boot.
5. [jij] Container resource-limieten (memory/CPU) zetten zodat Optimax Postgres/Node-RED/Grafana niet verdringt.
6. [jij] Herstart-na-reboot testen (overleeft de container een stroomuitval van de IX6000?).
7. [ik] Poortbezetting documenteren (80/3000/8080/8081 bezet, 9000 vrij).
8. [jij] Rollback testen: vorige image-tag terugzetten via de IXON-UI.

## B. Database & datalaag (9-22)

9. [samen] Besluit: nette tabellen op de live-DB, of SQL-views vanuit de ruwe tabellen.
10. [ik] Kolom-mapping documenteren: ruwe (`readconfig2`/`readstartstop3`/`test024`) -> dashboard-kolommen.
11. [ik] View `plc_alarms` bouwen vanuit de ruwe alarm-bron.
12. [ik] View `capacity_perminutev2` bouwen (counters per lijn per minuut).
13. [ik] View `palletstatus` bouwen (statuscodes per station).
14. [ik] View-performance testen (dashboard-queries < 2s, conform capaciteitsanalyse).
15. [jij/Tim] B-tree indexen op de `time`-kolommen bevestigen/aanmaken.
16. [ik] Range-partitionering per dag voorbereiden (limiet x10) voor toekomstige load.
17. [ik] Retentie-beleid (90 dagen) als job in Postgres.
18. [jij] M.2 SSD-installatie bevestigen (5 GB eMMC loopt anders binnen weken vol).
19. [ik] Tabelgroei wekelijks loggen (monitoring-query uit de analyse).
20. [jij] `machines`/`production_lines` vullen indien beschikbaar (echte lijnnamen).
21. [ik] Tijdzone-consistentie controleren (`AT TIME ZONE 'Europe/Amsterdam'`) tegen de ruwe data.
22. [jij] Aparte read-only DB-rol voor de app i.p.v. het `dgs`-hoofdaccount.

## C. Security hardening (23-36)

23. [jij] App-DB-gebruiker naar read-only downgraden (least privilege).
24. [jij] `chat_readonly`-rol aanmaken, rechten beperken tot SELECT op de 4 tabellen/views.
25. [ik] Secrets uit het image halen zodra de router env-vars/volume ondersteunt.
26. [jij] Dashboard-wachtwoord roteren na de eerste test (het gegenereerde was in chat zichtbaar).
27. [samen] HTTPS voor het dashboard overwegen (reverse proxy of IXON-publicatie met TLS).
28. [ik] API-brede rate-limiting overwegen (nu alleen op de chat).
29. [ik] Security headers toevoegen (CSP, X-Frame-Options, HSTS).
30. [ik] CORS expliciet dichtzetten en bevestigen.
31. [ik] `CHAT_TLS_VERIFY=true` afdwingen in productie.
32. [ik] Read-only rootfs voor de container overwegen (draait al non-root, uid 10001).
33. [ik] Image scannen op kwetsbaarheden (Trivy/Docker Scout), base-images updaten.
34. [ik] Dependency-audit (`pip-audit` + `npm audit`) en pinnen.
35. [jij] Toegang tot de registry (`:5000`) afschermen (nu open op het LAN).
36. [ik] Security-review-light op de gedeployde app (bestaand review-patroon).

## D. Observability & monitoring (37-46)

37. [ik] Logs naar Loki/Grafana (draait al op de IX6000).
38. [jij] Healthcheck-alert (`scripts/healthcheck_alert.py`) op een schema.
39. [jij] Externe uptime-monitoring op `/api/health`.
40. [ik] Request-metrics (Prometheus-export) in de backend.
41. [ik] Grafana-dashboard voor Optimax-app-metrics.
42. [ik] Alert bij DB-pool `null` (database weggevallen).
43. [ik] Logniveau per omgeving instelbaar houden (al via env).
44. [ik] `request_id` doorzoekbaar maken in de logs.
45. [jij] Schijfruimte-alert op de IX6000 (eMMC/SSD vol).
46. [ik] Chat-tokens/kosten loggen en dashboarden (budgetbewaking).

## E. Reliability, backup & ops (47-56)

47. [jij] Backup-strategie voor de Postgres-DB (schema, frequentie, locatie).
48. [jij] Restore-procedure testen.
49. [ik] Update-runbook: nieuw image -> push -> container hermaken.
50. [ik] Rollback-runbook: vorige tag terugzetten.
51. [jij] Back-up/rotatie-beleid voor het `optimax-logs`-volume.
52. [ik] Documenteren hoe je de container herstart/stopt via de IXON-UI.
53. [ik] VPN-uitval-scenario documenteren (dashboard blind; edge-AI als mitigatie).
54. [ik] Capaciteits-drempels bewaken (5M rijen/dag query-grens).
55. [jij] NTP/tijd-synchronisatie op de IX6000 bevestigen.
56. [jij] Onderhoudsvenster met DGS afspreken voor updates.

## F. Testing & QA (57-66)

57. [ik] Backend unit-tests (pytest) voor de KPI-queries.
58. [ik] Test-fixtures met dummy-data (`generate_dummy_data.py`).
59. [ik] Frontend-test-toolchain opzetten (vitest).
60. [ik] End-to-end smoke-test (Playwright) tegen een draaiende instance.
61. [samen] KPI-validatie: dashboard-cijfers vs. handmatige SQL.
62. [ik] OEE-berekening valideren tegen een bekende dag.
63. [ik] MTTR-pairing testen op edge-cases (orphaned resolves).
64. [ik] Lasttest: dashboard-snelheid bij ~5M rijen (simuleren).
65. [ik] Foutpad-tests: DB weg, chat-key leeg, lege dataset.
66. [jij] Cross-browser/mobiel testen (responsive layout).

## G. Frontend & UX (67-76)

67. [ik] Loading-/empty-/error-states op alle pagina's nalopen.
68. [ik] Datumkiezer: default "gisteren" + sneltoetsen (vandaag/week).
69. [ik] Toegankelijkheid (contrast, toetsenbord, ARIA).
70. [ik] Eindgebruiker-vriendelijke melding bij DB-down.
71. [jij/ik] Branding finaliseren (DGS-logo, kleuren via `brand.js`).
72. [ik] Favicon, titel en meta controleren.
73. [ik] Locale (nl-NL) overal consistent.
74. [ik] Grafiek-tooltips en legenda's op duidelijkheid nalopen.
75. [jij] Mobiele weergave van de productie-flow-diagram testen.
76. [ik] "Laatst bijgewerkt"-indicator + optionele auto-refresh.

## H. AI-chat (77-84)

77. [jij/ik] `chat_readonly` koppelen en de chat aanzetten.
78. [ik] SQL-sanitizer uitbreiden + testen tegen injectie-edge-cases.
79. [ik] Dagelijks tokenbudget (`CHAT_DAILY_TOKEN_BUDGET`) instellen + testen.
80. [ik] Schema-context in de prompt bijwerken naar de echte tabellen/views.
81. [ik] Voorbeeldvragen afstemmen op DGS-data.
82. [samen] Antwoordkwaliteit testen op een golden set van 10 vragen.
83. [ik] Chat-audit: uitgevoerde SQL loggen.
84. [ik] Fallback testen als OpenRouter onbereikbaar is.

## I. Documentatie & overdracht (85-92)

85. [ik] README bijwerken met router-deploy en echte waarden.
86. [ik] `DEPLOY-ixrouter.md` finaliseren met status "live".
87. [ik] Gebruikershandleiding voor DGS (1 pagina: inloggen, pagina's, chat).
88. [ik] Beheerdershandleiding voor IT (update/rollback/backup).
89. [ik] `ARCHITECTURE.md` bijwerken met de live-situatie.
90. [ik] Wiki-pagina DGS bijwerken (Optimax live, IP's, contactpersonen).
91. [jij] Overdracht-sessie met Tim/Marc plannen.
92. [jij] Wachtwoorden/sleutels netjes overdragen (wachtwoordmanager).

## J. Compliance & governance (93-98)

93. [samen] AVG-check: welke (persoons)gegevens in de data, vastleggen.
94. [samen] Toegangsbeleid: wie mag het dashboard zien (auth + netwerk).
95. [ik] AI Act-classificatie van de chat-functie noteren.
96. [samen] Bewaartermijn logging vastleggen (privacy).
97. [jij] DPA/verwerkersafspraken bij OpenRouter checken (data verlaat netwerk via chat).
98. [jij] Thomas-akkoord op klant-uitlevering (governance-regel).

## K. Product & roadmap (99-100)

99. [ik] Edge-AI alarm-anomaly-detection als losse container (sterk aanbevolen in de capaciteitsanalyse).
100. [samen] Predictive-maintenance-fase voorbereiden (3-6 mnd gelabelde data verzamelen).

---

## Prioriteit (suggestie)

- **Nu/blokkerend:** A1-A8, B9-B14, D38-D39 (live krijgen + data tonen).
- **Voor klant-go-live:** C23-C26, C31, I85-I92, J93-J98 (veilig + overgedragen).
- **Daarna:** F (tests), G (UX-polish), D/E (monitoring/ops), H (chat aan).
- **Roadmap:** K99-K100 (edge-AI, predictive maintenance).
