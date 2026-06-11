"""
Genereer realistische dummy data voor DGS Optimax als SQL naar stdout.

Vult 4 tabellen (CREATE TABLE IF NOT EXISTS + INSERTs):
  - plc_alarms (+ plc_alarms_mp1): alarmen met trigger/resolve paren en MTTR
  - capacity_perminutev2: productietellers per minuut (shift 05:00-23:00)
  - palletstatus: palletstation-statuscodes per ~1 min

Gebruik (alleen stdlib, geen dependencies):
  python scripts/generate_dummy_data.py --days 14 > seed.sql
  docker exec -i <db-container> psql -U <user> -d db_dgs_01 < seed.sql

Optioneel:
  --days 14          Aantal dagen (default: 7), weekenden worden overgeslagen
  --clear            DELETE bestaande data voor de gegenereerde periode

Voor de gepartitioneerde prod-spiegel: scripts/seed_partitioned.py (hergebruikt
de generator-functies hieronder). Voor de Edge-demo-image: scripts/build-ixrouter-db.sh.
"""

import argparse
import random
import sys
from datetime import datetime, timedelta

SHIFT_START_HOUR = 5
SHIFT_END_HOUR = 23

# Palletstatus-codes zoals de backend ze verwacht (zie pallets.py):
# 100 = geen pallet aanwezig, 200 = pallet leeg, 300 = pallet klaar.
PALLET_STATUSES = [100, 200, 300]

ALARM_MESSAGES = [
    ("Robot arm positie fout", "Error"),
    ("Transportband stilstand", "Error"),
    ("Noodstop geactiveerd", "Error"),
    ("Metaaldetector alarm", "Error"),
    ("Snijmachine overbelast", "Error"),
    ("Vacuumsysteem druk laag", "Error"),
    ("Pneumatiek druk te laag", "Error"),
    ("Etiketteersysteem fout", "Error"),
    ("Koeling temperatuur boven grens", "Warning"),
    ("Messenstation slijtage", "Warning"),
    ("Weegschaal kalibratie nodig", "Warning"),
    ("Productiesensor verschuild", "Warning"),
    ("Deur zone 3 open", "Warning"),
    ("Aanvoerband snelheid afwijking", "Warning"),
    ("Smeersysteem niveau laag", "Warning"),
    ("Reinigingscyclus gestart", "Info"),
    ("Pallet vol, transport nodig", "Info"),
    ("Shift-wissel gedetecteerd", "Info"),
    ("Onderhoudstimer bereikt", "Info"),
]


