"""
Seed dummy-data in een GEPARTITIONEERDE DGS-database (prod-spiegel).

De productie-database (en de lokale prod-spiegel `dgs-db-local`, poort 5434) gebruikt
RANGE-partities per dag op de kolom `time`, bijv. `capacity_20260526`.
Het gewone `generate_dummy_data.py` maakt vlakke tabellen en past daar niet op.

Dit script:
  - hergebruikt de generator-functies uit generate_dummy_data.py
  - maakt per dag de ontbrekende dagpartitie aan (CREATE TABLE ... PARTITION OF ...)
  - schrijft INSERTs op de partitioned parent (Postgres routeert naar de juiste partitie)

Het werkt met de tabellen die de prod-spiegel kent: plc_alarms, capacity (cumulatieve
infeed/placedrobot1/placedrobot2) en palletstatus. plc_alarms krijgt de kolommen die de
backend gebruikt; eventid wordt expliciet gevuld (NOT NULL op de prod-spiegel).

Gebruik (SQL naar stdout, daarna in de container pipen):
  python scripts/seed_partitioned.py --days 14 --clear > /tmp/seed.sql
  docker exec -i dgs-db-local psql -U dgs -d db_dgs_01 < /tmp/seed.sql
"""

import argparse
import sys
from datetime import datetime, timedelta

from generate_dummy_data import (
    escape_sql,
    generate_alarms_for_day,
    generate_capacity_for_day,
    generate_pallets_for_day,
)

# Partitioned parent -> kolommen die we vullen.
# plc_alarms: alarmid heeft een sequence-default (overslaan), maar eventid is
# NOT NULL zonder default, dus die geven we expliciet mee.
PARTITIONED_TABLES = {
    "plc_alarms": ("time", "alarmmessage", "severityclass", "incomingstate", "eventid"),
    "capacity": ("time", "infeed", "placedrobot1", "placedrobot2"),
    "palletstatus": ("time", "pallet6000", "pallet6005", "pallet6010", "pallet6015"),
}


def _partition_ddl(table: str, day: datetime.date) -> str:
    """CREATE TABLE IF NOT EXISTS voor de dagpartitie van `table` op `day`."""
    suffix = day.strftime("%Y%m%d")
    start = f"{day} 00:00:00"
    end = f"{day + timedelta(days=1)} 00:00:00"
    return (
        f"CREATE TABLE IF NOT EXISTS {table}_{suffix} "
        f"PARTITION OF {table} "
        f"FOR VALUES FROM ('{start}') TO ('{end}');"
    )


def _insert_batches(table: str, columns: tuple, rows: list[tuple], batch: int = 100) -> list[str]:
    """Batched INSERT-statements voor `rows` in `table`. Eerste kolom telt mee per rij."""
    col_list = ", ".join(columns)
    out = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        values = ",\n".join(
            "  (" + ", ".join(escape_sql(v) for v in row) + ")" for row in chunk
        )
        out.append(f"INSERT INTO {table} ({col_list}) VALUES\n{values};")
    return out


def generate_sql(days: int, end_date: datetime.date, clear: bool) -> str:
    start_date = end_date - timedelta(days=days - 1)
    lines = [
        "-- DGS partitie-bewuste dummy-data (prod-spiegel)",
        f"-- Periode: {start_date} t/m {end_date} (alleen werkdagen)",
        "",
    ]

    # Index op de partitiekolom (op de parent -> propageert naar alle partities,
    # ook toekomstige). Cruciaal voor performance: zonder index + sargable filter
    # scant elke dag-query alle partities. Idempotent.
    for table in PARTITIONED_TABLES:
        lines.append(f"CREATE INDEX IF NOT EXISTS idx_{table}_time ON {table} (time);")
    lines.append("")

    if clear:
        # Bereik-delete is sargable en raakt alleen de relevante partities.
        range_end = f"{end_date + timedelta(days=1)} 00:00:00"
        for table in PARTITIONED_TABLES:
            lines.append(
                f"DELETE FROM {table} WHERE time >= '{start_date} 00:00:00' "
                f"AND time < '{range_end}';"
            )
        lines.append("")

    for offset in range(days):
        day = start_date + timedelta(days=offset)
        if day.weekday() >= 5:  # weekend overslaan, net als de flat generator
            continue

        wd = ["ma", "di", "wo", "do", "vr", "za", "zo"][day.weekday()]
        print(f"  Genereer {day} ({wd})...", file=sys.stderr)
        lines.append(f"-- ===== {day} ({wd}) =====")

        # Dagpartities aanmaken voordat we inserten.
        for table in PARTITIONED_TABLES:
            lines.append(_partition_ddl(table, day))

        alarms = generate_alarms_for_day(day)
        # Unieke hex eventid per alarm (eventid is NOT NULL op de prod-spiegel).
        event_base = offset * 100000
        alarm_rows = [
            (t, m, s, st, f"{event_base + j:08x}")
            for j, (t, m, s, st) in enumerate(alarms)
        ]
        lines += _insert_batches("plc_alarms", PARTITIONED_TABLES["plc_alarms"], alarm_rows, batch=50)

        capacity = generate_capacity_for_day(day)
        lines += _insert_batches("capacity", PARTITIONED_TABLES["capacity"], capacity)

        pallets = generate_pallets_for_day(day)
        lines += _insert_batches("palletstatus", PARTITIONED_TABLES["palletstatus"], pallets)

        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="DGS partitie-bewuste dummy-data generator")
    parser.add_argument("--days", type=int, default=14, help="Aantal dagen terug (default: 14)")
    parser.add_argument("--end", type=str, default=None,
                        help="Einddatum YYYY-MM-DD (default: gisteren)")
    parser.add_argument("--clear", action="store_true",
                        help="Verwijder bestaande data in het bereik eerst")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    import random
    random.seed(args.seed)

    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        end_date = datetime.now().date() - timedelta(days=1)

    print(generate_sql(args.days, end_date, args.clear))


if __name__ == "__main__":
    main()
