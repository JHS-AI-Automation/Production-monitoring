"""
Pallet KPI's afgeleid uit de DGS palletstatus-data.

=== DATA-BRON ===

palletstatus:
    Elke rij = 1 meetmoment met status per palletstation.
    - time (timestamp): meetmoment
    - pallet6000, pallet6005, pallet6010, pallet6015 (int): statuscode per station

    Stations zijn vernoemd naar de IX6000 edge device poorten.

    Status-mapping:
        100 = geen pallet aanwezig (station is leeg/onbezet)
        200 = pallet leeg (staat op station, wacht op vulling)
        300 = pallet klaar (gevuld, klaar voor transport)

=== KPI OVERZICHT ===

1. Bezettingsgraad per station
   % tijd dat status = 300 (klaar) van totale meetmomenten
   Formule: COUNT(status=300) / COUNT(*) * 100

2. Leeg-wachttijd per station
   % tijd dat status = 200 (leeg, wacht op vulling)
   Formule: COUNT(status=200) / COUNT(*) * 100

3. Geen-pallet-tijd per station
   % tijd dat status = 100 (geen pallet aanwezig)
   Formule: COUNT(status=100) / COUNT(*) * 100

4. Bezettingsgraad per uur (tijdlijn)
   Per uur het percentage "klaar" per station, voor tijdlijn-analyse
"""

from datetime import date

from fastapi import APIRouter, Query

from backend.database import get_connection
from backend.timewindow import validate_date

router = APIRouter(prefix="/api/pallets", tags=["pallets"])

STATIONS = [
    {"id": "6000", "column": "pallet6000"},
    {"id": "6005", "column": "pallet6005"},
    {"id": "6010", "column": "pallet6010"},
    {"id": "6015", "column": "pallet6015"},
]


@router.get("/summary")
async def get_pallet_summary(target_date: date = Query(default=None, alias="date")):
    """Dagelijkse palletstatus-samenvatting per station."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # --- Bezettingsgraad per station ---
        # Formule per station: COUNT(*) FILTER (WHERE palletXXXX = status) / COUNT(*) * 100
        # Dit geeft het percentage van de dag dat elk station in elke status was.
        # Status 300 (klaar) = productief, Status 200 (leeg) = wachtend, Status 100 = onbezet
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_readings,

                -- Station 6000: bezettingspercentages
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6000 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6000_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6000 = 200)
                    / NULLIF(COUNT(*), 0), 1) AS s6000_empty_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6000 = 100)
                    / NULLIF(COUNT(*), 0), 1) AS s6000_none_pct,

                -- Station 6005: bezettingspercentages
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6005 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6005_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6005 = 200)
                    / NULLIF(COUNT(*), 0), 1) AS s6005_empty_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6005 = 100)
                    / NULLIF(COUNT(*), 0), 1) AS s6005_none_pct,

                -- Station 6010: bezettingspercentages
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6010 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6010_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6010 = 200)
                    / NULLIF(COUNT(*), 0), 1) AS s6010_empty_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6010 = 100)
                    / NULLIF(COUNT(*), 0), 1) AS s6010_none_pct,

                -- Station 6015: bezettingspercentages
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6015 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6015_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6015 = 200)
                    / NULLIF(COUNT(*), 0), 1) AS s6015_empty_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6015 = 100)
                    / NULLIF(COUNT(*), 0), 1) AS s6015_none_pct

            FROM palletstatus
            WHERE time >= $1::date AND time < $1::date + 1
            """,
            target_date,
        )

    stations = []
    for s in STATIONS:
        sid = s["id"]
        stations.append({
            "id": sid,
            "ready_pct": float(row[f"s{sid}_ready_pct"] or 0),
            "empty_pct": float(row[f"s{sid}_empty_pct"] or 0),
            "none_pct": float(row[f"s{sid}_none_pct"] or 0),
        })

    return {
        "date": target_date.isoformat(),
        "total_readings": int(row["total_readings"]),
        "stations": stations,
    }


@router.get("/hourly")
async def get_hourly_pallet_status(target_date: date = Query(default=None, alias="date")):
    """Bezettingsgraad per station per uur (voor tijdlijn-grafiek)."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # --- Bezettingsgraad per uur per station ---
        # Formule: per uur het percentage meetmomenten met status = 300 (klaar)
        # Geeft inzicht in wanneer stations productief zijn vs wachtend/onbezet
        # NULLIF voorkomt deling door nul als er geen data in dat uur is
        rows = await conn.fetch(
            """
            SELECT
                date_trunc('hour', time) AS hour,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6000 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6000_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6005 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6005_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6010 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6010_ready_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE pallet6015 = 300)
                    / NULLIF(COUNT(*), 0), 1) AS s6015_ready_pct
            FROM palletstatus
            WHERE time >= $1::date AND time < $1::date + 1
            GROUP BY date_trunc('hour', time)
            ORDER BY hour
            """,
            target_date,
        )

    return [
        {
            "hour": r["hour"].strftime("%H:%M"),
            "s6000": float(r["s6000_ready_pct"] or 0),
            "s6005": float(r["s6005_ready_pct"] or 0),
            "s6010": float(r["s6010_ready_pct"] or 0),
            "s6015": float(r["s6015_ready_pct"] or 0),
        }
        for r in rows
    ]
