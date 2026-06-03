from datetime import date

from fastapi import APIRouter, Query

from backend.database import get_connection
from backend.timewindow import validate_date, validate_range

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


@router.get("/open")
async def get_open_alarms(target_date: date = Query(default=None, alias="date")):
    """Openstaande alarmen: per alarmmessage het laatste event pakken,
    als dat incomingstate=1 is, is het alarm nog niet verholpen."""
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT alarmmessage, severityclass, time AS last_seen
            FROM (
                SELECT DISTINCT ON (alarmmessage)
                    alarmmessage, severityclass, incomingstate, time
                FROM plc_alarms
                WHERE time >= $1::date AND time < $1::date + 1
                ORDER BY alarmmessage, time DESC
            ) latest
            WHERE incomingstate = 1
            ORDER BY last_seen DESC
            """,
            target_date,
        )

    return [
        {
            "alarmmessage": r["alarmmessage"],
            "severityclass": r["severityclass"],
            "last_seen": r["last_seen"].isoformat(),
        }
        for r in rows
    ]


@router.get("/stats")
async def get_stats(target_date: date = Query(default=None, alias="date")):
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE incomingstate = 0) AS resolved,
                COUNT(*) FILTER (WHERE incomingstate = 1) AS triggered,
                MIN(time) AS first_alarm,
                MAX(time) AS last_alarm
            FROM plc_alarms
            WHERE time >= $1::date AND time < $1::date + 1
            """,
            target_date,
        )

    return {
        "date": target_date.isoformat(),
        "resolved": row["resolved"] or 0,
        "triggered": row["triggered"] or 0,
        "first_alarm": row["first_alarm"].isoformat() if row["first_alarm"] else None,
        "last_alarm": row["last_alarm"].isoformat() if row["last_alarm"] else None,
    }


@router.get("/top")
async def get_top_alarms(
    target_date: date = Query(default=None, alias="date"),
    limit: int = Query(default=10, ge=1, le=50),
):
    target_date = validate_date(target_date)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                alarmmessage,
                COUNT(*) FILTER (WHERE incomingstate = 1) AS trigger_count,
                COUNT(*) FILTER (WHERE incomingstate = 0) AS resolve_count,
                severityclass
            FROM plc_alarms
            WHERE time >= $1::date AND time < $1::date + 1
            GROUP BY alarmmessage, severityclass
            ORDER BY trigger_count DESC, alarmmessage
            LIMIT $2
            """,
            target_date,
            limit,
        )

    return [
        {
            "alarmmessage": r["alarmmessage"],
            "trigger_count": r["trigger_count"],
            "resolve_count": r["resolve_count"],
            "severityclass": r["severityclass"],
        }
        for r in rows
    ]


@router.get("/list")
async def get_alarm_list(
    target_date: date = Query(default=None, alias="date"),
    severity: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=10, le=200),
):
    target_date = validate_date(target_date)

    conditions = ["time >= $1::date AND time < $1::date + 1"]
    params: list = [target_date]
    idx = 2

    if severity:
        conditions.append(f"severityclass = ${idx}")
        params.append(severity)
        idx += 1

    if search:
        conditions.append(f"alarmmessage ILIKE ${idx}")
        params.append(f"%{search.strip()}%")
        idx += 1

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    async with get_connection() as conn:
        count = await conn.fetchval(
            f"SELECT COUNT(*) FROM plc_alarms WHERE {where}", *params
        )

        rows = await conn.fetch(
            f"""
            SELECT time, alarmmessage, severityclass, incomingstate
            FROM plc_alarms
            WHERE {where}
            ORDER BY time DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            per_page,
            offset,
        )

    total_pages = max(1, -(-count // per_page))
    clamped_page = min(page, total_pages)

    return {
        "total": count,
        "page": clamped_page,
        "per_page": per_page,
        "pages": total_pages,
        "items": [
            {
                "time": r["time"].isoformat(),
                "alarmmessage": r["alarmmessage"],
                "severityclass": r["severityclass"],
                "state": "resolved" if r["incomingstate"] == 0 else "triggered",
            }
            for r in rows
        ],
    }


@router.get("/trends")
async def get_trends(
    date_from: date = Query(default=None, alias="from"),
    date_to: date = Query(default=None, alias="to"),
):
    date_from, date_to = validate_range(date_from, date_to)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                time::date AS day,
                COUNT(*) FILTER (WHERE incomingstate = 1) AS triggered,
                COUNT(*) FILTER (WHERE incomingstate = 0) AS resolved
            FROM plc_alarms
            WHERE time >= $1::date AND time < $2::date + 1
            GROUP BY day
            ORDER BY day
            """,
            date_from,
            date_to,
        )

    return [
        {
            "date": r["day"].isoformat(),
            "triggered": r["triggered"],
            "resolved": r["resolved"],
        }
        for r in rows
    ]