def generate_alarms_for_day(day: datetime.date) -> list[tuple]:
    """Genereer alarm-events voor 1 dag met realistische trigger/resolve paren."""
    rows = []
    num_alarms = random.randint(25, 80)

    for _ in range(num_alarms):
        msg, severity = random.choice(ALARM_MESSAGES)
        hour = random.choices(
            range(SHIFT_START_HOUR, SHIFT_END_HOUR),
            weights=[
                3, 5, 7, 8, 8, 6, 5, 4, 5, 7, 8, 7, 6, 5, 4, 3, 2, 1
            ],
        )[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        ms = random.randint(0, 999)

        trigger_time = datetime(
            day.year, day.month, day.day,
            hour, minute, second, ms * 1000,
        )

        rows.append((trigger_time, msg, severity, 1))

        if random.random() < 0.85:
            if severity == "Error":
                resolve_minutes = random.uniform(2, 45)
            elif severity == "Warning":
                resolve_minutes = random.uniform(1, 15)
            else:
                resolve_minutes = random.uniform(0.5, 5)

            resolve_time = trigger_time + timedelta(minutes=resolve_minutes)
            if resolve_time.hour < SHIFT_END_HOUR:
                rows.append((resolve_time, msg, severity, 0))

    rows.sort(key=lambda r: r[0])
    return rows


def generate_capacity_for_day(day: datetime.date) -> list[tuple]:
    """Genereer productietellers per minuut voor 1 dag (shift 05:00-23:00)."""
    rows = []
    # Lijn 1 en 4 = robot-output (hoog), lijn 2 en 3 = overflow/rest (laag),
    # zodat het overflow-aandeel rond ~15% ligt (zichtbare groen/amber/rood-spreiding).
    base_rates = [26, 5, 4, 20]

    has_downtime = [random.random() < 0.15 for _ in range(4)]
    downtime_start = [random.randint(SHIFT_START_HOUR + 1, SHIFT_END_HOUR - 3) for _ in range(4)]
    downtime_duration = [random.randint(15, 90) for _ in range(4)]

    for hour in range(SHIFT_START_HOUR, SHIFT_END_HOUR):
        hour_factor = 1.0
        if hour < 7:
            hour_factor = 0.6
        elif hour < 9:
            hour_factor = 1.1
        elif hour == 12:
            hour_factor = 0.3
        elif 9 <= hour <= 15:
            hour_factor = 1.0
        elif hour > 20:
            hour_factor = 0.7

        for minute in range(60):
            t = datetime(day.year, day.month, day.day, hour, minute,
                         random.randint(0, 59), random.randint(0, 999) * 1000)

            counters = []
            for line in range(4):
                elapsed_min = (hour - SHIFT_START_HOUR) * 60 + minute

                if has_downtime[line]:
                    dt_start_min = (downtime_start[line] - SHIFT_START_HOUR) * 60
                    if dt_start_min <= elapsed_min < dt_start_min + downtime_duration[line]:
                        counters.append(0)
                        continue

                base = base_rates[line] * hour_factor
                noise = random.gauss(0, base * 0.15)
                val = max(0, int(base + noise))
                counters.append(val)

            rows.append((t, *counters))

    return rows


def generate_pallets_for_day(day: datetime.date) -> list[tuple]:
    """Genereer palletstatus-metingen per ~1 minuut voor 1 dag.

    Statuscodes moeten matchen met wat de backend-queries verwachten
    (pallets.py filtert op 100/200/300): 100 = geen pallet, 200 = leeg,
    300 = klaar. Eerder werd hier 0/1/2 geschreven, waardoor de
    Pallets-pagina overal 0% toonde.
    """
    rows = []
    current_status = [random.choice(PALLET_STATUSES) for _ in range(4)]

    for hour in range(SHIFT_START_HOUR, SHIFT_END_HOUR):
        for minute in range(60):
            t = datetime(day.year, day.month, day.day, hour, minute,
                         random.randint(0, 59), random.randint(0, 999) * 1000)

            for i in range(4):
                if random.random() < 0.08:
                    current_status[i] = random.choice(PALLET_STATUSES)

            rows.append((t, *current_status[:]))

    return rows


def escape_sql(val) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
    if isinstance(val, str):
        return "'" + val.replace("'", "''") + "'"
    return str(val)


def generate_sql(days: int, clear: bool) -> str:
    lines = []
    lines.append("-- DGS dummy data, gegenereerd door generate_dummy_data.py")
    lines.append("-- Tabellen: plc_alarms, capacity_perminutev2, palletstatus")
    lines.append("")

    lines.append("""
CREATE TABLE IF NOT EXISTS plc_alarms (
    time        TIMESTAMP NOT NULL,
    alarmmessage TEXT,
    severityclass VARCHAR(20),
    incomingstate INTEGER
);

CREATE TABLE IF NOT EXISTS plc_alarms_mp1 (
    time          TIMESTAMP NOT NULL,
    alarmid       SERIAL,
    alarmmessage  VARCHAR(200),
    severityclass VARCHAR(20),
    incomingstate INTEGER,
    eventid       VARCHAR(150)
);

CREATE TABLE IF NOT EXISTS capacity_perminutev2 (
    time     TIMESTAMP NOT NULL,
    counter0 INTEGER,
    counter1 INTEGER,
    counter2 INTEGER,
    counter3 INTEGER
);

CREATE TABLE IF NOT EXISTS palletstatus (
    time       TIMESTAMP NOT NULL,
    pallet6000 INTEGER,
    pallet6005 INTEGER,
    pallet6010 INTEGER,
    pallet6015 INTEGER
);
""")

    today = datetime.now().date()
    start_date = today - timedelta(days=days)
    end_date = today - timedelta(days=1)

    if clear:
        lines.append(f"DELETE FROM plc_alarms WHERE time::date BETWEEN '{start_date}' AND '{end_date}';")
        lines.append(f"DELETE FROM plc_alarms_mp1 WHERE time::date BETWEEN '{start_date}' AND '{end_date}';")
        lines.append(f"DELETE FROM capacity_perminutev2 WHERE time::date BETWEEN '{start_date}' AND '{end_date}';")
        lines.append(f"DELETE FROM palletstatus WHERE time::date BETWEEN '{start_date}' AND '{end_date}';")
        lines.append("")

    for day_offset in range(days):
        day = start_date + timedelta(days=day_offset)
        weekday = day.weekday()
        if weekday >= 5:
            continue

        print(f"  Genereer {day} ({['ma','di','wo','do','vr','za','zo'][weekday]})...",
              file=sys.stderr)

        alarms = generate_alarms_for_day(day)
        lines.append(f"-- plc_alarms {day} ({len(alarms)} events)")
        for i in range(0, len(alarms), 50):
            batch = alarms[i:i+50]
            vals = ",\n".join(
                f"  ({escape_sql(t)}, {escape_sql(m)}, {escape_sql(s)}, {st})"
                for t, m, s, st in batch
            )
            lines.append(f"INSERT INTO plc_alarms (time, alarmmessage, severityclass, incomingstate) VALUES\n{vals};")

        event_counter = day_offset * 10000
        lines.append(f"-- plc_alarms_mp1 {day}")
        for i in range(0, len(alarms), 50):
            batch = alarms[i:i+50]
            vals = ",\n".join(
                f"  ({escape_sql(t)}, {escape_sql(m)}, {escape_sql(s)}, {st}, {escape_sql(f'{event_counter + j:06x}')})"
                for j, (t, m, s, st) in enumerate(batch, start=i)
            )
            lines.append(f"INSERT INTO plc_alarms_mp1 (time, alarmmessage, severityclass, incomingstate, eventid) VALUES\n{vals};")

        capacity = generate_capacity_for_day(day)
        lines.append(f"-- capacity_perminutev2 {day} ({len(capacity)} rijen)")
        for i in range(0, len(capacity), 100):
            batch = capacity[i:i+100]
            vals = ",\n".join(
                f"  ({escape_sql(t)}, {c0}, {c1}, {c2}, {c3})"
                for t, c0, c1, c2, c3 in batch
            )
            lines.append(f"INSERT INTO capacity_perminutev2 (time, counter0, counter1, counter2, counter3) VALUES\n{vals};")

        pallets = generate_pallets_for_day(day)
        lines.append(f"-- palletstatus {day} ({len(pallets)} rijen)")
        for i in range(0, len(pallets), 100):
            batch = pallets[i:i+100]
            vals = ",\n".join(
                f"  ({escape_sql(t)}, {p0}, {p1}, {p2}, {p3})"
                for t, p0, p1, p2, p3 in batch
            )
            lines.append(f"INSERT INTO palletstatus (time, pallet6000, pallet6005, pallet6010, pallet6015) VALUES\n{vals};")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="DGS dummy data generator (SQL naar stdout)")
    parser.add_argument("--days", type=int, default=7, help="Aantal dagen (default: 7)")
    parser.add_argument("--clear", action="store_true", help="Verwijder bestaande data voor de periode")
    args = parser.parse_args()

    random.seed(42)
    print(generate_sql(args.days, args.clear))


if __name__ == "__main__":
    main()
