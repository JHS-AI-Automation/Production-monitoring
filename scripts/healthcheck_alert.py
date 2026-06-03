"""
Externe gezondheidscheck met alerting voor DGS Optimax.

Pollt /api/health en stuurt een melding naar een webhook (Teams/Slack/generiek) zodra
de app onbereikbaar of ongezond (503) is. Bedoeld voor een cron of scheduled task,
los van de app zelf (een app die plat ligt kan zichzelf niet alarmeren).

Gebruik:
  ALERT_WEBHOOK_URL=https://... python scripts/healthcheck_alert.py --url http://localhost:8080

Cron (elke 5 min):
  */5 * * * * ALERT_WEBHOOK_URL=https://... /usr/bin/python3 /app/scripts/healthcheck_alert.py >> /var/log/optimax-alert.log 2>&1

Exit-code: 0 = gezond, 1 = ongezond/onbereikbaar (handig als de runner zelf al alarmeert).
Alleen stdlib, geen dependencies.
"""

import argparse
import json
import os
import sys
import urllib.request


def check(base_url: str, timeout: float) -> tuple[bool, str]:
    """Geef (gezond, detail) terug."""
    url = base_url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            healthy = resp.status == 200 and body.get("status") == "healthy"
            return healthy, f"status={resp.status} db={body.get('database')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} (ongezond, bv. DB onbereikbaar)"
    except Exception as e:  # noqa: BLE001
        return False, f"onbereikbaar: {type(e).__name__}: {e}"


def send_alert(webhook: str, text: str, timeout: float) -> None:
    """Post een simpele JSON-melding. Werkt met Teams/Slack/generieke webhooks ({"text": ...})."""
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            print(f"alert verstuurd (HTTP {resp.status})", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"FOUT bij versturen alert: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimax health-alert")
    parser.add_argument("--url", default=os.environ.get("OPTIMAX_URL", "http://localhost:8080"))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--webhook", default=os.environ.get("ALERT_WEBHOOK_URL", ""))
    args = parser.parse_args()

    healthy, detail = check(args.url, args.timeout)
    if healthy:
        print(f"OK: Optimax gezond ({detail})", file=sys.stderr)
        sys.exit(0)

    text = f"DGS Optimax ONGEZOND op {args.url} - {detail}"
    print(text, file=sys.stderr)
    if args.webhook:
        send_alert(args.webhook, text, args.timeout)
    else:
        print("(geen ALERT_WEBHOOK_URL gezet, geen melding verstuurd)", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
