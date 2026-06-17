import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  fetchStats,
  fetchTopAlarms,
  fetchOee,
  type AlarmStats,
  type TopAlarm,
  type OeeData,
} from "../api";
import { useApi, combineApi } from "../hooks/useApi";
import KPICard from "../components/KPICard";
import DatePicker from "../components/DatePicker";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import LoadingSpinner from "../components/LoadingSpinner";
import StaleBanner from "../components/StaleBanner";
import MachineStateLegend from "../components/MachineStateLegend";
import brand from "../brand";
import { yesterday } from "../lib/date";
import { formatTime } from "../lib/format";
import { SEVERITY_CHART } from "../lib/colors";

export default function Overview() {
  const [date, setDate] = useState(yesterday);

  const stats = useApi<AlarmStats>(
    (signal) => fetchStats(date, signal),
    [date],
    `stats-${date}`,
  );
  const top = useApi<TopAlarm[]>(
    (signal) => fetchTopAlarms(date, 10, signal),
    [date],
    `top-${date}`,
  );
  const oee = useApi<OeeData>(
    (signal) => fetchOee(date, signal),
    [date],
    `oee-${date}`,
  );

  const { loading, error, stale, refreshFailed, lastUpdated, retryAll } = combineApi(stats, top, oee);
  const topAlarms = top.data ?? [];

  const severityData = topAlarms.reduce<Record<string, number>>((acc, a) => {
    acc[a.severityclass] = (acc[a.severityclass] ?? 0) + a.trigger_count;
    return acc;
  }, {});

  const pieData = Object.entries(severityData).map(([name, value]) => ({
    name,
    value,
  }));

  if (loading && !stats.data) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">Overzicht</h1>
        <DatePicker value={date} onChange={setDate} />
      </div>

      {error && <ErrorBanner message={error} onRetry={retryAll} />}
      <StaleBanner stale={stale} refreshFailed={refreshFailed} lastUpdated={lastUpdated} onRetry={retryAll} />

      {stats.data && !error && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              label="Geactiveerd"
              value={stats.data.triggered}
              color="red"
            />
            <KPICard
              label="Verholpen"
              value={stats.data.resolved}
              subtitle={`van ${stats.data.triggered} geactiveerd`}
              color="green"
            />
            <KPICard
              label="Eerste alarm"
              value={formatTime(stats.data.first_alarm)}
              color="blue"
            />
            <KPICard
              label="Laatste alarm"
              value={formatTime(stats.data.last_alarm)}
              color="gray"
            />
          </div>

          {oee.data && oee.data.oee != null && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                OEE (Overall Equipment Effectiveness)
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-6">
                <div className="flex flex-col items-center justify-center">
                  <div className="relative w-36 h-36">
                    <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                      <circle cx="60" cy="60" r="52" fill="none" stroke="#e5e7eb" strokeWidth="12" />
                      <circle
                        cx="60" cy="60" r="52" fill="none"
                        stroke={oee.data.oee >= 85 ? "#16a34a" : oee.data.oee >= 65 ? "#ca8a04" : "#dc2626"}
                        strokeWidth="12"
                        strokeLinecap="round"
                        strokeDasharray={`${(oee.data.oee / 100) * 2 * Math.PI * 52} ${2 * Math.PI * 52}`}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className={`text-3xl font-bold ${
                        oee.data.oee >= 85 ? "text-green-600" : oee.data.oee >= 65 ? "text-yellow-600" : "text-red-600"
                      }`}>
                        {oee.data.oee}%
                      </span>
                      <span className="text-xs text-gray-400">OEE</span>
                    </div>
                  </div>
                  <div className="flex gap-4 mt-3">
                    {[
                      { label: "A", value: oee.data.availability, tip: "Beschikbaarheid" },
                      { label: "P", value: oee.data.performance, tip: "Prestatie" },
                      { label: "Q", value: oee.data.quality, tip: "Kwaliteit" },
                    ].map(({ label, value, tip }) => (
                      <div key={label} className="text-center" title={tip}>
                        <p className="text-xs font-medium text-gray-400">{label}</p>
                        <p className="text-sm font-bold text-gray-700">{value?.toFixed(1) ?? "-"}%</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <h3 className="text-xs font-medium text-gray-500 mb-2">OEE per robot</h3>
                    <div className="space-y-2">
                      {oee.data.per_robot.map((r) => (
                        <div key={r.robot} className="flex items-center gap-3">
                          <span className="text-xs text-gray-500 w-16">{r.name}</span>
                          <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${r.oee}%`,
                                backgroundColor: r.oee >= 85 ? "#16a34a" : r.oee >= 65 ? "#ca8a04" : "#dc2626",
                              }}
                            />
                          </div>
                          <span className="text-xs font-bold text-gray-700 w-14 text-right">{r.oee}%</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {oee.data.losses && (
                    <div>
                      <h3 className="text-xs font-medium text-gray-500 mb-2">Tijdverlies (gem. per lijn)</h3>
                      <div className="flex h-6 rounded-full overflow-hidden bg-gray-100">
                        <div
                          className="bg-green-500"
                          style={{ width: `${(oee.data.losses.effective_time / oee.data.losses.planned_time) * 100}%` }}
                          title={`Effectief: ${oee.data.losses.effective_time} min`}
                        />
                        <div
                          className="bg-yellow-500"
                          style={{ width: `${(oee.data.losses.speed_loss / oee.data.losses.planned_time) * 100}%` }}
                          title={`Snelheidsverlies: ${oee.data.losses.speed_loss} min`}
                        />
                        <div
                          className="bg-red-500"
                          style={{ width: `${(oee.data.losses.downtime_loss / oee.data.losses.planned_time) * 100}%` }}
                          title={`Stilstand: ${oee.data.losses.downtime_loss} min`}
                        />
                      </div>
                      <div className="flex justify-between mt-1.5 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                          Effectief {oee.data.losses.effective_time} min
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block w-2 h-2 rounded-full bg-yellow-500" />
                          Snelheid {oee.data.losses.speed_loss} min
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
                          Stilstand {oee.data.losses.downtime_loss} min
                        </span>
                      </div>
                    </div>
                  )}

                  {oee.data.six_big_losses.length > 0 && (
                    <div>
                      <h3 className="text-xs font-medium text-gray-500 mb-2">Six Big Losses</h3>
                      <div className="grid grid-cols-2 gap-2">
                        {oee.data.six_big_losses.map((loss) => (
                          <div key={loss.category} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-1.5">
                            <span className="text-xs text-gray-600">{loss.category}</span>
                            <span className="text-xs font-bold text-gray-700">
                              {loss.events != null ? `${loss.events}x` : `${loss.minutes} min`}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <MachineStateLegend />
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                Top alarmen (aantal triggers)
              </h2>
              {topAlarms.length === 0 ? (
                <EmptyState message="Geen alarmen op deze datum" />
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={topAlarms.slice(0, 8)}
                    layout="vertical"
                    margin={{ left: 8, right: 24 }}
                  >
                    <XAxis type="number" tick={{ fontSize: 12 }} />
                    <YAxis
                      type="category"
                      dataKey="alarmmessage"
                      width={200}
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: string) =>
                        v.length > 35 ? v.slice(0, 35) + "..." : v
                      }
                      hide={typeof window !== "undefined" && window.innerWidth < 640}
                    />
                    <Tooltip />
                    <Bar dataKey="trigger_count" fill={brand.chartAccent} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                Verdeling per klasse
              </h2>
              {pieData.length === 0 ? (
                <EmptyState message="Geen data" />
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {pieData.map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={SEVERITY_CHART[entry.name] ?? "#6b7280"}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      )}

    </div>
  );
}
