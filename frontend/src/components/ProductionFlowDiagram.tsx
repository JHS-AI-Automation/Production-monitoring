import { useCallback, useRef, useState } from "react";
import { useApi } from "../hooks/useApi";
import {
  fetchMinutelyProduction,
  type HourlyProduction,
  type MinutelyProduction,
} from "../api";
import brand from "../brand";

interface Props {
  hourlyData: HourlyProduction[];
  date: string;
}

const LINE_COLORS = brand.lineColors;
const INFEED_COLOR = "#3b82f6";
const ROBOT1_COLOR = LINE_COLORS[0];
const ROBOT2_COLOR = LINE_COLORS[3];

// Kleur op basis van het gemist-percentage (instroom die niet geplaatst werd).
function missColor(pct: number): string {
  if (pct > 20) return "#ef4444";
  if (pct > 5) return "#f59e0b";
  return "#22c55e";
}

function loadColor(value: number, max: number): string {
  if (max === 0) return "#e5e7eb";
  const ratio = value / max;
  if (ratio > 0.85) return "#ef4444";
  if (ratio > 0.6) return "#f59e0b";
  return "#22c55e";
}

function FlowBox({
  x, y, name, tag, count, color, maxVal,
}: {
  x: number; y: number; name: string; tag: string;
  count: number; color: string; maxVal: number;
}) {
  const W = 180, H = 110, barW = 156;
  const fillW = maxVal > 0
    ? Math.max((count / maxVal) * barW, count > 0 ? 6 : 0)
    : 0;
  const lc = loadColor(count, maxVal);

  return (
    <g>
      <rect x={x} y={y} width={W} height={H} rx={10}
        fill="white" stroke="#e2e8f0" strokeWidth={1.5} />
      <rect x={x} y={y} width={W} height={30} rx={10}
        fill={color} opacity={0.1} />
      <rect x={x} y={y + 22} width={W} height={8}
        fill={color} opacity={0.1} />
      <text x={x + 12} y={y + 20} fontSize={12}
        fontWeight="700" fill={color}>{name}</text>
      <text x={x + W - 12} y={y + 19} fontSize={9}
        fontWeight="500" fill="#94a3b8" textAnchor="end">{tag}</text>
      <rect x={x + 12} y={y + 42} width={barW} height={22}
        rx={6} fill="#f1f5f9" />
      <rect x={x + 12} y={y + 42} width={fillW} height={22}
        rx={6} fill={lc} opacity={0.7}>
        <animate attributeName="width" from="0" to={fillW}
          dur="0.5s" fill="freeze" />
      </rect>
      <text x={x + 12} y={y + 90} fontSize={18}
        fontWeight="700" fill="#1e293b">
        {count.toLocaleString("nl-NL")}
      </text>
      <text x={x + 12} y={y + 103} fontSize={10} fill="#94a3b8">/uur</text>
    </g>
  );
}

const MINUTE_SERIES = [
  { key: "infeed" as const, name: "Instroom", color: INFEED_COLOR, robot: false },
  { key: "robot1" as const, name: "Robot 1", color: ROBOT1_COLOR, robot: true },
  { key: "robot2" as const, name: "Robot 2", color: ROBOT2_COLOR, robot: true },
];

