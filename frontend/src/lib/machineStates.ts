// PackML-machinetoestanden (ISA-88 / OMAC). De PLC rapporteert per eenheid een
// toestandscode 1-17 (kolommen startstop0/1/2 in de DB-tabel `startstops`). Dit
// is dezelfde mapping als de Grafana "State timeline"; de kleuren hieronder volgen
// dat paneel zodat dashboard en Grafana consistent te lezen zijn.
//
// Naast de toestand zelf classificeren we elke code naar de REDEN waarom er geen
// productie is. Dat volgt de OEE-verliesindeling (Six Big Losses / Weihenstephan):
// onderscheid gepland vs ongepland en intern vs extern, zodat je kunt zien WAAROM
// de lijn stilstaat, niet alleen DAT hij stilstaat. Voor de OEE telt alleen
// "Execute" als productieve draaitijd; "Standby" (geen order) valt doorgaans
// buiten de OEE-noemer.

export type Reason =
  | "produceert"
  | "storing"
  | "geblokkeerd"
  | "pauze"
  | "gestopt"
  | "standby"
  | "omstel";

export interface MachineState {
  code: number;
  /** Originele PackML-naam (zoals in Grafana). */
  name: string;
  /** Nederlandse uitleg voor de klant. */
  label: string;
  reason: Reason;
  /** Hex-kleur, afgestemd op het Grafana State-timeline-paneel. */
  color: string;
}

export const MACHINE_STATES: MachineState[] = [
  { code: 1, name: "Clearing", label: "Opruimen na stop", reason: "omstel", color: "#86efac" },
  { code: 2, name: "Stopped", label: "Gestopt", reason: "gestopt", color: "#ef4444" },
  { code: 3, name: "Starting", label: "Aan het opstarten", reason: "omstel", color: "#15803d" },
  { code: 4, name: "Idle", label: "Klaar, geen productie", reason: "standby", color: "#d1d5db" },
  { code: 5, name: "Suspended", label: "Onderbroken (geen aanvoer/afvoer vol)", reason: "geblokkeerd", color: "#f87171" },
  { code: 6, name: "Execute", label: "Produceert", reason: "produceert", color: "#22c55e" },
  { code: 7, name: "Stopping", label: "Aan het stoppen", reason: "gestopt", color: "#b91c1c" },
  { code: 8, name: "Aborting", label: "Noodstop bezig", reason: "storing", color: "#fca5a5" },
  { code: 9, name: "Aborted", label: "Afgebroken (storing)", reason: "storing", color: "#dc2626" },
  { code: 10, name: "Holding", label: "Aan het pauzeren", reason: "pauze", color: "#3b82f6" },
  { code: 11, name: "Held", label: "Gepauzeerd", reason: "pauze", color: "#3b82f6" },
  { code: 12, name: "Unholding", label: "Pauze opheffen", reason: "pauze", color: "#3b82f6" },
  { code: 13, name: "Suspending", label: "Onderbreking bezig", reason: "geblokkeerd", color: "#3b82f6" },
  { code: 14, name: "Unsuspending", label: "Onderbreking opheffen", reason: "geblokkeerd", color: "#3b82f6" },
  { code: 15, name: "Resetting", label: "Resetten", reason: "omstel", color: "#3b82f6" },
  { code: 16, name: "Completing", label: "Afronden", reason: "omstel", color: "#a855f7" },
  { code: 17, name: "Completed", label: "Voltooid", reason: "standby", color: "#a855f7" },
];

/** Toelichting per reden-groep, in volgorde van weergave (productief eerst). */
export const REASON_GROUPS: { reason: Reason; title: string; note: string }[] = [
  { reason: "produceert", title: "Produceert", note: "telt als draaitijd voor de OEE" },
  { reason: "storing", title: "Storing", note: "ongeplande stilstand, machine afgebroken" },
  { reason: "geblokkeerd", title: "Geblokkeerd", note: "wacht op aanvoer of afvoer (externe stop)" },
  { reason: "pauze", title: "Operator-pauze", note: "tijdelijk vastgehouden (interne stop)" },
  { reason: "gestopt", title: "Gestopt", note: "hand- of geplande stop" },
  { reason: "standby", title: "Standby", note: "klaar, geen order (valt meestal buiten de OEE)" },
  { reason: "omstel", title: "Omstel / opstart", note: "kortstondig bij starten, resetten of afronden" },
];

/** States van één reden-groep, in code-volgorde. */
export function statesByReason(reason: Reason): MachineState[] {
  return MACHINE_STATES.filter((s) => s.reason === reason);
}

/** Zoek een toestand op zijn PLC-code (1-17). */
export function stateByCode(code: number): MachineState | undefined {
  return MACHINE_STATES.find((s) => s.code === code);
}
