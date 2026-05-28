import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

export default function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-start gap-3">
      <AlertTriangle size={20} className="text-red-500 shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm font-medium text-red-800">
          Kan gegevens niet laden
        </p>
        <p className="text-sm text-red-600 mt-1">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-300 text-sm font-medium text-red-700 hover:bg-red-100 transition-colors"
        >
          <RefreshCw size={14} />
          Opnieuw
        </button>
      )}
    </div>
  );
}
