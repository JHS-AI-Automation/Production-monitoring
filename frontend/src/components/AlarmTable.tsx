import type { TopAlarm } from "../api";

const SEVERITY_STYLES: Record<string, string> = {
  Error: "bg-red-100 text-red-700",
  Warning: "bg-yellow-100 text-yellow-700",
  Info: "bg-blue-100 text-blue-700",
};

interface AlarmTableProps {
  alarms: TopAlarm[];
  title?: string;
}

export default function AlarmTable({ alarms, title = "Top alarmen" }: AlarmTableProps) {
  if (alarms.length === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        Geen alarmen gevonden voor deze datum.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {title && (
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">{title}</h2>
        </div>
      )}
      <table className="w-full">
        <thead>
          <tr className="bg-dgs-900 text-white text-xs uppercase tracking-wide">
            <th className="text-left px-5 py-3 font-semibold">Alarmbericht</th>
            <th className="text-center px-4 py-3 font-semibold">Klasse</th>
            <th className="text-center px-4 py-3 font-semibold">Geactiveerd</th>
            <th className="text-center px-4 py-3 font-semibold">Verholpen</th>
          </tr>
        </thead>
        <tbody>
          {alarms.map((alarm, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-gray-50/50" : "bg-white"}>
              <td className="px-5 py-3 text-sm text-gray-700">
                {alarm.alarmmessage}
              </td>
              <td className="px-4 py-3 text-center">
                <span
                  className={`inline-block px-2.5 py-0.5 rounded text-xs font-semibold ${
                    SEVERITY_STYLES[alarm.severityclass] ?? "bg-gray-100 text-gray-600"
                  }`}
                >
                  {alarm.severityclass}
                </span>
              </td>
              <td className="px-4 py-3 text-center text-sm font-semibold text-gray-700">
                {alarm.trigger_count}x
              </td>
              <td className="px-4 py-3 text-center text-sm text-gray-500">
                {alarm.resolve_count}x
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
