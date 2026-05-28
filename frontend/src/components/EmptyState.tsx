import { Inbox } from "lucide-react";

interface EmptyStateProps {
  message?: string;
  className?: string;
}

export default function EmptyState({
  message = "Geen data beschikbaar voor deze datum",
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 text-gray-400 ${className}`}>
      <Inbox size={36} className="mb-3 text-gray-300" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
