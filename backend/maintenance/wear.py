"""Slijtage-detectie op dagelijkse motor-piekstroom.

Transparante regel, geen ML (juist goed uit te leggen aan de Technische Dienst):
vergelijk het gemiddelde van de laatste `WINDOW` meetdagen met een basislijn (de eerste
`WINDOW` meetdagen). Loopt dat boven beide drempels (relatief EN absoluut), dan is er
sprake van slijtage-drift. De absolute ondergrens voorkomt valse alarmen bij kleine waarden.
"""
from __future__ import annotations

WINDOW = 7            # dagen voor basislijn en recent gemiddelde
MIN_DAYS = 14         # minder data dan dit -> geen uitspraak
WARN_PCT = 8.0        # >= dit % stijging -> let op
ALARM_PCT = 15.0      # >= dit % stijging -> alarm
MIN_ABS_A = 0.25      # absolute ondergrens (A), dempt ruis-alarmen


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def analyze_motor(history: list[dict]) -> dict | None:
    """Basislijn, huidige waarde, stijging en status voor één motor.
    Geeft None als er te weinig data is voor een uitspraak."""
    peaks = [d["peak_a"] for d in history]
    if len(peaks) < MIN_DAYS:
        return None

    baseline = _mean(peaks[:WINDOW])
    recent = _mean(peaks[-WINDOW:])
    increase_abs = recent - baseline
    increase_pct = (increase_abs / baseline * 100) if baseline > 0 else 0.0

    drift = increase_pct >= WARN_PCT and increase_abs >= MIN_ABS_A
    if not drift:
        status = "ok"
    elif increase_pct >= ALARM_PCT:
        status = "alarm"
    else:
        status = "warn"

    # Sinds wanneer loopt het op: tel terug vanaf vandaag hoeveel dagen de piek
    # boven de (basislijn + halve drempel) bleef.
    threshold = baseline + max(MIN_ABS_A, baseline * WARN_PCT / 100) / 2
    since_days = 0
    for d in reversed(history):
        if d["peak_a"] >= threshold:
            since_days += 1
        else:
            break

    return {
        "baseline_a": round(baseline, 3),
        "current_a": round(peaks[-1], 3),
        "recent_a": round(recent, 3),
        "increase_pct": round(increase_pct, 1),
        "since_days": since_days,
        "status": status,
    }


def detect_wear(motors: list[dict], histories: dict[int, list[dict]]) -> list[dict]:
    """Signalen voor motoren met status 'warn' of 'alarm', alarm bovenaan."""
    by_id = {m["id"]: m for m in motors}
    signals = []
    for motor_id, history in histories.items():
        a = analyze_motor(history)
        if a is None or a["status"] == "ok":
            continue
        meta = by_id.get(motor_id, {})
        name = meta.get("name", f"Motor {motor_id}")
        signals.append({
            "motor_id": motor_id,
            "motor_name": name,
            "line": meta.get("line"),
            "baseline_a": a["baseline_a"],
            "current_a": a["current_a"],
            "increase_pct": a["increase_pct"],
            "since_days": a["since_days"],
            "status": a["status"],
            "advice": (
                f"Controleer {name}: piekstroom loopt op "
                f"({a['baseline_a']} A -> {a['current_a']} A, +{a['increase_pct']}%)."
            ),
        })
    signals.sort(key=lambda s: (s["status"] != "alarm", -s["increase_pct"]))
    return signals
