import { RefreshCw } from "lucide-react";

interface Props {
  stale: boolean;
  refreshFailed: boolean;
  lastUpdated: number | null;
  onRetry: () => void;
}

/** Melding wanneer de pagina (tijdelijk) eerder opgehaalde gegevens toont.
 *  Verschijnt alleen bij stale data: direct na een verse fetch is hij onzichtbaar. */
export default function StaleBanner({ stale, refreshFailed, lastUpdated, onRetry }: Props) {
  if (!stale) return null;

  const tijd = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <div className="rounded-lg bg-sky-50 border border-sky-200 px-4 py-2.5 text-sm text-sky-800 flex items-center justify-between gap-3 flex-wrap">
      <span>
        Je kijkt naar eerder opgehaalde gegevens{tijd ? ` (van ${tijd})` : ""}.{" "}
        {refreshFailed
          ? "Vernieuwen lukte zojuist niet, mogelijk is het druk op de server."
          : "Op de achtergrond worden de nieuwste cijfers opgehaald."}
      </span>
      {refreshFailed && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md border border-sky-300 bg-white px-2.5 py-1 text-xs font-medium text-sky-700 hover:bg-sky-100"
        >
          <RefreshCw size={12} />
          Opnieuw proberen
        </button>
      )}
    </div>
  );
}
