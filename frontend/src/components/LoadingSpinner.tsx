import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

// Na deze wachttijd leggen we uit WAAROM het duurt: een kale spinner van 10+
// seconden voelt als "kapot", dezelfde spinner met uitleg voelt als "druk".
const SLOW_AFTER_MS = 8_000;

export default function LoadingSpinner({ message = "Laden..." }: { message?: string }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      <Loader2 size={28} className="animate-spin text-dgs-600" />
      <span className="text-sm text-gray-400">{message}</span>
      {slow && (
        <span className="text-sm text-gray-500 max-w-sm text-center">
          Dit duurt langer dan normaal, waarschijnlijk is het druk op de server.
          We blijven het proberen.
        </span>
      )}
    </div>
  );
}
