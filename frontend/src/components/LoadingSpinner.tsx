import { Loader2 } from "lucide-react";

export default function LoadingSpinner({ message = "Laden..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      <Loader2 size={28} className="animate-spin text-dgs-600" />
      <span className="text-sm text-gray-400">{message}</span>
    </div>
  );
}
