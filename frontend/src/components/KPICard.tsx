interface KPICardProps {
  label: string;
  value: number | string;
  subtitle?: string;
  color: "green" | "red" | "blue" | "gray";
}

const BORDER_COLORS = {
  green: "border-t-green-500",
  red: "border-t-red-500",
  blue: "border-t-blue-500",
  gray: "border-t-gray-300",
};

export default function KPICard({ label, value, subtitle, color }: KPICardProps) {
  return (
    <div
      className={`bg-white rounded-xl border border-gray-200 border-t-4 ${BORDER_COLORS[color]} p-5`}
    >
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </p>
      <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
      {subtitle && (
        <p className="text-xs text-gray-400 mt-1.5">{subtitle}</p>
      )}
    </div>
  );
}
