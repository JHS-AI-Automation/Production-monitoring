"""
Productie KPI's afgeleid uit de DGS productiedata.

=== DATA-BRONNEN ===

capacity_perminutev2 - productie-tellers:
    Elke rij = 1 minuut meetdata van de productielijn.
    - time (timestamp): meetmoment
    - counter0..counter3 (int): aantal producten geteld per lijn in die minuut
    Mapping: counter0=Lijn 1, counter1=Lijn 2, counter2=Lijn 3, counter3=Lijn 4

plc_alarms - alarm-events (voor cross-table KPI's):
    - time (timestamp): tijdstip event
    - incomingstate (int): 1 = alarm geactiveerd, 0 = alarm opgelost
    - alarmmessage (text): beschrijving van het alarm

=== CONSTANTEN ===

Shifttijd: 05:00 - 23:00 (18 uur = 1080 minuten productietijd)
Buiten shift wordt niet geproduceerd, stilstand alleen binnen shift geteld.

=== KPI OVERZICHT ===

1. Totaal productie per dag per lijn
   SUM(counterX) over alle minuten van de dag

2. Stilstand-minuten per lijn
   COUNT rijen waar counterX = 0 binnen shift (05:00-23:00)

3. Piekuur productie
   Het uur met de hoogste totale productie over alle lijnen

4. Lijn-balans ratio
   MIN(lijn-totaal) / MAX(lijn-totaal), ideaal = 1.0

5. MTTR (Mean Time To Resolve)
   Gemiddelde tijd tussen alarm-activatie en -resolutie per alarm
   Pairing: per alarmmessage kijkt LEAD() naar het eerstvolgende event.
   Alleen paren waar state=1 gevolgd door state=0 tellen als opgelost.
   Orphaned resolves (state=0 zonder voorafgaande state=1) worden gefilterd.

6. Alarm-impact op throughput
   Vergelijking productie per minuut tijdens alarm vs zonder alarm

7. Alarm-productie correlatie per uur
   Aantal alarmen naast totale productie per uur
"""

from datetime import date, time, timedelta

from fastapi import APIRouter, HTTPException, Query

from backend.database import get_connection

router = APIRouter(prefix="/api/production", tags=["production"])

SHIFT_START = time(5, 0)
SHIFT_END = time(23, 0)
SHIFT_MINUTES = 1080
MAX_TREND_DAYS = 365
TZ = "Europe/Amsterdam"


def _validate_date(target_date: date | None) -> date:
    if target_date is None:
        return date.today() - timedelta(days=1)
    if target_date > date.today():
        raise HTTPException(400, f"Datum {target_date} ligt in de toekomst")
    return target_date


def _validate_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    if date_to is None:
        date_to = date.today() - timedelta(days=1)
    if date_from is None:
        date_from = date_to - timedelta(days=29)
    if date_to > date.today():
        raise HTTPException(400, f"Einddatum {date_to} ligt in de toekomst")
    if date_from > date_to:
        raise HTTPException(400, "Startdatum mag niet na einddatum liggen")
    if (date_to - date_from).days > MAX_TREND_DAYS:
        raise HTTPException(400, f"Maximale periode is {MAX_TREND_DAYS} dagen")
    return date_from, date_to


