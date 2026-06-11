"""Synthetische motor-stroomdata voor de Maintenance-demo.

=== DIT IS DE NAAD ===

Alles wat met de HERKOMST van de motor-stroomdata te maken heeft, zit in dit ene bestand.
Zodra de echte PLC-tabel + kolomnamen bekend zijn, vervang je get_motors() en
get_motor_history() door een query op die tabel (via de bestaande asyncpg-pool in
backend.database). De detectie (wear.py), de endpoints en de hele frontend blijven dan
ongewijzigd: zij praten alleen met de functies hieronder, niet met de databron.

De synthetische set heeft 12 motoren. De meeste zijn stabiel: elke productiedag start de
stroom rond 0,05 A en piekt tot ~3,0 A. Twee motoren vertonen bewust een trage opwaartse
drift over de periode (hun dagpiek kruipt van ~3,0 A naar ~3,5 A), precies het
slijtage-patroon dat we willen detecteren.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

# (id, naam, lijn, drift_per_dag_in_A). drift 0 = stabiel.
_MOTOR_CONFIG = [
    (1, "Motor 1", 1, 0.0),
    (2, "Motor 2", 1, 0.0),
    (3, "Motor 3", 1, 0.0),
    (4, "Motor 4", 2, 0.0),
    (5, "Motor 5", 2, 0.0),
    (6, "Motor 6", 2, 0.0),
    (7, "Motor 7", 3, 0.0),
    (8, "Motor 8", 3, 0.009),    # trage slijtage: ~0,5 A over ~8 weken -> alarm
    (9, "Motor 9", 3, 0.0),
    (10, "Motor 10", 4, 0.0),
    (11, "Motor 11", 4, 0.005),  # mildere drift -> let op
    (12, "Motor 12", 4, 0.0),
]

BASE_PEAK_A = 3.0
START_A = 0.05


def get_motors() -> list[dict]:
    """Metadata van alle motoren (geen metingen)."""
    return [{"id": m[0], "name": m[1], "line": m[2]} for m in _MOTOR_CONFIG]


def _config(motor_id: int):
    return next((m for m in _MOTOR_CONFIG if m[0] == motor_id), None)


def get_motor_history(motor_id: int, days: int = 60) -> list[dict]:
    """Dagelijkse start- en piekstroom voor één motor over de laatste `days` dagen
    (eindigend gisteren). Weekenden worden overgeslagen (geen productie). Deterministisch
    per motor (seeded), zodat de demo stabiel en reproduceerbaar is."""
    cfg = _config(motor_id)
    if cfg is None:
        return []
    drift = cfg[3]
    rng = random.Random(1000 + motor_id)
    end = date.today() - timedelta(days=1)
    start_day = end - timedelta(days=days - 1)
    rows = []
    for i in range(days):
        d = start_day + timedelta(days=i)
        if d.weekday() >= 5:  # weekend: motor staat stil
            continue
        start_a = round(START_A + rng.uniform(-0.01, 0.02), 3)
        peak = BASE_PEAK_A + drift * i + rng.uniform(-0.12, 0.12)
        rows.append({"date": d.isoformat(), "start_a": start_a, "peak_a": round(peak, 3)})
    return rows


def get_all_histories(days: int = 60) -> dict[int, list[dict]]:
    return {m[0]: get_motor_history(m[0], days) for m in _MOTOR_CONFIG}
