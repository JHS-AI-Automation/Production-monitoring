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

STATIONS = ["6000", "6005", "6010", "6015"]

# Statuscode per API-label (zie module-docstring): klaar / leeg-wachtend / geen pallet.
STATUS_CODES = {"ready": 300, "empty": 200, "none": 100}


def _pct_col(station: str, label: str, code: int) -> str:
    """SQL-kolom: percentage meetmomenten waarin het station deze statuscode had.

    Wordt uitsluitend gevuld vanuit de STATIONS/STATUS_CODES-constanten hierboven
    (nooit user-input), dus veilig als f-string. NULLIF voorkomt deling door nul.
    """
    return (
        f"ROUND(100.0 * COUNT(*) FILTER (WHERE pallet{station} = {code})"
        f" / NULLIF(COUNT(*), 0), 1) AS s{station}_{label}_pct"
    )


@router.get("/summary")
async def get_pallet_summary(target_date: date = Query(default=None, alias="date")):
    """Dagelijkse palletstatus-samenvatting per station."""
    target_date = validate_date(target_date)

    # Bezettingsgraad per station: per station x status het percentage van de dag
    # (4 stations x 3 statussen, gegenereerd uit de constanten).
    pct_cols = ",\n                ".join(
        _pct_col(s, label, code)
        for s in STATIONS
        for label, code in STATUS_CODES.items()
    )

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) AS total_readings,
                {pct_cols}
            FROM palletstatus
            WHERE time >= $1::date AND time < $1::date + 1
            """,
            target_date,
        )

    stations = [
        {
            "id": sid,
            **{f"{label}_pct": float(row[f"s{sid}_{label}_pct"] or 0) for label in STATUS_CODES},
        }
        for sid in STATIONS
    ]

    return {
        "date": target_date.isoformat(),
        "total_readings": int(row["total_readings"]),
        "stations": stations,
    }


@router.get("/hourly")
async def get_hourly_pallet_status(target_date: date = Query(default=None, alias="date")):
    """Bezettingsgraad per station per uur (voor tijdlijn-grafiek)."""
    target_date = validate_date(target_date)

    # Per uur het percentage meetmomenten met status 300 (klaar) per station.
    ready_cols = ",\n                ".join(
        _pct_col(s, "ready", STATUS_CODES["ready"]) for s in STATIONS
    )

    async with get_connection() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                date_trunc('hour', time) AS hour,
                {ready_cols}
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
            **{f"s{sid}": float(r[f"s{sid}_ready_pct"] or 0) for sid in STATIONS},
        }
        for r in rows
    ]
