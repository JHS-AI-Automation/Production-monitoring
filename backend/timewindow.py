"""Gedeelde datum-validatie voor de API-routers.

Alle endpoints werken met een dag (`date`) of een periode (`from`/`to`). De validatie
was identiek gekopieerd in alarms.py, production.py en pallets.py; die ene bron staat nu hier.

Conventie:
- Geen datum opgegeven -> gisteren (de PLC-data van vandaag is nog niet compleet).
- Datums in de toekomst worden geweigerd.
- Een periode mag maximaal MAX_TREND_DAYS dagen beslaan.

Tijdzone: "vandaag/gisteren" is expliciet Amsterdam-tijd (de fabriek), NIET de
kloktijd van de container of host. Anders verspringt de default-dag rond
middernacht UTC i.p.v. middernacht lokale tijd (een container zonder TZ-config
draait op UTC). Het PyPI-pakket tzdata levert de zone-database waar het OS die
niet heeft (Windows-dev, slanke containers).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

MAX_TREND_DAYS = 365
FACTORY_TZ = ZoneInfo("Europe/Amsterdam")


def factory_today() -> date:
    """De huidige datum in de fabriek (Amsterdam), onafhankelijk van host/container-TZ."""
    return datetime.now(FACTORY_TZ).date()


def validate_date(target_date: date | None) -> date:
    """Geef een geldige doeldatum terug; default = gisteren (Amsterdam)."""
    if target_date is None:
        return factory_today() - timedelta(days=1)
    if target_date > factory_today():
        raise HTTPException(400, f"Datum {target_date} ligt in de toekomst")
    return target_date


def validate_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    """Valideer en normaliseer een periode; default = de laatste 30 dagen tot gisteren."""
    if date_to is None:
        date_to = factory_today() - timedelta(days=1)
    if date_from is None:
        date_from = date_to - timedelta(days=29)
    if date_to > factory_today():
        raise HTTPException(400, f"Einddatum {date_to} ligt in de toekomst")
    if date_from > date_to:
        raise HTTPException(400, "Startdatum mag niet na einddatum liggen")
    if (date_to - date_from).days > MAX_TREND_DAYS:
        raise HTTPException(400, f"Maximale periode is {MAX_TREND_DAYS} dagen")
    return date_from, date_to
