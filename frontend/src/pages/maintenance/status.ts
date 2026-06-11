// Statuskleuren voor motoren. Pure functie zodat hij apart te testen is.

export interface StatusMeta {
  label: string;
  text: string;   // tailwind tekstkleur
  bg: string;     // tailwind achtergrond
  ring: string;   // tailwind ring
  dot: string;    // hex voor grafiek/stip
}

export function statusMeta(status: string): StatusMeta {
  switch (status) {
    case "alarm":
      return { label: "Alarm", text: "text-red-700", bg: "bg-red-50", ring: "ring-red-200", dot: "#dc2626" };
    case "warn":
      return { label: "Let op", text: "text-amber-700", bg: "bg-amber-50", ring: "ring-amber-200", dot: "#d97706" };
    case "ok":
      return { label: "Stabiel", text: "text-green-700", bg: "bg-green-50", ring: "ring-green-200", dot: "#16a34a" };
    default:
      return { label: "Onbekend", text: "text-gray-500", bg: "bg-gray-50", ring: "ring-gray-200", dot: "#9ca3af" };
  }
}
