import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  LineChart,
  Line,
} from "recharts";
import {
  fetchPalletSummary,
  fetchHourlyPallets,
  type PalletSummary,
  type HourlyPallet,
} from "../api";
import { useApi, combineApi } from "../hooks/useApi";
import DatePicker from "../components/DatePicker";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import LoadingSpinner from "../components/LoadingSpinner";
import { yesterday } from "../lib/date";

const STATION_COLORS: Record<string, string> = {
  "6000": "#6366f1",
  "6005": "#0891b2",
  "6010": "#d946ef",
  "6015": "#f97316",
};

const STATUS_COLORS = {
  ready: "#16a34a",
  empty: "#ca8a04",
  none: "#dc2626",
};

export default function Pallets() {
  const [date, setDate] = useState(yesterday);

  const summary = useApi<PalletSummary>(
    (signal) => fetchPalletSummary(date, signal),
    [date],
    `pallet-summary-${date}`,
  );
  const hourly = useApi<HourlyPallet[]>(
    (signal) => fetchHourlyPallets(date, signal),
    [date],
    `pallet-hourly-${date}`,
  );

  const { loading, error, retryAll } = combineApi(summary, hourly);
  const s = summary.data;
  const h = hourly.data ?? [];

  if (loading && !s) {
    return <LoadingSpinner />;
  }

  const stationChartData =
    s?.stations.map((st) => ({
      station: `Station ${st.id}`,
      Klaar: st.ready_pct,
      Leeg: st.empty_pct,
      "Geen pallet": st.none_pct,
    })) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">Palletstatus</h1>
        <DatePicker value={date} onChange={setDate} />
      </div>

      {error && <ErrorBanner message={error} onRetry={retryAll} />}

      {s && !error && (
        <>
          {s.total_readings === 0 ? (
            <EmptyState message={`Geen palletdata op ${date}`} />
          ) : (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {s.stations.map((st) => (
                  <div
                    key={st.id}
                    className="bg-white rounded-xl border border-gray-200 p-5"
                    style={{ borderTop: `4px solid ${STATION_COLORS[st.id]}` }}
                  >
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Station {st.id}
                    </p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">
                      {st.ready_pct}% bezet
                    </p>
                    <div className="flex gap-3 mt-2 text-xs text-gray-400">
                      <span>{st.empty_pct}% leeg</span>
                      <span>{st.none_pct}% geen pallet</span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-4">
                  Statusverdeling per station (%)
                </h2>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={stationChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="station" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                    <Tooltip />
                    <Legend />
                    <Bar
                      dataKey="Klaar"
                      fill={STATUS_COLORS.ready}
                      radius={[2, 2, 0, 0]}
                    />
                    <Bar
                      dataKey="Leeg"
                      fill={STATUS_COLORS.empty}
                      radius={[2, 2, 0, 0]}
                    />
                    <Bar
                      dataKey="Geen pallet"
                      fill={STATUS_COLORS.none}
                      radius={[2, 2, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-4">
                  Bezettingsgraad per uur (% klaar)
                </h2>
                {h.length === 0 ? (
                  <EmptyState message="Geen uurlijkse data beschikbaar" />
                ) : (
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={h}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                      <Tooltip />
                      <Legend />
                      {Object.entries(STATION_COLORS).map(([id, color]) => (
                        <Line
                          key={id}
                          type="monotone"
                          dataKey={`s${id}`}
                          name={`Station ${id}`}
                          stroke={color}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>

              <p className="text-xs text-gray-400 text-center">
                {s.total_readings.toLocaleString("nl-NL")} meetpunten op{" "}
                {date}. Statuscode: 100 = geen pallet, 200 = leeg, 300 = klaar.
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
}
