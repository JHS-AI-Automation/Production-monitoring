// Datum-helpers voor de dashboard-pagina's. Alle datums zijn ISO-strings (YYYY-MM-DD),
// het formaat dat de API verwacht. Eerder stond `yesterday()` vier keer gekopieerd.

/** Een Date naar een ISO-datumstring (YYYY-MM-DD). */
export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Vandaag als ISO-datumstring. */
export function today(): string {
  return isoDate(new Date());
}

/** Gisteren als ISO-datumstring (default-datum: PLC-data van vandaag is nog niet compleet). */
export function yesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return isoDate(d);
}

/** Een periode van `days` dagen die eindigt op gisteren, voor de trendgrafieken. */
export function rangeEndingYesterday(days: number): { from: string; to: string } {
  const to = new Date();
  to.setDate(to.getDate() - 1);
  const from = new Date(to);
  from.setDate(from.getDate() - days + 1);
  return { from: isoDate(from), to: isoDate(to) };
}