function MinuteDetail({ data }: { data: MinutelyProduction[] }) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const allVals = MINUTE_SERIES.map(l => data.map(m => m[l.key]));
  const sharedMax = Math.max(...allVals.flat(), 1);
  const labelW = 36;
  const chartW = 600;
  const chartH = 48;
  const ticks = [Math.round(sharedMax), Math.round(sharedMax * 0.5), 0];
  const n = data.length;

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const xPct = (e.clientX - rect.left) / rect.width;
    const idx = Math.round(xPct * (n - 1));
    setHoverIdx(Math.max(0, Math.min(idx, n - 1)));
  }, [n]);

  const handleMouseLeave = useCallback(() => setHoverIdx(null), []);

  const hoverX = hoverIdx !== null && n > 1 ? (hoverIdx / (n - 1)) * chartW : null;

  return (
    <div ref={containerRef}>
      <div className="flex items-center gap-3 mb-2 text-[10px] text-gray-400">
        <span>Max: {sharedMax.toLocaleString("nl-NL")}</span>
        <span className="border-l border-gray-200 pl-3">Instroom en robots op dezelfde schaal</span>
        {hoverIdx !== null && (
          <span className="ml-auto font-medium text-gray-600">
            {data[hoverIdx].minute}
          </span>
        )}
      </div>
      <div className="space-y-3">
        {MINUTE_SERIES.map((line, li) => {
          const vals = allVals[li];
          const total = vals.reduce((a, b) => a + b, 0);
          const points = vals
            .map((v, i) => {
              const x = n > 1 ? (i / (n - 1)) * chartW : chartW / 2;
              const y = chartH - (v / sharedMax) * chartH;
              return `${x},${y}`;
            })
            .join(" ");
          const areaPoints = `0,${chartH} ${points} ${chartW},${chartH}`;
          const hoverVal = hoverIdx !== null ? vals[hoverIdx] : null;
          const hoverY = hoverVal !== null ? chartH - (hoverVal! / sharedMax) * chartH : null;
          return (
            <div key={line.key}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium w-16" style={{ color: line.color }}>
                  {line.name}
                </span>
                {line.robot && (
                  <svg width="12" height="12" viewBox="0 0 28 28">
                    <path d="M6 22 L6 12 L14 6 L22 12 L22 22" stroke={line.color} strokeWidth={3} fill="none" strokeLinecap="round" strokeLinejoin="round" />
                    <circle cx={14} cy={12} r={3} fill={line.color} />
                  </svg>
                )}
                <span className="text-[11px] text-gray-400 ml-auto">
                  {hoverIdx !== null ? (
                    <span style={{ color: line.color }} className="font-semibold">{hoverVal!.toLocaleString("nl-NL")}</span>
                  ) : (
                    total.toLocaleString("nl-NL")
                  )}
                </span>
              </div>
              <div className="flex">
                <div className="flex flex-col justify-between py-px" style={{ width: labelW }}>
                  {ticks.map(t => (
                    <span key={t} className="text-[9px] text-gray-300 text-right pr-1 leading-none">
                      {t}
                    </span>
                  ))}
                </div>
                <svg
                  viewBox={`0 0 ${chartW} ${chartH}`}
                  className="flex-1 h-12 bg-gray-50 rounded"
                  preserveAspectRatio="none"
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleMouseLeave}
                  style={{ cursor: "crosshair" }}
                >
                  {[1, 0.75, 0.5, 0.25].map(frac => (
                    <line key={frac} x1={0} y1={chartH - frac * chartH} x2={chartW} y2={chartH - frac * chartH}
                      stroke="#e5e7eb" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                  ))}
                  <line x1={0} y1={chartH * 0.5} x2={chartW} y2={chartH * 0.5}
                    stroke="#d1d5db" strokeWidth={1} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
                  <polygon points={areaPoints} fill={line.color} opacity={0.1} />
                  <polyline points={points} fill="none" stroke={line.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
                  {hoverX !== null && (
                    <>
                      <line x1={hoverX} y1={0} x2={hoverX} y2={chartH}
                        stroke="#94a3b8" strokeWidth={1} strokeDasharray="3 2" vectorEffect="non-scaling-stroke" />
                      <circle cx={hoverX} cy={hoverY!} r={4} fill={line.color} stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" />
                    </>
                  )}
                </svg>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ProductionFlowDiagram({ hourlyData, date }: Props) {
  const [selectedHour, setSelectedHour] = useState<number | null>(null);

  const peak = hourlyData.reduce(
    (best, h) => (h.placed > (best?.placed ?? 0) ? h : best),
    hourlyData[0],
  );
  const activeHourStr = selectedHour !== null
    ? `${String(selectedHour).padStart(2, "0")}:00`
    : peak?.hour;
  const d = hourlyData.find(h => h.hour === activeHourStr) ?? peak;

  const minutely = useApi<MinutelyProduction[]>(
    (signal) => selectedHour !== null
      ? fetchMinutelyProduction(date, selectedHour, signal)
      : Promise.resolve([]),
    [date, selectedHour],
    selectedHour !== null ? `prod-min-${date}-${selectedHour}` : undefined,
  );

  if (!d) return null;

  // Model: de camera detecteert de instroom (infeed); robot 1 en 2 plaatsen samen
  // het geplaatste deel. Wat niet geplaatst wordt is "gemist" (overflow). Een hoog
  // gemist-percentage = de robots houden de aanvoer niet bij.
  const gemist = Math.max(0, d.infeed - d.placed);
  const gemistPct = d.infeed > 0 ? (gemist / d.infeed) * 100 : 0;
  const maxVal = Math.max(d.infeed, d.robot1, d.robot2, d.placed, 1);
  const arrowCol = missColor(gemistPct);
  const arrowW = gemistPct > 20 ? 3.5 : 2.5;
  const markerName = gemistPct > 20 ? "red" : gemistPct > 5 ? "amber" : "green";

  const shiftHours = hourlyData.filter(h => {
    const hr = parseInt(h.hour);
    return hr >= 5 && hr <= 22;
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-700">
          Productiestroom{" "}
          <span className="font-normal text-gray-400">
            {selectedHour !== null
              ? `${String(selectedHour).padStart(2, "0")}:00`
              : `piekuur (${peak?.hour ?? "-"})`}
          </span>
        </h2>
        {d.infeed > 0 && (
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
              gemistPct > 20
                ? "bg-red-50 text-red-600 ring-1 ring-red-200"
                : gemistPct > 5
                  ? "bg-amber-50 text-amber-600 ring-1 ring-amber-200"
                  : "bg-green-50 text-green-600 ring-1 ring-green-200"
            }`}
          >
            {gemistPct.toFixed(0)}% gemist (rendement {(100 - gemistPct).toFixed(0)}%)
          </span>
        )}
      </div>

      {/* Factory Schematic: instroom -> 2 robots -> geplaatst, met gemist als lek */}
      <svg viewBox="0 0 760 410" className="w-full mx-auto" style={{ maxWidth: 720 }}>
        <defs>
          <style>{`
            @keyframes dash{from{stroke-dashoffset:16}to{stroke-dashoffset:0}}
            .flow{animation:dash .7s linear infinite}
          `}</style>
          <marker id="a-gray" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0,8 3,0 6" fill="#cbd5e1" />
          </marker>
          <marker id="a-green" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0,8 3,0 6" fill="#22c55e" />
          </marker>
          <marker id="a-amber" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0,8 3,0 6" fill="#f59e0b" />
          </marker>
          <marker id="a-red" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0,8 3,0 6" fill="#ef4444" />
          </marker>
        </defs>

        {/* === INSTROOM (boven) === */}
        <text x={290} y={12} textAnchor="middle" fontSize={10} fontWeight="600"
          fill="#94a3b8" style={{ letterSpacing: "0.08em" }}>INSTROOM (CAMERA)</text>
        <FlowBox x={200} y={18} name="Instroom" tag="ERKANNT"
          count={d.infeed} color={INFEED_COLOR} maxVal={maxVal} />
        {/* Splitsing naar de twee robots */}
        <path d="M 250 130 L 130 168" fill="none" stroke="#cbd5e1" strokeWidth={2} markerEnd="url(#a-gray)" />
        <path d="M 330 130 L 450 168" fill="none" stroke="#cbd5e1" strokeWidth={2} markerEnd="url(#a-gray)" />
        {/* Lek naar gemist (rechts) */}
        {gemist > 0 && (
          <path d="M 380 73 L 560 73" fill="none" stroke={arrowCol} strokeWidth={arrowW}
            strokeDasharray="10 6" className="flow" markerEnd={`url(#a-${markerName})`} />
        )}

        {/* === ROBOTS (midden) === */}
        <FlowBox x={40} y={170} name="Robot 1" tag="PLAATST"
          count={d.robot1} color={ROBOT1_COLOR} maxVal={maxVal} />
        <FlowBox x={360} y={170} name="Robot 2" tag="PLAATST"
          count={d.robot2} color={ROBOT2_COLOR} maxVal={maxVal} />

        {/* === GEMIST (rechtsboven) === */}
        <rect x={560} y={40} width={160} height={66} rx={10}
          fill="none" stroke={arrowCol} strokeWidth={1.5} strokeDasharray="5 4" />
        <text x={640} y={62} textAnchor="middle" fontSize={10} fontWeight="600"
          fill="#94a3b8" style={{ letterSpacing: "0.06em" }}>GEMIST (OVERFLOW)</text>
        <text x={640} y={88} textAnchor="middle" fontSize={18} fontWeight="700" fill={arrowCol}>
          {gemist.toLocaleString("nl-NL")}
        </text>

        {/* === GEPLAATST (onder) === */}
        <path d="M 130 280 L 250 320" fill="none" stroke="#22c55e" strokeWidth={2.5} markerEnd="url(#a-green)" />
        <path d="M 450 280 L 330 320" fill="none" stroke="#22c55e" strokeWidth={2.5} markerEnd="url(#a-green)" />
        <FlowBox x={200} y={300} name="Geplaatst" tag="ROBOT-OUTPUT"
          count={d.placed} color="#16a34a" maxVal={maxVal} />
      </svg>

      {/* Hourly Timeline */}
      <div className="mt-5">
        <p className="text-[11px] text-gray-400 mb-2 uppercase tracking-wide">
          Tijdlijn (klik voor detail)
        </p>
        <div className="flex gap-1">
          {shiftHours.map((h) => {
            const hr = parseInt(h.hour);
            const g = Math.max(0, h.infeed - h.placed);
            const pct = h.infeed > 0 ? (g / h.infeed) * 100 : 0;
            const sel = hr === selectedHour;
            const isPeak = h.hour === peak?.hour && selectedHour === null;
            return (
              <button
                key={hr}
                onClick={() => setSelectedHour(hr === selectedHour ? null : hr)}
                className={`flex-1 h-9 rounded-md text-[11px] font-medium transition-all
                  ${sel ? "ring-2 ring-blue-500 ring-offset-1 shadow-sm" : ""}
                  ${isPeak && !sel ? "ring-1 ring-gray-300" : ""}
                `}
                style={{
                  backgroundColor:
                    h.placed === 0 && h.infeed === 0 ? "#f9fafb" : `${missColor(pct)}18`,
                  borderBottom:
                    h.placed > 0 || h.infeed > 0
                      ? `3px solid ${missColor(pct)}`
                      : "3px solid #e5e7eb",
                  color: h.placed === 0 && h.infeed === 0 ? "#d1d5db" : "#374151",
                }}
              >
                {String(hr).padStart(2, "0")}
              </button>
            );
          })}
        </div>
        <div className="flex gap-4 mt-2 text-[10px] text-gray-400">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-green-500 opacity-40" />
            weinig gemist
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-amber-500 opacity-40" />
            wat gemist
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-red-500 opacity-40" />
            veel gemist
          </span>
        </div>
      </div>

      {/* Minute Detail */}
      {selectedHour !== null && (
        <div className="mt-5 pt-4 border-t border-gray-100">
          <p className="text-[11px] text-gray-400 mb-3 uppercase tracking-wide">
            Per minuut: {String(selectedHour).padStart(2, "0")}:00 -{" "}
            {String(selectedHour).padStart(2, "0")}:59
          </p>
          {minutely.loading ? (
            <div className="flex justify-center py-6">
              <div className="h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : minutely.data && minutely.data.length > 0 ? (
            <MinuteDetail data={minutely.data} />
          ) : (
            <p className="text-xs text-gray-400 text-center py-3">
              Geen minuutdata beschikbaar
            </p>
          )}
        </div>
      )}
    </div>
  );
}
