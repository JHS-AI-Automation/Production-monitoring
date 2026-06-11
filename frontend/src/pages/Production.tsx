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
} from "recharts";
import {
  fetchProductionSummary,
  fetchHourlyProduction,
  fetchAlarmImpact,
  type ProductionSummary,
  type HourlyProduction,
  type AlarmImpact,
} from "../api";
import { useApi, combineApi } from "../hooks/useApi";
import KPICard from "../components/KPICard";
import DatePicker from "../components/DatePicker";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import LoadingSpinner from "../components/LoadingSpinner";
import ProductionFlowDiagram from "../components/ProductionFlowDiagram";
import brand from "../brand";
import { yesterday } from "../lib/date";

const LINE_COLORS = brand.lineColors;
const LINE_NAMES = ["Lijn 1", "Lijn 2", "Lijn 3", "Lijn 4"];

export default function Production() {
  const [date, setDate] = useState(yesterday);

  const summary = useApi<ProductionSummary>(
    (signal) => fetchProductionSummary(date, signal),
    [date],
    `prod-summary-${date}`,
  );
  const hourly = useApi<HourlyProduction[]>(
    (signal) => fetchHourlyProduction(date, signal),
    [date],
    `prod-hourly-${date}`,
  );
  const impact = useApi<AlarmImpact>(
    (signal) => fetchAlarmImpact(date, signal),
    [date],
    `prod-impact-${date}`,
  );

  const { loading, error, retryAll } = combineApi(summary, hourly, impact);
  const s = summary.data;
  const h = hourly.data ?? [];
  const imp = impact.data;

  if (loading && !s) {
    return <LoadingSpinner />;
  }

  const avgDowntime = s
    ? Math.round(s.downtime_minutes.reduce((a, b) => a + b, 0) / 4)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">Productie</h1>
        <DatePicker value={date} onChange={setDate} />
      </div>

      {error && <ErrorBanner message={error} onRetry={retryAll} />}

      {s && !error && s.data_gap_minutes > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-2.5 text-sm text-amber-800">
          Let op: {s.data_gap_minutes} van de {s.shift_minutes} shift-minuten hebben{" "}
          <strong>geen meetdata</strong> (logger of dataverbinding weg). Deze minuten tellen
          niet mee als stilstand; de KPI's hieronder gaan alleen over de gemeten minuten.
        </div>
      )}

      {s && !error && (
        <>
          {s.grand_total === 0 ? (
            <EmptyState message={`Geen productiedata op ${date}`} />
          ) : (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                <KPICard
                  label="Totaal producten"
                  value={s.grand_total.toLocaleString("nl-NL")}
                  color="red"
                />
                <KPICard
                  label="Piekuur"
                  value={s.peak_hour ?? "-"}
                  subtitle={`${s.peak_hour_total.toLocaleString("nl-NL")} producten`}
                  color="blue"
                />
                <KPICard
                  label="Stilstand"
                  value={`${avgDowntime} min`}
                  subtitle="gemiddeld per lijn"
                  color="gray"
                />
                <KPICard
                  label="Lijn-balans"
                  value={s.line_balance != null ? s.line_balance.toFixed(2) : "-"}
                  subtitle="1.0 = perfect in balans"
                  color={s.line_balance != null && s.line_balance >= 0.7 ? "green" : "red"}
                />
                <KPICard
                  label="MTTR"
                  value={s.mttr_avg_minutes != null ? `${s.mttr_avg_minutes} min` : "-"}
                  subtitle={
                    s.mttr_resolved > 0
                      ? `${s.mttr_resolved} opgelost, ${s.mttr_unresolved} open`
                      : "geen alarmdata"
                  }
                  color="blue"
                />
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {s.per_line.map((total, i) => (
                  <div
                    key={i}
                    className="bg-white rounded-xl border border-gray-200 p-5"
                    style={{ borderTop: `4px solid ${LINE_COLORS[i]}` }}
                  >
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                      {LINE_NAMES[i]}
                    </p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">
                      {total.toLocaleString("nl-NL")}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      {s.downtime_minutes[i]} min stilstand
                    </p>
                  </div>
                ))}
              </div>

              {h.length === 0 ? (
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <EmptyState message="Geen uurlijkse data beschikbaar" />
                </div>
              ) : (
                <ProductionFlowDiagram hourlyData={h} date={date} />
              )}

              {imp && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-white rounded-xl border border-gray-200 p-5">
                    <h2 className="text-sm font-semibold text-gray-700 mb-4">
                      Alarm-impact op productie
                    </h2>
                    {imp.alarm_minutes === 0 && imp.normal_minutes === 0 ? (
                      <EmptyState message="Geen alarm-impact data" />
                    ) : (
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">
                            Gem. productie tijdens alarm
                          </span>
                          <span className="text-lg font-bold text-red-600">
                            {imp.avg_during_alarm?.toFixed(1) ?? "-"} producten/min
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">
                            Gem. productie zonder alarm
                          </span>
                          <span className="text-lg font-bold text-green-600">
                            {imp.avg_without_alarm?.toFixed(1) ?? "-"} producten/min
                          </span>
                        </div>
                        {imp.production_loss_pct != null && (
                          <div className="pt-3 border-t border-gray-100 flex justify-between items-center">
                            <span className="text-sm font-medium text-gray-700">
                              Productieverlies
                            </span>
                            <span
                              className={`text-lg font-bold ${
                                imp.production_loss_pct > 0
                                  ? "text-red-600"
                                  : "text-green-600"
                              }`}
                            >
                              {imp.production_loss_pct > 0 ? "-" : "+"}
                              {Math.abs(imp.production_loss_pct)}%
                            </span>
                          </div>
                        )}
                        <p className="text-xs text-gray-400 pt-2">
                          {imp.alarm_minutes} min met alarm,{" "}
                          {imp.normal_minutes} min normaal
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="bg-white rounded-xl border border-gray-200 p-5">
                    <h2 className="text-sm font-semibold text-gray-700 mb-4">
                      Productie vs alarmen per uur
                    </h2>
                    {imp.hourly_correlation.length === 0 ? (
                      <EmptyState message="Geen correlatie data" />
                    ) : (
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={imp.hourly_correlation}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                          <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                          <YAxis yAxisId="prod" tick={{ fontSize: 11 }} />
                          <YAxis
                            yAxisId="alarms"
                            orientation="right"
                            tick={{ fontSize: 11 }}
                          />
                          <Tooltip />
                          <Legend />
                          <Bar
                            yAxisId="prod"
                            dataKey="production"
                            name="Productie (producten)"
                            fill={brand.chartAccent}
                            radius={[2, 2, 0, 0]}
                            opacity={0.7}
                          />
                          <Bar
                            yAxisId="alarms"
                            dataKey="alarms"
                            name="Alarmen"
                            fill="#6b7280"
                            radius={[2, 2, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
