# DGS Optimax

Optimax: interactief productie- en alarmdashboard voor de DGS-fabriek. Leest uit dezelfde PostgreSQL database als het bestaande alarm-report, maar biedt een interactieve UI in plaats van een dagelijkse e-mail.

**Features:**
- Overzicht met KPI-kaarten, top-alarmen bar chart en severity pie chart
- Doorzoekbare alarmenlijst met filters (severity, zoektekst) en paginering
- Trendgrafiek (7/14/30 dagen) met geactiveerde vs. verholpen alarmen

---

## Voorbereiding

Kopieer het voorbeeld-bestand en vul de database credentials in:

```bash
cp .env.example .env
```

De database-instellingen zijn identiek aan die van het alarm-report (`192.168.23.254`, `db_dgs_01`).

---

## Draaien met Docker (aanbevolen)

**Vereisten:** Docker Desktop geinstalleerd en draaiend.

```bash
docker compose up --build
```

Open `http://localhost:8080` (of `http://<machine-ip>:8080` vanuit het netwerk).

---

## Lokaal ontwikkelen

**Vereisten:** Python 3.12+, Node.js 20+

### Backend

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8080
```

### Frontend (aparte terminal)

```bash
cd frontend
npm install
npm run dev
```

De Vite dev server draait op `http://localhost:5173` en proxied `/api` naar de backend op poort 8080.

---

## Projectstructuur

| Map/Bestand | Doel |
|---|---|
| `backend/main.py` | FastAPI app, dient API + statische frontend |
| `backend/database.py` | Async PostgreSQL connectie pool (asyncpg) |
| `backend/routers/alarms.py` | API endpoints: stats, top, list, trends |
| `backend/config.py` | Settings uit environment variabelen |
| `frontend/` | React + Vite + TypeScript + Tailwind |
| `frontend/src/pages/` | Overview, AlarmList, Trends pagina's |
| `Dockerfile` | Multi-stage build (Node + Python) |
| `docker-compose.yml` | Productie container setup |

## API Endpoints

| Methode | Pad | Omschrijving |
|---------|-----|--------------|
| GET | `/api/alarms/stats?date=YYYY-MM-DD` | KPI statistieken voor een dag |
| GET | `/api/alarms/top?date=YYYY-MM-DD&limit=10` | Top N alarmen op trigger count |
| GET | `/api/alarms/list?date=YYYY-MM-DD&severity=Error&search=pomp&page=1` | Gefilterde alarmenlijst |
| GET | `/api/alarms/trends?from=YYYY-MM-DD&to=YYYY-MM-DD` | Dagelijkse alarm counts voor trendgrafiek |
| GET | `/api/health` | Gezondheidscheck (database connectiviteit) |

## Troubleshooting

### Database niet bereikbaar

- Controleer of je op het DGS-netwerk zit (192.168.23.x)
- Ping de DB: `ping 192.168.23.254`
- Controleer `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` in `.env`
- Bij Docker: gebruik `host.docker.internal` als `DB_HOST` als de DB op de host draait
