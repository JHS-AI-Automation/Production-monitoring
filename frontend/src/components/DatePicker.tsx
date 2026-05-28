interface DatePickerProps {
  value: string;
  onChange: (date: string) => void;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function DatePicker({ value, onChange }: DatePickerProps) {
  return (
    <input
      type="date"
      value={value}
      max={todayStr()}
      onChange={(e) => onChange(e.target.value)}
      className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dgs-500 focus:border-transparent"
    />
  );
}
