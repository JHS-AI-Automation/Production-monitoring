"""
Productie KPI's afgeleid uit de DGS productiedata.

=== DATA-BRONNEN ===

capacity_perminutev2 - productie-tellers:
    Elke rij = 1 minuut meetdata van de productielijn.
    - time (timestamp): meetmoment
    - counter0..counter3 (int): aantal producten geteld per lijn in die minuut
    Mapping: counter0=Lijn 1, counter1=Lijn 2, counter2=Lijn 3, counter3=Lijn 4
    Model: lijn 1 en 4 = wat de robot aflegt (robot-output); lijn 2 en 3 = overflow
    (de rest die na de robot overblijft).

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

8. OEE (Overall Equipment Effectiveness)
   OEE = Availability x Performance x Quality
   - Availability = (shift_minutes - downtime) / shift_minutes
   - Performance = actual_output / (uptime_minutes x ideal_rate)
     ideal_rate = 95e percentiel van per-minuut output tijdens uptime
   - Quality = 100% (geen uitvaldata beschikbaar uit PLC, placeholder)
   Six Big Losses: Equipment Failure (Error-alarmen), Minor Stops (Warning),
   Speed Loss (onderprestatie t.o.v. ideal rate), Quality Loss (placeholder 0)
"""

from datetime import date, time

from fastapi import APIRouter, Query

from backend.database import get_connection
from backend.timewindow import validate_date, validate_range

router = APIRouter(prefix="/api/production", tags=["production"])

SHIFT_START = time(5, 0)
SHIFT_END = time(23, 0)
SHIFT_MINUTES = 1080
TZ = "Europe/Amsterdam"


def _line_payload(row, label_key: str, label_value) -> dict:
    """Bouw een rij voor de productie-grafieken: 4 lijntotalen + som.

    `label_key` is "hour", "minute" of "date"; `label_value` de bijbehorende waarde.
    Vervangt de identieke dict die in hourly/minutely/trends werd herhaald.
    """
    lines = {f"line_{i}": int(row[f"line_{i}"]) for i in range(4)}
    return {label_key: label_value, **lines, "total": sum(lines.values())}


@router.get("/summary")
async def get_production_summary(target_date: date = Query(default=None, alias="date")):
    """Dagelijkse productie-samenvatting met kern-KPI's per lijn."""
    target_date = validate_date(target_date)

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
            WHERE time >= $1::date AND time < $1::date + 1
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
            WHERE time >= $1::date AND time < $1::date + 1
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
            WHERE time >= $1::date AND time < $1::date + 1
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
                WHERE time >= $1::date AND time < $1::date + 1
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
    target_date = validate_date(target_date)

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
            WHERE time >= $1::date AND time < $1::date + 1
            GROUP BY date_trunc('hour', time AT TIME ZONE $2)
            ORDER BY hour
            """,
            target_date,
            TZ,
        )

    return [_line_payload(r, "hour", r["hour"].strftime("%H:%M")) for r in rows]


@router.get("/minutely")
async def get_minutely_production(
    target_date: date = Query(default=None, alias="date"),
    hour: int = Query(ge=0, le=23),
):
    """Per-minuut productiedata voor een specifiek uur (inzoom voor lijnverdeling)."""
    target_date = validate_date(target_date)

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
            WHERE time >= $1::date AND time < $1::date + 1
              AND EXTRACT(HOUR FROM time AT TIME ZONE $3) = $2
            GROUP BY date_trunc('minute', time AT TIME ZONE $3)
            ORDER BY minute
            """,
            target_date,
            hour,
            TZ,
        )

    return [_line_payload(r, "minute", r["minute"].strftime("%H:%M")) for r in rows]