@router.get("/summary")
async def get_production_summary(target_date: date = Query(default=None, alias="date")):
    """Dagelijkse productie-samenvatting met kern-KPI's per lijn."""
    target_date = _validate_date(target_date)

    async with get_connection() as conn:
        # --- KPI 1: Totaal productie per lijn ---
        # Formule: SUM(counterX) over alle minuten van de dag
        # Eenheid: producten per lijn per dag
        totals = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(counter0), 0) AS line_0,
                COALESCE(SUM(counter1), 0) AS line_1,
                COALESCE(SUM(counter2), 0) AS line_2,
                COALESCE(SUM(counter3), 0) AS line_3
            FROM capacity_perminutev2
            WHERE time::date = $1
            """,
            target_date,
        )

        # --- KPI 2: Stilstand-minuten per lijn ---
        # Formule: COUNT rijen waar counterX = 0 binnen shift (05:00-23:00)
        # Elke rij = 1 minuut meetdata, dus COUNT = minuten zonder productie op die lijn
        downtime = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE counter0 = 0) AS line_0,
                COUNT(*) FILTER (WHERE counter1 = 0) AS line_1,
                COUNT(*) FILTER (WHERE counter2 = 0) AS line_2,
                COUNT(*) FILTER (WHERE counter3 = 0) AS line_3,
                COUNT(*) AS total_shift_minutes
            FROM capacity_perminutev2
            WHERE time::date = $1
              AND time::time BETWEEN $2 AND $3
            """,
            target_date,
            SHIFT_START,
            SHIFT_END,
        )

        # --- KPI 3: Piekuur productie ---
        # Formule: het uur met de hoogste SUM(counter0 + counter1 + counter2 + counter3)
        # AT TIME ZONE zorgt dat het uur klopt in Nederlandse tijd
        peak = await conn.fetchrow(
            """
            SELECT
                date_trunc('hour', time AT TIME ZONE $2) AS hour,
                SUM(counter0 + counter1 + counter2 + counter3) AS total
            FROM capacity_perminutev2
            WHERE time::date = $1
            GROUP BY date_trunc('hour', time AT TIME ZONE $2)
            ORDER BY total DESC
            LIMIT 1
            """,
            target_date,
            TZ,
        )

        # --- KPI 5: MTTR (Mean Time To Resolve) ---
        # Per alarm (alarmmessage): LEAD kijkt naar het eerstvolgende event.
        # Paar state=1 -> state=0 = opgelost, tijdsverschil = resolve-tijd.
        # Orphaned resolves (state=0 zonder voorafgaande trigger) worden
        # automatisch gefilterd door WHERE incomingstate = 1.
        mttr = await conn.fetchrow(
            """
            WITH events AS (
                SELECT
                    alarmmessage,
                    time,
                    incomingstate,
                    LEAD(time) OVER (
                        PARTITION BY alarmmessage ORDER BY time
                    ) AS next_time,
                    LEAD(incomingstate) OVER (
                        PARTITION BY alarmmessage ORDER BY time
                    ) AS next_state
                FROM plc_alarms
                WHERE time::date = $1
            )
            SELECT
                ROUND(AVG(EXTRACT(EPOCH FROM (next_time - time)) / 60)::numeric, 1)
                    AS avg_minutes,
                ROUND(MIN(EXTRACT(EPOCH FROM (next_time - time)) / 60)::numeric, 1)
                    AS min_minutes,
                ROUND(MAX(EXTRACT(EPOCH FROM (next_time - time)) / 60)::numeric, 1)
                    AS max_minutes,
                COUNT(*) AS resolved,
                (SELECT COUNT(*) FROM events
                 WHERE incomingstate = 1 AND (next_state IS NULL OR next_state != 0)
                ) AS unresolved
            FROM events
            WHERE incomingstate = 1 AND next_state = 0
            """,
            target_date,
        )

    per_line = [int(totals[f"line_{i}"]) for i in range(4)]
    grand_total = sum(per_line)
    dt_minutes = [int(downtime[f"line_{i}"]) for i in range(4)]

    # --- KPI 4: Lijn-balans ratio ---
    # Formule: MIN(lijn-totaal) / MAX(lijn-totaal)
    # Bereik: 0.0 - 1.0
    # 1.0 = alle lijnen even productief (perfecte balans)
    # < 0.7 = scheve verdeling, duidt op bottleneck of storing op een lijn
    max_line = max(per_line) if per_line else 0
    line_balance = round(min(per_line) / max_line, 2) if max_line > 0 else None

    return {
        "date": target_date.isoformat(),
        "grand_total": grand_total,
        "per_line": per_line,
        "downtime_minutes": dt_minutes,
        "shift_minutes": SHIFT_MINUTES,
        "peak_hour": peak["hour"].strftime("%H:%M") if peak and peak["hour"] else None,
        "peak_hour_total": int(peak["total"]) if peak and peak["total"] else 0,
        "line_balance": line_balance,
        "mttr_avg_minutes": float(mttr["avg_minutes"]) if mttr and mttr["avg_minutes"] else None,
        "mttr_min_minutes": float(mttr["min_minutes"]) if mttr and mttr["min_minutes"] else None,
        "mttr_max_minutes": float(mttr["max_minutes"]) if mttr and mttr["max_minutes"] else None,
        "mttr_resolved": int(mttr["resolved"]) if mttr and mttr["resolved"] else 0,
        "mttr_unresolved": int(mttr["unresolved"]) if mttr and mttr["unresolved"] else 0,
    }


