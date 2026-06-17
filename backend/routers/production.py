"""
Productie KPI's afgeleid uit de DGS productiedata.

=== DATA-BRONNEN ===

capacity - cumulatieve productie-tellers (PLC-totaaltellers, lopen op gedurende de dag):
    - time (timestamp): meetmoment
    - infeed (bigint): cumulatief aantal door de camera gedetecteerde producten (instroom/"Erkannt")
    - placedrobot1 (bigint): cumulatief aantal door robot 1 geplaatst
    - placedrobot2 (bigint): cumulatief aantal door robot 2 geplaatst

    LET OP: dit zijn CUMULATIEVE tellers. Productie in een periode = verschil tussen
    het begin en eind van die periode, NIET de som van de rauwe waarden. Alle queries
    hieronder rekenen daarom met deltas tussen opeenvolgende minuten (zie _DAY_DELTAS).

    Afgeleide grootheden:
    - geplaatst = placedrobot1 + placedrobot2 (robot-output)
    - gemist    = infeed - geplaatst (instroom die de robots niet plaatsten = overflow)
    - rendement = geplaatst / infeed (kern-KPI: hoeveel van de aanvoer plaatsen de robots?)

plc_alarms - alarm-events (voor cross-table KPI's):
    - time (timestamp): tijdstip event
    - incomingstate (int): 1 = alarm geactiveerd, 0 = alarm opgelost
    - alarmmessage (text): beschrijving van het alarm

=== CONSTANTEN ===

Shifttijd: 05:00 - 23:00 (18 uur = 1080 minuten productietijd)
Buiten shift wordt niet geproduceerd, stilstand alleen binnen shift geteld.

=== KPI OVERZICHT ===

1. Totaal productie per dag per robot
   SUM(per-minuut-delta van placedrobotX) over de dag

2. Instroom / geplaatst / gemist / rendement
   infeed-delta vs (robot1+robot2)-delta; gemist = instroom - geplaatst

3. Stilstand-minuten per robot
   COUNT minuten binnen shift waarin de robot 0 plaatste (delta = 0)

4. Piekuur productie
   Het uur met de hoogste geplaatste productie (robot1 + robot2)

5. Robot-balans ratio
   MIN(robot-totaal) / MAX(robot-totaal), ideaal = 1.0

6. MTTR (Mean Time To Resolve)
   Gemiddelde tijd tussen alarm-activatie en -resolutie per alarm (plc_alarms)

7. Alarm-impact op throughput
   Geplaatste productie per minuut tijdens alarm vs zonder alarm

8. OEE (Overall Equipment Effectiveness) per robot
   OEE = Availability x Performance x Quality
   - Availability = (gemeten minuten - stilstand) / gemeten minuten
   - Performance = geplaatst / (uptime_minuten x ideaal_tempo)
     ideaal_tempo = 95e percentiel van de per-minuut-plaatsing tijdens uptime
   - Quality = 100% (geen uitvaldata beschikbaar uit PLC, placeholder)
"""

from datetime import date, datetime, time

from fastapi import APIRouter, Query

from backend.database import get_connection
from backend.timewindow import FACTORY_TZ, validate_date, validate_range

router = APIRouter(prefix="/api/production", tags=["production"])

SHIFT_START = time(5, 0)
SHIFT_END = time(23, 0)
SHIFT_MINUTES = 1080
TZ = "Europe/Amsterdam"

# Cumulatieve tellers -> productie per minuut is het VERSCHIL met de vorige minuut.
# MAX(...) per minuut vangt een hogere sample-rate op (laatste stand binnen de minuut);
# GREATEST(delta, 0) maakt een teller-reset of de NULL van de allereerste minuut 0
# i.p.v. negatief. Gevolg: de allereerste gemeten minuut van de dag telt als 0 (de
# overnacht-/baseline-toename gaat verloren, een verwaarloosbare ~1 minuut per dag).
# Levert een CTE `deltas(minute, infeed, r1, r2)` met productie PER MINUUT. $1 = datum.
_DAY_DELTAS = """
    WITH minute_max AS (
        SELECT date_trunc('minute', time) AS minute,
               MAX(infeed) AS infeed,
               MAX(placedrobot1) AS r1,
               MAX(placedrobot2) AS r2
        FROM capacity
        WHERE time >= $1::date AND time < $1::date + 1
        GROUP BY 1
    ),
    deltas AS (
        SELECT minute,
               GREATEST(infeed - LAG(infeed) OVER w, 0) AS infeed,
               GREATEST(r1 - LAG(r1) OVER w, 0) AS r1,
               GREATEST(r2 - LAG(r2) OVER w, 0) AS r2
        FROM minute_max
        WINDOW w AS (ORDER BY minute)
    )
"""


