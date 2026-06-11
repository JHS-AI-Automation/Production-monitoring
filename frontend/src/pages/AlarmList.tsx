import { useEffect, useState } from "react";
import { fetchAlarmList, fetchOpenAlarms, type OpenAlarm } from "../api";
import { useApi } from "../hooks/useApi";
import DatePicker from "../components/DatePicker";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import LoadingSpinner from "../components/LoadingSpinner";
import { AlertTriangle, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { yesterday } from "../lib/date";
import { formatTime } from "../lib/format";
import { SEVERITY_BADGE, SEVERITY_BADGE_FALLBACK } from "../lib/colors";

const STATE_STYLES: Record<string, string> = {
  triggered: "bg-red-50 text-red-600",
  resolved: "bg-green-50 text-green-600",
};

export default function AlarmList() {
  const [date, setDate] = useState(yesterday);
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [date, severity, search]);

  const { data: res, loading, error, retry } = useApi(
    (signal) =>
      fetchAlarmList({
        date,
        severity: severity || undefined,
        search: search || undefined,
        page,
        per_page: 50,
      }, signal),
    [date, severity, search, page],
  );

  const openAlarms = useApi<OpenAlarm[]>(
    (signal) => fetchOpenAlarms(date, signal),
    [date],
    `open-${date}`,
  );

  const items = res?.items ?? [];
  const total = res?.total ?? 0;
  const pages = res?.pages ?? 1;
  const clampedPage = Math.min(page, pages);
  const open = openAlarms.data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">Alarmen</h1>
        <DatePicker value={date} onChange={setDate} />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Zoek in alarmbericht..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dgs-500 focus:border-transparent"
          />
        </div>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dgs-500"
        >
          <option value="">Alle klassen</option>
          <option value="Error">Error</option>
          <option value="Warning">Warning</option>
          <option value="Info">Info</option>
        </select>
        <span className="text-sm text-gray-500">{total} resultaten</span>
      </div>

      {error && <ErrorBanner message={error} onRetry={retry} />}

      {/* Openstaande alarmen */}
      {open.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={18} className="text-red-600" />
            <h2 className="text-sm font-semibold text-red-800">
              {open.length} openstaand{open.length !== 1 ? "e" : ""} alarm{open.length !== 1 ? "en" : ""}
            </h2>
          </div>
          <div className="space-y-1.5">
            {open.map((a, i) => (
              <div
                key={i}
                className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-red-100"
              >
                <span className="text-sm text-gray-700">{a.alarmmessage}</span>
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      SEVERITY_BADGE[a.severityclass] ?? SEVERITY_BADGE_FALLBACK
                    }`}
                  >
                    {a.severityclass}
                  </span>
                  <span className="text-xs text-gray-400 font-mono">
                    {formatTime(a.last_seen, { seconds: false })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {openAlarms.data && open.length === 0 && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-center gap-2">
          <span className="text-green-600 text-sm font-medium">Geen openstaande alarmen</span>
        </div>
      )}

      {/* Desktop table */}
      <div className="hidden md:block bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-dgs-900 text-white text-xs uppercase tracking-wide">
              <th className="text-left px-5 py-3 font-semibold">Tijd</th>
              <th className="text-left px-5 py-3 font-semibold">Alarmbericht</th>
              <th className="text-center px-4 py-3 font-semibold">Klasse</th>
              <th className="text-center px-4 py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <LoadingSpinner />
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <EmptyState message="Geen alarmen gevonden" />
                </td>
              </tr>
            ) : (
              items.map((item, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-gray-50/50" : "bg-white"}>
                  <td className="px-5 py-2.5 text-sm text-gray-600 font-mono">
                    {formatTime(item.time)}
                  </td>
                  <td className="px-5 py-2.5 text-sm text-gray-700">
                    {item.alarmmessage}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded text-xs font-semibold ${
                        SEVERITY_BADGE[item.severityclass] ?? SEVERITY_BADGE_FALLBACK
                      }`}
                    >
                      {item.severityclass}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded text-xs font-semibold ${
                        STATE_STYLES[item.state] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {item.state === "triggered" ? "Actief" : "Verholpen"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-2">
        {loading && items.length === 0 ? (
          <LoadingSpinner />
        ) : items.length === 0 ? (
          <EmptyState message="Geen alarmen gevonden" />
        ) : (
          items.map((item, i) => (
            <div
              key={i}
              className="bg-white rounded-xl border border-gray-200 p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-gray-500">
                  {formatTime(item.time)}
                </span>
                <div className="flex gap-1.5">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      SEVERITY_BADGE[item.severityclass] ?? SEVERITY_BADGE_FALLBACK
                    }`}
                  >
                    {item.severityclass}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      STATE_STYLES[item.state] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {item.state === "triggered" ? "Actief" : "Verholpen"}
                  </span>
                </div>
              </div>
              <p className="text-sm text-gray-700">{item.alarmmessage}</p>
            </div>
          ))
        )}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={clampedPage <= 1}
            className="p-2 rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm text-gray-600">
            Pagina {clampedPage} van {pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={clampedPage >= pages}
            className="p-2 rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