@router.get("/hourly")
async def get_hourly_production(target_date: date = Query(default=None, alias="date")):
    """Productie per lijn per uur, voor de uurlijkse productiegrafiek."""
    target_date = _validate_date(target_date)

    async with get_connection() as conn:
        # --- Throughput per lijn per uur ---
        # Formule: SUM(counterX) gegroepeerd per uur
        # Eenheid: producten per lijn per uur
        rows = await conn.fetch(
            """
            SELECT
                date_trunc('hour', time AT TIME ZONE $2) AS hour,
                COALESCE(SUM(counter0), 0) AS line_0,
                COALESCE(SUM(counter1), 0) AS line_1,
                COALESCE(SUM(counter2), 0) AS line_2,
                COALESCE(SUM(counter3), 0) AS line_3
            FROM capacity_perminutev2
            WHERE time::date = $1
            GROUP BY date_trunc('hour', time AT TIME ZONE $2)
            ORDER BY hour
            """,
            target_date,
            TZ,
        )

    return [
        {
            "hour": r["hour"].strftime("%H:%M"),
            "line_0": int(r["line_0"]),
            "line_1": int(r["line_1"]),
            "line_2": int(r["line_2"]),
            "line_3": int(r["line_3"]),
            "total": sum(int(r[f"line_{i}"]) for i in range(4)),
        }
        for r in rows
    ]


