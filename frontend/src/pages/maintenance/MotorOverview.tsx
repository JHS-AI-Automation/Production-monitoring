import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from "recharts";
import { useApi, combineApi } from "../../hooks/useApi";
import {
  fetchMotors, fetchSignals, fetchMotorHistory,
  type MotorsResponse, type SignalsResponse, type MotorHistory,
} from "../../maintenanceApi";
import { statusMeta } from "./status";
import LoadingSpinner from "../../components/LoadingSpinner";
import ErrorBanner from "../../components/ErrorBanner";
import EmptyState from "../../components/EmptyState";

const DAYS = 60;

export default function MotorOverview() {
  const [selected, setSelected] = useState<number | null>(null);

  const motors = useApi<MotorsResponse>((s) => fetchMotors(DAYS, s), [], "mnt-motors");
  const signals = useApi<SignalsResponse>((s) => fetchSignals(DAYS, s), [], "mnt-signals");
  const { loading, error, retryAll } = combineApi(motors, signals);

  // null = geen motor geselecteerd (type-eerlijk, geen cast).
  const history = useApi<MotorHistory | null>(
    (s) => (selected !== null ? fetchMotorHistory(selected, DAYS, s) : Promise.resolve(null)),
    [selected],
    selected !== null ? `mnt-hist-${selected}` : undefined,
  );

  if (loading && !motors.data) return <LoadingSpinner />;

  const motorList = motors.data?.motors ?? [];
  const signalList = signals.data?.signals ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-800">Maintenance, motoren</h1>

      <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
        In ontwikkeling. De getoonde stroomwaarden zijn <strong>synthetische demo-data</strong>,
        nog niet de echte PLC-metingen. Zodra de PLC-data is gekoppeld, tonen deze grafieken de
        werkelijke motorstromen.
      </div>

      {error && <ErrorBanner message={error} onRetry={retryAll} />}

      {/* Onderhoudssignalen */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Onderhoudssignalen</h2>
        {signalList.length === 0 ? (
          <EmptyState message="Geen signalen: alle motoren draaien stabiel" />
        ) : (
          <div className="space-y-2">
            {signalList.map((s) => {
              const meta = statusMeta(s.status);
              return (
                <div
                  key={s.motor_id}
                  className={`flex items-start gap-3 rounded-lg ${meta.bg} ring-1 ${meta.ring} px-4 py-3 cursor-pointer`}
                  onClick={() => setSelected(s.motor_id)}
                >
                  <span className="inline-block w-2.5 h-2.5 rounded-full mt-1.5" style={{ backgroundColor: meta.dot }} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-800">{s.motor_name}</span>
                      <span className={`text-xs font-medium ${meta.text}`}>{meta.label}</span>
                      <span className="text-xs text-gray-400">lijn {s.line}</span>
                    </div>
                    <p className="text-sm text-gray-600 mt-0.5">{s.advice}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Loopt al ~{s.since_days} dagen op. Klik voor de trendgrafiek.
                    </p>
                  </div>
                  <span className={`text-lg font-bold ${meta.text}`}>+{s.increase_pct.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Motoren-raster */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {motorList.map((m) => {
          const meta = statusMeta(m.status);
          const isSel = m.id === selected;
          return (
            <button
              key={m.id}
              onClick={() => setSelected(isSel ? null : m.id)}
              className={`text-left bg-white rounded-xl border border-gray-200 p-4 transition-all hover:shadow-sm ${
                isSel ? "ring-2 ring-blue-500" : ""
              }`}
              style={{ borderTop: `4px solid ${meta.dot}` }}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-800">{m.name}</span>
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${meta.bg} ${meta.text}`}>
                  {meta.label}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">Lijn {m.line}</p>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {m.current_a != null ? `${m.current_a.toFixed(2)} A` : "-"}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                basislijn {m.baseline_a != null ? `${m.baseline_a.toFixed(2)} A` : "-"}
                {m.increase_pct != null && m.increase_pct >= 1 ? ` · +${m.increase_pct}%` : ""}
              </p>
            </button>
          );
        })}
      </div>

      {/* Trendgrafiek geselecteerde motor */}
      {selected !== null && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            Trend {motorList.find((m) => m.id === selected)?.name ?? `Motor ${selected}`}: dagelijkse piekstroom
          </h2>
          {history.loading ? (
            <div className="flex justify-center py-8">
              <div className="h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : history.data && history.data.history.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={history.data.history} margin={{ left: 4, right: 16, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={28} />
                <YAxis tick={{ fontSize: 11 }} unit=" A" domain={["dataMin - 0.3", "dataMax + 0.3"]} />
                <Tooltip formatter={(v: number) => [`${v} A`, "piekstroom"]} />
                {history.data.analysis && (
                  <ReferenceLine
                    y={history.data.analysis.baseline_a}
                    stroke="#94a3b8"
                    strokeDasharray="5 4"
                    label={{ value: "basislijn", fontSize: 10, fill: "#94a3b8", position: "insideTopLeft" }}
                  />
                )}
                <Line type="monotone" dataKey="peak_a" stroke="#ED1C24" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="Geen historie beschikbaar voor deze motor" />
          )}
        </div>
      )}
    </div>
  );
}