def expected_shift_minutes(target_date: date, now: datetime | None = None) -> int:
    """Hoeveel meetminuten horen er in het shift-venster van deze dag te zitten?

    Volle (verleden) dag: SHIFT_MINUTES. Voor vandaag telt alleen het deel van de
    shift dat al verstreken is, anders zou een lopende dag altijd een enorm
    "datagat" rapporteren. `now` is injecteerbaar voor tests.
    """
    now = now or datetime.now(FACTORY_TZ)
    if target_date < now.date():
        return SHIFT_MINUTES
    shift_start = datetime.combine(target_date, SHIFT_START, tzinfo=FACTORY_TZ)
    shift_end = datetime.combine(target_date, SHIFT_END, tzinfo=FACTORY_TZ)
    elapsed = (min(now, shift_end) - shift_start).total_seconds()
    return max(0, int(elapsed // 60))


def _flow_payload(row, label_key: str, label_value) -> dict:
    """Bouw een rij voor de productiegrafieken: instroom + 2 robots + geplaatst.

    `label_key` is "hour", "minute" of "date"; `label_value` de bijbehorende waarde.
    `placed` (robot1 + robot2) is de robot-output; `infeed` de instroom.
    """
    r1 = int(row["robot1"])
    r2 = int(row["robot2"])
    infeed = int(row["infeed"])
    return {
        label_key: label_value,
        "robot1": r1,
        "robot2": r2,
        "infeed": infeed,
        "placed": r1 + r2,
    }


@router.get("/summary")
async def get_production_summary(target_date: date = Query(default=None, alias="date")):
    """Dagelijkse productie-samenvatting: instroom, robot-output, gemist en kern-KPI's."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # --- KPI 1-3: dagtotalen, instroom en stilstand per robot ---
        # Productie = som van de per-minuut-deltas. Stilstand = minuten binnen shift
        # waarin de robot niets plaatste (delta = 0). recorded_minutes telt de minuten
        # met meetdata (voor het datagat-onderscheid).
        prod = await conn.fetchrow(
            _DAY_DELTAS
            + """
            SELECT
                COALESCE(SUM(r1), 0) AS robot1_total,
                COALESCE(SUM(r2), 0) AS robot2_total,
                COALESCE(SUM(infeed), 0) AS infeed_total,
                COUNT(*) FILTER (WHERE minute::time BETWEEN $2 AND $3)
                    AS recorded_shift_minutes,
                COUNT(*) FILTER (WHERE r1 = 0 AND minute::time BETWEEN $2 AND $3)
                    AS robot1_downtime,
                COUNT(*) FILTER (WHERE r2 = 0 AND minute::time BETWEEN $2 AND $3)
                    AS robot2_downtime
            FROM deltas
            """,
            target_date,
            SHIFT_START,
            SHIFT_END,
        )

        # --- KPI 4: Piekuur (hoogste geplaatste productie = robot1 + robot2) ---
        peak = await conn.fetchrow(
            _DAY_DELTAS
            + """
            SELECT
                date_trunc('hour', minute AT TIME ZONE $2) AS hour,
                SUM(r1 + r2) AS total
            FROM deltas
            GROUP BY date_trunc('hour', minute AT TIME ZONE $2)
            ORDER BY total DESC
            LIMIT 1
            """,
            target_date,
            TZ,
        )

        # --- KPI 5: MTTR (Mean Time To Resolve) ---
        # Per alarm (alarmmessage): LEAD kijkt naar het eerstvolgende event.
        # Paar state=1 -> state=0 = opgelost; orphaned resolves worden gefilterd.
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

    per_robot = [int(prod["robot1_total"]), int(prod["robot2_total"])]
    placed_total = sum(per_robot)
    infeed_total = int(prod["infeed_total"])
    # Gemist = instroom die niet geplaatst is. Clamp >= 0: meetruis/datagaten kunnen
    # geplaatst kortstondig boven instroom duwen, een negatief "gemist" is onzin.
    missed_total = max(0, infeed_total - placed_total)
    yield_pct = round(placed_total / infeed_total * 100, 1) if infeed_total > 0 else None
    dt_minutes = [int(prod["robot1_downtime"]), int(prod["robot2_downtime"])]

    # Datagat: shift-minuten ZONDER meetrij. Dat is "logger/pipeline weg", niet
    # per se "lijn stond stil"; daarom expliciet apart i.p.v. als stilstand geteld.
    recorded = int(prod["recorded_shift_minutes"] or 0)
    data_gap = max(0, expected_shift_minutes(target_date) - recorded)

    # --- KPI 5: Robot-balans ratio (MIN/MAX van de robot-totalen) ---
    max_robot = max(per_robot) if per_robot else 0
    robot_balance = round(min(per_robot) / max_robot, 2) if max_robot > 0 else None

    return {
        "date": target_date.isoformat(),
        "infeed_total": infeed_total,
        "placed_total": placed_total,
        "missed_total": missed_total,
        "yield_pct": yield_pct,
        "per_robot": per_robot,
        "downtime_minutes": dt_minutes,
        "shift_minutes": SHIFT_MINUTES,
        "data_gap_minutes": data_gap,
        "peak_hour": peak["hour"].strftime("%H:%M") if peak and peak["hour"] else None,
        "peak_hour_total": int(peak["total"]) if peak and peak["total"] else 0,
        "robot_balance": robot_balance,
        "mttr_avg_minutes": float(mttr["avg_minutes"]) if mttr and mttr["avg_minutes"] else None,
        "mttr_min_minutes": float(mttr["min_minutes"]) if mttr and mttr["min_minutes"] else None,
        "mttr_max_minutes": float(mttr["max_minutes"]) if mttr and mttr["max_minutes"] else None,
        "mttr_resolved": int(mttr["resolved"]) if mttr and mttr["resolved"] else 0,
        "mttr_unresolved": int(mttr["unresolved"]) if mttr and mttr["unresolved"] else 0,
    }


@router.get("/hourly")
async def get_hourly_production(target_date: date = Query(default=None, alias="date")):
    """Productie per robot per uur (instroom + robot-output), voor de uurgrafiek."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        rows = await conn.fetch(
            _DAY_DELTAS
            + """
            SELECT
                date_trunc('hour', minute AT TIME ZONE $2) AS hour,
                COALESCE(SUM(r1), 0) AS robot1,
                COALESCE(SUM(r2), 0) AS robot2,
                COALESCE(SUM(infeed), 0) AS infeed
            FROM deltas
            GROUP BY date_trunc('hour', minute AT TIME ZONE $2)
            ORDER BY hour
            """,
            target_date,
            TZ,
        )

    return [_flow_payload(r, "hour", r["hour"].strftime("%H:%M")) for r in rows]


@router.get("/minutely")
async def get_minutely_production(
    target_date: date = Query(default=None, alias="date"),
    hour: int = Query(ge=0, le=23),
):
    """Per-minuut productiedata voor een specifiek uur (inzoom voor robot-verdeling)."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # Deltas over de hele dag (LAG-continuiteit), pas in de outer-query op het uur filteren.
        rows = await conn.fetch(
            _DAY_DELTAS
            + """
            SELECT
                minute AT TIME ZONE $3 AS minute_local,
                r1 AS robot1,
                r2 AS robot2,
                infeed
            FROM deltas
            WHERE EXTRACT(HOUR FROM minute AT TIME ZONE $3) = $2
            ORDER BY minute
            """,
            target_date,
            hour,
            TZ,
        )

    return [_flow_payload(r, "minute", r["minute_local"].strftime("%H:%M")) for r in rows]


@router.get("/trends")
async def get_production_trends(
    date_from: date = Query(default=None, alias="from"),
    date_to: date = Query(default=None, alias="to"),
):
    """Dagelijkse productie-trend over een periode (per robot), voor trendgrafiek."""
    date_from, date_to = validate_range(date_from, date_to)

    async with get_connection() as conn:
        # Range-variant van de delta-CTE: deltas over de hele periode, daarna per dag
        # gesommeerd. De eerste minuut van de periode telt als 0 (zie _DAY_DELTAS).
        rows = await conn.fetch(
            """
            WITH minute_max AS (
                SELECT date_trunc('minute', time) AS minute,
                       time::date AS day,
                       MAX(infeed) AS infeed,
                       MAX(placedrobot1) AS r1,
                       MAX(placedrobot2) AS r2
                FROM capacity
                WHERE time >= $1::date AND time < $2::date + 1
                GROUP BY 1, 2
            ),
            deltas AS (
                SELECT day,
                       GREATEST(infeed - LAG(infeed) OVER w, 0) AS infeed,
                       GREATEST(r1 - LAG(r1) OVER w, 0) AS r1,
                       GREATEST(r2 - LAG(r2) OVER w, 0) AS r2
                FROM minute_max
                WINDOW w AS (ORDER BY minute)
            )
            SELECT day,
                   COALESCE(SUM(r1), 0) AS robot1,
                   COALESCE(SUM(r2), 0) AS robot2,
                   COALESCE(SUM(infeed), 0) AS infeed
            FROM deltas
            GROUP BY day
            ORDER BY day
            """,
            date_from,
            date_to,
        )

    return [_flow_payload(r, "date", r["day"].isoformat()) for r in rows]


@router.get("/alarm-impact")
async def get_alarm_impact(target_date: date = Query(default=None, alias="date")):
    """Cross-table analyse: alarm-impact op de geplaatste productie (robot-output)."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # --- KPI 7: Alarm-impact op throughput ---
        # Vergelijk geplaatste productie per minuut TIJDENS actief alarm vs ZONDER.
        # "Tijdens alarm" = het hele interval trigger -> eerstvolgende event (resolve
        # of her-trigger); onopgeloste alarmen tellen door tot einde dag.
        impact = await conn.fetchrow(
            """
            WITH events AS (
                SELECT
                    time,
                    incomingstate,
                    LEAD(time) OVER (PARTITION BY alarmmessage ORDER BY time) AS next_time
                FROM plc_alarms
                WHERE time >= $1::date AND time < $1::date + 1
            ),
            intervals AS (
                SELECT
                    date_trunc('minute', time) AS start_min,
                    date_trunc('minute',
                        COALESCE(next_time, $1::date + 1 - interval '1 minute')) AS end_min
                FROM events
                WHERE incomingstate = 1
            ),
            alarm_minutes AS (
                SELECT DISTINCT gs.minute
                FROM intervals
                CROSS JOIN LATERAL
                    generate_series(start_min, end_min, '1 minute') AS gs(minute)
            ),
            minute_max AS (
                SELECT date_trunc('minute', time) AS minute,
                       MAX(placedrobot1) AS r1,
                       MAX(placedrobot2) AS r2
                FROM capacity
                WHERE time >= $1::date AND time < $1::date + 1
                GROUP BY 1
            ),
            deltas AS (
                SELECT minute,
                       GREATEST((r1 + r2) - LAG(r1 + r2) OVER (ORDER BY minute), 0) AS placed
                FROM minute_max
            )
            SELECT
                ROUND(AVG(CASE WHEN am.minute IS NOT NULL THEN d.placed END)::numeric, 1)
                    AS avg_during_alarm,
                ROUND(AVG(CASE WHEN am.minute IS NULL THEN d.placed END)::numeric, 1)
                    AS avg_without_alarm,
                COUNT(*) FILTER (WHERE am.minute IS NOT NULL) AS alarm_minutes,
                COUNT(*) FILTER (WHERE am.minute IS NULL) AS normal_minutes
            FROM deltas d
            LEFT JOIN alarm_minutes am ON d.minute = am.minute
            """,
            target_date,
        )

        # --- Alarm-productie correlatie per uur (geplaatste productie + alarmcount) ---
        correlation = await conn.fetch(
            """
            WITH minute_max AS (
                SELECT date_trunc('minute', time) AS minute,
                       MAX(placedrobot1) AS r1,
                       MAX(placedrobot2) AS r2
                FROM capacity
                WHERE time >= $1::date AND time < $1::date + 1
                GROUP BY 1
            ),
            deltas AS (
                SELECT minute,
                       GREATEST((r1 + r2) - LAG(r1 + r2) OVER (ORDER BY minute), 0) AS placed
                FROM minute_max
            )
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
                SELECT date_trunc('hour', minute) AS hour, SUM(placed) AS total
                FROM deltas
                GROUP BY date_trunc('hour', minute)
            ) p ON h.hour = p.hour
            LEFT JOIN (
                SELECT date_trunc('hour', time) AS hour, COUNT(*) AS alarm_count
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

    # Productieverlies-percentage: (1 - tijdens/zonder) * 100. Positief = verlies.
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
    """OEE (Overall Equipment Effectiveness) per robot en totaal."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        # Per-minuut-deltas over de dag; binnen-shift gefilterd in de aggregatie.
        # Voor elke robot: gemeten minuten, stilstand (delta=0), totaal en ideaal-tempo
        # (p95 van de per-minuut-plaatsing tijdens uptime).
        stats = await conn.fetchrow(
            _DAY_DELTAS
            + """
            SELECT
                COUNT(*) FILTER (WHERE minute::time BETWEEN $2 AND $3) AS total_minutes,
                COUNT(*) FILTER (WHERE r1 = 0 AND minute::time BETWEEN $2 AND $3) AS dt_1,
                COUNT(*) FILTER (WHERE r2 = 0 AND minute::time BETWEEN $2 AND $3) AS dt_2,
                COALESCE(SUM(r1) FILTER (WHERE minute::time BETWEEN $2 AND $3), 0) AS total_1,
                COALESCE(SUM(r2) FILTER (WHERE minute::time BETWEEN $2 AND $3), 0) AS total_2,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY r1)
                    FILTER (WHERE r1 > 0 AND minute::time BETWEEN $2 AND $3) AS ideal_1,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY r2)
                    FILTER (WHERE r2 > 0 AND minute::time BETWEEN $2 AND $3) AS ideal_2
            FROM deltas
            """,
            target_date,
            SHIFT_START,
            SHIFT_END,
        )

        alarm_losses = await conn.fetch(
            """
            SELECT severityclass, COUNT(*) AS event_count
            FROM plc_alarms
            WHERE time >= $1::date AND time < $1::date + 1 AND incomingstate = 1
            GROUP BY severityclass
            """,
            target_date,
        )

    total_min = int(stats["total_minutes"]) if stats["total_minutes"] else 0
    data_gap = max(0, expected_shift_minutes(target_date) - total_min)
    if total_min == 0:
        return {
            "date": target_date.isoformat(),
            "oee": None,
            "availability": None,
            "performance": None,
            "quality": 100.0,
            "per_robot": [],
            "losses": None,
            "six_big_losses": [],
            "data_gap_minutes": data_gap,
        }

    per_robot = []
    total_downtime = 0
    total_speed_loss = 0
    oee_values = []

    for i in (1, 2):
        dt = int(stats[f"dt_{i}"])
        total = int(stats[f"total_{i}"])
        ideal = float(stats[f"ideal_{i}"]) if stats[f"ideal_{i}"] else 0
        uptime = total_min - dt

        availability = uptime / total_min if total_min > 0 else 0
        if uptime > 0 and ideal > 0:
            performance = min(total / (uptime * ideal), 1.0)
        else:
            performance = 0
        quality = 1.0
        oee = availability * performance * quality

        speed_loss_min = round((1 - performance) * uptime) if uptime > 0 else 0
        total_downtime += dt
        total_speed_loss += speed_loss_min
        oee_values.append(oee)

        per_robot.append({
            "robot": i,
            "name": f"Robot {i}",
            "oee": round(oee * 100, 1),
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
            "downtime_minutes": dt,
            "speed_loss_minutes": speed_loss_min,
        })

    n = len(per_robot)
    avg_downtime = round(total_downtime / n)
    avg_speed_loss = round(total_speed_loss / n)
    avg_oee = round(sum(oee_values) / n * 100, 1)
    avg_a = round(sum(r["availability"] for r in per_robot) / n, 1)
    avg_p = round(sum(r["performance"] for r in per_robot) / n, 1)

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
        "per_robot": per_robot,
        "losses": {
            "planned_time": total_min,
            "downtime_loss": avg_downtime,
            "speed_loss": avg_speed_loss,
            "quality_loss": 0,
            "effective_time": total_min - avg_downtime - avg_speed_loss,
        },
        "six_big_losses": six_big,
        "data_gap_minutes": data_gap,
    }