@router.get("/minutely")
async def get_minutely_production(
    target_date: date = Query(default=None, alias="date"),
    hour: int = Query(ge=0, le=23),
):
    """Per-minuut productiedata voor een specifiek uur (inzoom voor lijnverdeling)."""
    target_date = _validate_date(target_date)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                date_trunc('minute', time AT TIME ZONE $3) AS minute,
                COALESCE(SUM(counter0), 0) AS line_0,
                COALESCE(SUM(counter1), 0) AS line_1,
                COALESCE(SUM(counter2), 0) AS line_2,
                COALESCE(SUM(counter3), 0) AS line_3
            FROM capacity_perminutev2
            WHERE time::date = $1
              AND EXTRACT(HOUR FROM time AT TIME ZONE $3) = $2
            GROUP BY date_trunc('minute', time AT TIME ZONE $3)
            ORDER BY minute
            """,
            target_date,
            hour,
            TZ,
        )

    return [
        {
            "minute": r["minute"].strftime("%H:%M"),
            "line_0": int(r["line_0"]),
            "line_1": int(r["line_1"]),
            "line_2": int(r["line_2"]),
            "line_3": int(r["line_3"]),
            "total": sum(int(r[f"line_{i}"]) for i in range(4)),
        }
        for r in rows
    ]


@router.get("/trends")
async def get_production_trends(
    date_from: date = Query(default=None, alias="from"),
    date_to: date = Query(default=None, alias="to"),
):
    """Dagelijkse productie-trend over een periode, voor trendgrafiek."""
    date_from, date_to = _validate_range(date_from, date_to)

    async with get_connection() as conn:
        # --- Dagelijkse productie-trend ---
        # Formule: SUM(counterX) per dag, alle lijnen
        rows = await conn.fetch(
            """
            SELECT
                time::date AS day,
                COALESCE(SUM(counter0), 0) AS line_0,
                COALESCE(SUM(counter1), 0) AS line_1,
                COALESCE(SUM(counter2), 0) AS line_2,
                COALESCE(SUM(counter3), 0) AS line_3
            FROM capacity_perminutev2
            WHERE time::date BETWEEN $1 AND $2
            GROUP BY day
            ORDER BY day
            """,
            date_from,
            date_to,
        )

    return [
        {
            "date": r["day"].isoformat(),
            "line_0": int(r["line_0"]),
            "line_1": int(r["line_1"]),
            "line_2": int(r["line_2"]),
            "line_3": int(r["line_3"]),
            "total": sum(int(r[f"line_{i}"]) for i in range(4)),
        }
        for r in rows
    ]


@router.get("/alarm-impact")
async def get_alarm_impact(target_date: date = Query(default=None, alias="date")):
    """Cross-table analyse: alarm-impact op productie-throughput."""
    target_date = _validate_date(target_date)

    async with get_connection() as conn:
        # --- KPI 6: Alarm-impact op throughput ---
        # Vergelijk gemiddelde productie (producten/minuut) TIJDENS actief alarm vs ZONDER alarm.
        impact = await conn.fetchrow(
            """
            WITH alarm_minutes AS (
                SELECT DISTINCT date_trunc('minute', time) AS minute
                FROM plc_alarms
                WHERE time::date = $1 AND incomingstate = 1
            )
            SELECT
                ROUND(AVG(CASE WHEN am.minute IS NOT NULL
                    THEN c.counter0 + c.counter1 + c.counter2 + c.counter3
                    END)::numeric, 1) AS avg_during_alarm,
                ROUND(AVG(CASE WHEN am.minute IS NULL
                    THEN c.counter0 + c.counter1 + c.counter2 + c.counter3
                    END)::numeric, 1) AS avg_without_alarm,
                COUNT(*) FILTER (WHERE am.minute IS NOT NULL) AS alarm_minutes,
                COUNT(*) FILTER (WHERE am.minute IS NULL) AS normal_minutes
            FROM capacity_perminutev2 c
            LEFT JOIN alarm_minutes am
                ON date_trunc('minute', c.time) = am.minute
            WHERE c.time::date = $1
            """,
            target_date,
        )

        # --- KPI 7: Alarm-productie correlatie per uur ---
        correlation = await conn.fetch(
            """
            SELECT
                h.hour,
                COALESCE(p.total, 0) AS production,
                COALESCE(a.alarm_count, 0) AS alarms
            FROM generate_series(
                ($1::date + '00:00'::time)::timestamp,
                ($1::date + '23:00'::time)::timestamp,
                '1 hour'
            ) AS h(hour)
            LEFT JOIN (
                SELECT
                    date_trunc('hour', time) AS hour,
                    SUM(counter0 + counter1 + counter2 + counter3) AS total
                FROM capacity_perminutev2
                WHERE time::date = $1
                GROUP BY date_trunc('hour', time)
            ) p ON h.hour = p.hour
            LEFT JOIN (
                SELECT
                    date_trunc('hour', time) AS hour,
                    COUNT(*) AS alarm_count
                FROM plc_alarms
                WHERE time::date = $1 AND incomingstate = 1
                GROUP BY date_trunc('hour', time)
            ) a ON h.hour = a.hour
            ORDER BY h.hour
            """,
            target_date,
        )

    avg_during = float(impact["avg_during_alarm"]) if impact["avg_during_alarm"] else None
    avg_without = float(impact["avg_without_alarm"]) if impact["avg_without_alarm"] else None

    # Productieverlies-percentage:
    # Formule: (1 - avg_during / avg_without) * 100
    # Positief = verlies, negatief = onverwachte stijging (data-ruis)
    loss_pct = None
    if avg_during is not None and avg_without is not None and avg_without > 0:
        loss_pct = round((1 - avg_during / avg_without) * 100, 1)

    return {
        "date": target_date.isoformat(),
        "avg_during_alarm": avg_during,
        "avg_without_alarm": avg_without,
        "alarm_minutes": int(impact["alarm_minutes"]),
        "normal_minutes": int(impact["normal_minutes"]),
        "production_loss_pct": loss_pct,
        "hourly_correlation": [
            {
                "hour": r["hour"].strftime("%H:%M"),
                "production": int(r["production"]),
                "alarms": int(r["alarms"]),
            }
            for r in correlation
        ],
    }
