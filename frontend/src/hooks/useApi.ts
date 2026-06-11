import { useEffect, useRef, useState } from "react";

const CACHE_TTL = 60_000;
const FETCH_TIMEOUT = 15_000;

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const cache = new Map<string, CacheEntry<unknown>>();

function getCached<T>(key: string): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL) {
    cache.delete(key);
    return null;
  }
  return entry.data as T;
}

function setCache<T>(key: string, data: T): void {
  cache.set(key, { data, timestamp: Date.now() });
}

export function clearCache(): void {
  cache.clear();
}

interface ApiState {
  loading: boolean;
  error: string | null;
  retry: () => void;
}

/** Bundel meerdere useApi-resultaten tot één loading/error/retryAll voor een pagina.
 *  Vervangt de per-pagina herhaalde `a.loading || b.loading` / `a.error || b.error`
 *  / retry-bundeling. */
export function combineApi(...results: ApiState[]) {
  return {
    loading: results.some((r) => r.loading),
    error: results.find((r) => r.error)?.error ?? null,
    retryAll: () => results.forEach((r) => r.retry()),
  };
}

export function useApi<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>,
  deps: unknown[],
  cacheKey?: string,
): { data: T | null; loading: boolean; error: string | null; retry: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function load() {
    if (cacheKey) {
      const cached = getCached<T>(cacheKey);
      if (cached) {
        setData(cached);
        setLoading(false);
        setError(null);
        return;
      }
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    // Twee soorten abort: door ONZE timeout (echte fout, gebruiker moet het zien)
    // of door unmount/nieuwe load (stil negeren). timedOut maakt het onderscheid;
    // voorheen verdween de timeout in de stille tak en bleef de spinner eeuwig staan.
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, FETCH_TIMEOUT);

    fetcher(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          if (cacheKey) setCache(cacheKey, result);
        }
      })
      .catch((e) => {
        if (timedOut) {
          setError("Verbinding time-out. Controleer of de backend draait.");
        } else if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Onbekende fout");
        }
      })
      .finally(() => {
        clearTimeout(timeout);
        if (timedOut || !controller.signal.aborted) setLoading(false);
      });
  }

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, retry: load };
}
