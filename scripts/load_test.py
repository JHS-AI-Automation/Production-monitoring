"""
Load-test voor DGS Optimax: simuleert N gelijktijdige gebruikers die het dashboard
gebruiken en meet latency (p50/p95/p99), foutpercentage en throughput.

Elke gebruiker is een eigen httpx-client (alsof het losse browsers zijn) en doorloopt
per ronde de vijf pagina's; elke pagina vuurt de API-calls af die de echte frontend ook
doet. De frontend cachet 60s per browser, dus dit is een worst-case (elke call raakt de
backend).

Gebruik:
  # backend moet draaien (uvicorn ... --port 8080) tegen de nep-DB
  python scripts/load_test.py --users 5 --rounds 10 --date 2026-06-01
  python scripts/load_test.py --users 10 --rounds 10           # stress-run
  python scripts/load_test.py --users 5 --chat                 # incl. 1 chat per user

Vereist: httpx (zit al in backend/requirements.txt).
"""

import argparse
import asyncio
import statistics
import time
from collections import defaultdict

import httpx

# Pagina -> API-calls die de frontend bij het openen doet (zonder browser-cache).
def _pages(date: str, frm: str, to: str) -> dict[str, list[str]]:
    return {
        "Overzicht": [
            f"/api/alarms/stats?date={date}",
            f"/api/alarms/top?date={date}",
            f"/api/production/oee?date={date}",
        ],
        "Productie": [
            f"/api/production/summary?date={date}",
            f"/api/production/hourly?date={date}",
            f"/api/production/alarm-impact?date={date}",
        ],
        "Pallets": [
            f"/api/pallets/summary?date={date}",
            f"/api/pallets/hourly?date={date}",
        ],
        "Alarmen": [
            f"/api/alarms/list?date={date}&page=1",
            f"/api/alarms/open?date={date}",
        ],
        "Trends": [
            f"/api/alarms/trends?from={frm}&to={to}",
            f"/api/production/trends?from={frm}&to={to}",
        ],
    }


async def _user_session(
    user_id: int, base: str, rounds: int, paths: list[str], results: list, errors: list
):
    """Eén gebruiker: `rounds` keer alle pagina-calls, latency per call vastleggen."""
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        for _ in range(rounds):
            for path in paths:
                start = time.perf_counter()
                try:
                    resp = await client.get(path)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    results.append((path.split("?")[0], elapsed_ms, resp.status_code))
                    if resp.status_code >= 400:
                        errors.append((path, resp.status_code))
                except Exception as e:  # noqa: BLE001 - load-test mag alles vangen
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    results.append((path.split("?")[0], elapsed_ms, "EXC"))
                    errors.append((path, repr(e)))


async def _one_chat(base: str, message: str, results: list, errors: list):
    async with httpx.AsyncClient(base_url=base, timeout=60.0) as client:
        start = time.perf_counter()
        try:
            resp = await client.post("/api/chat", json={"message": message})
            elapsed_ms = (time.perf_counter() - start) * 1000
            results.append(("/api/chat", elapsed_ms, resp.status_code))
            if resp.status_code >= 400:
                errors.append(("/api/chat", resp.status_code))
        except Exception as e:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start) * 1000
            results.append(("/api/chat", elapsed_ms, "EXC"))
            errors.append(("/api/chat", repr(e)))


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    return statistics.quantiles(values, n=100)[min(p, 99) - 1] if len(values) > 1 else values[0]


def _report(results: list, errors: list, wall_s: float, users: int, rounds: int):
    latencies = [r[1] for r in results]
    total = len(results)
    n_err = len([r for r in results if r[2] == "EXC" or (isinstance(r[2], int) and r[2] >= 400)])

    print("\n" + "=" * 64)
    print(f"  LOAD-TEST RESULTAAT  ({users} gebruikers x {rounds} rondes)")
    print("=" * 64)
    print(f"  Totaal requests   : {total}")
    print(f"  Fouten            : {n_err} ({100 * n_err / total:.1f}%)" if total else "  geen requests")
    print(f"  Wall-clock        : {wall_s:.2f}s")
    print(f"  Throughput        : {total / wall_s:.1f} req/s")
    print(f"  Latency p50       : {statistics.median(latencies):.0f} ms")
    print(f"  Latency p95       : {_pct(latencies, 95):.0f} ms")
    print(f"  Latency p99       : {_pct(latencies, 99):.0f} ms")
    print(f"  Latency max       : {max(latencies):.0f} ms")

    print("\n  Per endpoint (p50 / p95 / max ms, n):")
    by_ep: dict[str, list[float]] = defaultdict(list)
    for ep, ms, _ in results:
        by_ep[ep].append(ms)
    for ep in sorted(by_ep):
        v = by_ep[ep]
        print(f"    {ep:42s} {statistics.median(v):6.0f} / {_pct(v, 95):6.0f} / {max(v):6.0f}  (n={len(v)})")

    if errors:
        print(f"\n  Eerste fouten: {errors[:5]}")
    print("=" * 64)


async def _main():
    parser = argparse.ArgumentParser(description="DGS Optimax load-test")
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--date", default="2026-06-01")
    parser.add_argument("--from", dest="frm", default="2026-05-20")
    parser.add_argument("--to", default="2026-06-02")
    parser.add_argument("--chat", action="store_true", help="Voeg 1 gelijktijdige chat per gebruiker toe")
    parser.add_argument("--chat-msg", default="Hoeveel alarmen waren er gisteren?")
    args = parser.parse_args()

    paths = [p for calls in _pages(args.date, args.frm, args.to).values() for p in calls]
    print(f"Start: {args.users} gebruikers, {args.rounds} rondes, {len(paths)} calls/ronde -> {args.base}")

    results: list = []
    errors: list = []
    start = time.perf_counter()
    tasks = [
        _user_session(i, args.base, args.rounds, paths, results, errors)
        for i in range(args.users)
    ]
    if args.chat:
        tasks += [_one_chat(args.base, args.chat_msg, results, errors) for _ in range(args.users)]
    await asyncio.gather(*tasks)
    wall_s = time.perf_counter() - start

    _report(results, errors, wall_s, args.users, args.rounds)


if __name__ == "__main__":
    asyncio.run(_main())
