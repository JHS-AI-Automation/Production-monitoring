import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { fetchTrends, type TrendPoint } from "../api";
import { useApi } from "../hooks/useApi";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import LoadingSpinner from "../components/LoadingSpinner";

function formatRange(days: number): { from: string; to: string } {
  const to = new Date();
  to.setDate(to.getDate() - 1);
  const from = new Date(to);
  from.setDate(from.getDate() - days + 1);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

const RANGES = [
  { label: "7 dagen", days: 7 },
  { label: "14 dagen", days: 14 },
  { label: "30 dagen", days: 30 },
] as const;

export default function Trends() {
  const [days, setDays] = useState(30);
  const { from, to } = formatRange(days);

  const { data, loading, error, retry } = useApi<TrendPoint[]>(
    () => fetchTrends(from, to),
    [days],
    `trends-${days}`,
  );

  const trendData = data ?? [];
  const totalTriggered = trendData.reduce((s, d) => s + d.triggered, 0);
  const totalResolved = trendData.reduce((s, d) => s + d.resolved, 0);
  const avgPerDay = trendData.length > 0 ? Math.round(totalTriggered / trendData.length) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">Trends</h1>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                days === r.days
                  ? "bg-white text-dgs-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Totaal geactiveerd
          </p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalTriggered}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Totaal verholpen
          </p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalResolved}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Gemiddeld per dag
          </p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{avgPerDay}</p>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={retry} />}

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          Alarmen per dag (laatste {days} dagen)
        </h2>
        {loading ? (
          <div className="h-[350px]">
            <LoadingSpinner />
          </div>
        ) : trendData.length === 0 ? (
          <EmptyState message={`Geen alarmdata in de afgelopen ${days} dagen`} />
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                tickFormatter={(d: string) => {
                  const [, m, day] = d.split("-");
                  return `${day}-${m}`;
                }}
              />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                labelFormatter={(d: string) => {
                  const dt = new Date(d);
                  return dt.toLocaleDateString("nl-NL", {
                    weekday: "short",
                    day: "numeric",
                    month: "long",
                  });
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="triggered"
                name="Geactiveerd"
                stroke="#dc2626"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="resolved"
                name="Verholpen"
                stroke="#16a34a"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