@router.get("/trends")
async def get_production_trends(
    date_from: date = Query(default=None, alias="from"),
    date_to: date = Query(default=None, alias="to"),
):
    """Dagelijkse productie-trend over een periode, voor trendgrafiek."""
    date_from, date_to = validate_range(date_from, date_to)

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
            WHERE time >= $1::date AND time < $2::date + 1
            GROUP BY day
            ORDER BY day
            """,
            date_from,
            date_to,
        )

    return [_line_payload(r, "date", r["day"].isoformat()) for r in rows
    ]


@router.get("/alarm-impact")
async def get_alarm_impact(target_date: date = Query(default=None, alias="date")):
    """Cross-table analyse: alarm-impact op productie-throughput."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # --- KPI 6: Alarm-impact op throughput ---
        # Vergelijk gemiddelde productie (producten/minuut) TIJDENS actief alarm vs ZONDER alarm.
        impact = await conn.fetchrow(
            """
            WITH alarm_minutes AS (
                SELECT DISTINCT date_trunc('minute', time) AS minute
                FROM plc_alarms
                WHERE time >= $1::date AND time < $1::date + 1 AND incomingstate = 1
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
            WHERE c.time >= $1::date AND c.time < $1::date + 1
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
                WHERE time >= $1::date AND time < $1::date + 1
                GROUP BY date_trunc('hour', time)
            ) p ON h.hour = p.hour
            LEFT JOIN (
                SELECT
                    date_trunc('hour', time) AS hour,
                    COUNT(*) AS alarm_count
                FROM plc_alarms
                WHERE time >= $1::date AND time < $1::date + 1 AND incomingstate = 1
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


@router.get("/oee")
async def get_oee(target_date: date = Query(default=None, alias="date")):
    """OEE (Overall Equipment Effectiveness) per lijn en totaal."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_minutes,
                COUNT(*) FILTER (WHERE counter0 = 0) AS dt_0,
                COUNT(*) FILTER (WHERE counter1 = 0) AS dt_1,
                COUNT(*) FILTER (WHERE counter2 = 0) AS dt_2,
                COUNT(*) FILTER (WHERE counter3 = 0) AS dt_3,
                COALESCE(SUM(counter0), 0) AS total_0,
                COALESCE(SUM(counter1), 0) AS total_1,
                COALESCE(SUM(counter2), 0) AS total_2,
                COALESCE(SUM(counter3), 0) AS total_3,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY counter0)
                    FILTER (WHERE counter0 > 0) AS ideal_0,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY counter1)
                    FILTER (WHERE counter1 > 0) AS ideal_1,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY counter2)
                    FILTER (WHERE counter2 > 0) AS ideal_2,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY counter3)
                    FILTER (WHERE counter3 > 0) AS ideal_3
            FROM capacity_perminutev2
            WHERE time >= $1::date AND time < $1::date + 1
              AND time::time BETWEEN $2 AND $3
            """,
            target_date,
            SHIFT_START,
            SHIFT_END,
        )

        alarm_losses = await conn.fetch(
            """
            SELECT
                severityclass,
                COUNT(*) AS event_count
            FROM plc_alarms
            WHERE time >= $1::date AND time < $1::date + 1 AND incomingstate = 1
            GROUP BY severityclass
            """,
            target_date,
        )

    total_min = int(stats["total_minutes"]) if stats["total_minutes"] else 0
    if total_min == 0:
        return {
            "date": target_date.isoformat(),
            "oee": None,
            "availability": None,
            "performance": None,
            "quality": 100.0,
            "per_line": [],
            "losses": None,
            "six_big_losses": [],
        }

    per_line = []
    total_downtime = 0
    total_speed_loss = 0
    oee_values = []

    for i in range(4):
        dt = int(stats[f"dt_{i}"])
        total = int(stats[f"total_{i}"])
        ideal = float(stats[f"ideal_{i}"]) if stats[f"ideal_{i}"] else 0
        uptime = total_min - dt

        availability = uptime / total_min if total_min > 0 else 0
        if uptime > 0 and ideal > 0:
            performance = total / (uptime * ideal)
            performance = min(performance, 1.0)
        else:
            performance = 0
        quality = 1.0
        oee = availability * performance * quality

        speed_loss_min = round((1 - performance) * uptime) if uptime > 0 else 0
        total_downtime += dt
        total_speed_loss += speed_loss_min
        oee_values.append(oee)

        per_line.append({
            "line": i,
            "name": f"Lijn {i + 1}",
            "oee": round(oee * 100, 1),
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
            "downtime_minutes": dt,
            "speed_loss_minutes": speed_loss_min,
        })

    avg_downtime = round(total_downtime / 4)
    avg_speed_loss = round(total_speed_loss / 4)
    avg_oee = round(sum(oee_values) / len(oee_values) * 100, 1) if oee_values else 0

    avg_a = round(sum(line["availability"] for line in per_line) / 4, 1)
    avg_p = round(sum(line["performance"] for line in per_line) / 4, 1)

    alarm_map = {r["severityclass"]: int(r["event_count"]) for r in alarm_losses}
    six_big = [
        {"category": "Storingen", "type": "availability", "events": alarm_map.get("Error", 0)},
        {"category": "Kleine stops", "type": "availability", "events": alarm_map.get("Warning", 0)},
        {"category": "Snelheidsverlies", "type": "performance", "minutes": avg_speed_loss},
        {"category": "Kwaliteitsverlies", "type": "quality", "minutes": 0},
    ]

    return {
        "date": target_date.isoformat(),
        "oee": avg_oee,
        "availability": avg_a,
        "performance": avg_p,
        "quality": 100.0,
        "per_line": per_line,
        "losses": {
            "planned_time": total_min,
            "downtime_loss": avg_downtime,
            "speed_loss": avg_speed_loss,
            "quality_loss": 0,
            "effective_time": total_min - avg_downtime - avg_speed_loss,
        },
        "six_big_losses": six_big,
    }
