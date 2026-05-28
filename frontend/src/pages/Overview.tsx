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
import { fetchStats, fetchTopAlarms, type AlarmStats, type TopAlarm } from "../api";
import { useApi } from "../hooks/useApi";
import KPICard from "../components/KPICard";
import AlarmTable from "../components/AlarmTable";
import DatePicker from "../components/DatePicker";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import LoadingSpinner from "../components/LoadingSpinner";
import brand from "../brand.js";

function yesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

const SEVERITY_COLORS: Record<string, string> = {
  Error: "#dc2626",
  Warning: "#ca8a04",
  Info: "#0284c7",
};

export default function Overview() {
  const [date, setDate] = useState(yesterday);

  const stats = useApi<AlarmStats>(
    () => fetchStats(date),
    [date],
    `stats-${date}`,
  );
  const top = useApi<TopAlarm[]>(
    () => fetchTopAlarms(date),
    [date],
    `top-${date}`,
  );

  const loading = stats.loading || top.loading;
  const error = stats.error || top.error;
  const topAlarms = top.data ?? [];

  const severityData = topAlarms.reduce<Record<string, number>>((acc, a) => {
    acc[a.severityclass] = (acc[a.severityclass] ?? 0) + a.trigger_count;
    return acc;
  }, {});

  const pieData = Object.entries(severityData).map(([name, value]) => ({
    name,
    value,
  }));

  const fmtTime = (iso: string | null) => {
    if (!iso) return "-";
    return new Date(iso).toLocaleTimeString("nl-NL", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  if (loading && !stats.data) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">Overzicht</h1>
        <DatePicker value={date} onChange={setDate} />
      </div>

      {error && <ErrorBanner message={error} onRetry={() => { stats.retry(); top.retry(); }} />}

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
              value={fmtTime(stats.data.first_alarm)}
              color="blue"
            />
            <KPICard
              label="Laatste alarm"
              value={fmtTime(stats.data.last_alarm)}
              color="gray"
            />
          </div>

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
                          fill={SEVERITY_COLORS[entry.name] ?? "#6b7280"}
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

      {stats.data && stats.data.triggered === 0 && !error && (
        <EmptyState message={`Geen alarmen geregistreerd op ${date}`} />
      )}

      {topAlarms.length > 0 && (
        <AlarmTable alarms={topAlarms} title={`Top alarmen - ${date}`} />
      )}
    </div>
  );
}
