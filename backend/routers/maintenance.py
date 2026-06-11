"""Maintenance-endpoints: motor-stroom + slijtage-signalen (demo op synthetische data).

Read-only. De databron zit achter de naad in backend.maintenance.data; deze router
weet niet of de cijfers synthetisch of echt zijn.
"""
from fastapi import APIRouter, HTTPException, Query

from backend.maintenance import data
from backend.maintenance.wear import analyze_motor, detect_wear

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

DEFAULT_DAYS = 60


@router.get("/motors")
async def list_motors(days: int = Query(default=DEFAULT_DAYS, ge=14, le=180)):
    """Alle motoren met hun huidige status (ok / warn / alarm)."""
    motors = data.get_motors()
    histories = data.get_all_histories(days)
    out = []
    for m in motors:
        a = analyze_motor(histories.get(m["id"], []))
        out.append({
            **m,
            "baseline_a": a["baseline_a"] if a else None,
            "current_a": a["current_a"] if a else None,
            "increase_pct": a["increase_pct"] if a else None,
            "status": a["status"] if a else "unknown",
        })
    return {"days": days, "motors": out}


@router.get("/motors/{motor_id}/history")
async def motor_history(motor_id: int, days: int = Query(default=DEFAULT_DAYS, ge=14, le=180)):
    """Dagelijkse start- en piekstroom van één motor + de analyse, voor de trendgrafiek."""
    # Onbekende motor (404) is een andere fout dan bekend-maar-geen-metingen (422);
    # één gedeelde melding zou bij echte PLC-data misleidend debuggen.
    if not data.motor_exists(motor_id):
        raise HTTPException(404, f"Onbekende motor {motor_id}")
    history = data.get_motor_history(motor_id, days)
    if not history:
        raise HTTPException(422, f"Geen productiedagen voor motor {motor_id} in de gevraagde periode")
    return {
        "motor_id": motor_id,
        "days": days,
        "analysis": analyze_motor(history),
        "history": history,
    }


@router.get("/signals")
async def signals(days: int = Query(default=DEFAULT_DAYS, ge=14, le=180)):
    """De onderhoudssignalen: motoren waarvan de stroom oploopt."""
    motors = data.get_motors()
    histories = data.get_all_histories(days)
    return {"days": days, "signals": detect_wear(motors, histories)}
