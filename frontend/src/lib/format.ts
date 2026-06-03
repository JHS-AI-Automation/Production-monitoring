// Weergave-formattering (Nederlandse locale). Eerder stonden deze toLocaleTime/Date-
// aanroepen verspreid over Overview en AlarmList.

/** Tijd uit een ISO-string, standaard met seconden. Geeft "-" bij null. */
export function formatTime(iso: string | null, opts: { seconds?: boolean } = {}): string {
  if (!iso) return "-";
  const options: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
  if (opts.seconds !== false) options.second = "2-digit";
  return new Date(iso).toLocaleTimeString("nl-NL", options);
}

/** Datum uit een ISO-string met expliciete opmaak-opties (voor grafiek-labels). */
export function formatDate(iso: string, options: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleDateString("nl-NL", options);
}
