// Gedeelde kleur-mappings voor alarm-severity. Lijnkleuren staan in brand.ts.

/** Tailwind-badgeklassen per severity (gebruikt in tabellen en lijsten). */
export const SEVERITY_BADGE: Record<string, string> = {
  Error: "bg-red-100 text-red-700",
  Warning: "bg-yellow-100 text-yellow-700",
  Info: "bg-blue-100 text-blue-700",
};

/** Hex-kleuren per severity (gebruikt in recharts-grafieken). */
export const SEVERITY_CHART: Record<string, string> = {
  Error: "#dc2626",
  Warning: "#ca8a04",
  Info: "#0284c7",
};

/** Fallback-badge voor onbekende severity. */
export const SEVERITY_BADGE_FALLBACK = "bg-gray-100 text-gray-600";
