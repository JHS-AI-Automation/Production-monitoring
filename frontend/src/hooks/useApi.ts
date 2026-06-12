import { useEffect, useRef, useState } from "react";

// Vers-venster: binnen deze tijd wordt een gecached antwoord direct gebruikt zonder
// nieuwe fetch. Daarbuiten (tot STALE_MAX) tonen we het oude antwoord METEEN en
// verversen we op de achtergrond (stale-while-revalidate): de pagina voelt direct,
// ook als de server of VPN traag is.
const FRESH_TTL = 60_000;
const STALE_MAX = 30 * 60_000;
const FETCH_TIMEOUT = 15_000;

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const cache = new Map<string, CacheEntry<unknown>>();

function getEntry<T>(key: string): CacheEntry<T> | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > STALE_MAX) {
    cache.delete(key);
    return null;
  }
  return entry as CacheEntry<T>;
}

function setCache<T>(key: string, data: T, timestamp: number): void {
  cache.set(key, { data, timestamp });
}

export function clearCache(): void {
  cache.clear();
}

export interface ApiState {
  loading: boolean;
  error: string | null;
  stale: boolean;
  refreshFailed: boolean;
  lastUpdated: number | null;
  retry: () => void;
}

/** Bundel meerdere useApi-resultaten tot één loading/error/stale/retryAll voor een
 *  pagina. lastUpdated is de OUDSTE van de getoonde datasets (conservatief: de
 *  melding "gegevens van HH:MM" mag nooit verser lijken dan de data is). */
export function combineApi(...results: ApiState[]) {
  const timestamps = results
    .map((r) => r.lastUpdated)
    .filter((t): t is number => t !== null);
  return {
    loading: results.some((r) => r.loading),
    error: results.find((r) => r.error)?.error ?? null,
    stale: results.some((r) => r.stale),
    refreshFailed: results.some((r) => r.refreshFailed),
    lastUpdated: timestamps.length ? Math.min(...timestamps) : null,
    retryAll: () => results.forEach((r) => r.retry()),
  };
}

export function useApi<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>,
  deps: unknown[],
  cacheKey?: string,
): { data: T | null } & ApiState {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /** background=true: er staat al (oudere) data op het scherm; de pagina blijft
   *  bruikbaar en een mislukte refresh wordt alleen gemeld, niet als blokkende fout. */
  function fetchInto(background: boolean) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    if (!background) {
      setLoading(true);
      setError(null);
    }

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
        if (controller.signal.aborted) return;
        const now = Date.now();
        setData(result);
        setStale(false);
        setRefreshFailed(false);
        setLastUpdated(now);
        setError(null);
        if (cacheKey) setCache(cacheKey, result, now);
      })
      .catch((e) => {
        if (background) {
          // De oude data blijft staan; alleen melden dat verversen niet lukte.
          if (timedOut || !controller.signal.aborted) setRefreshFailed(true);
        } else if (timedOut) {
          setError("De server reageert traag of is onbereikbaar (time-out). Probeer het zo opnieuw.");
        } else if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Onbekende fout");
        }
      })
      .finally(() => {
        clearTimeout(timeout);
        if (!background && (timedOut || !controller.signal.aborted)) setLoading(false);
      });
  }

  function load() {
    const entry = cacheKey ? getEntry<T>(cacheKey) : null;
    if (entry) {
      // Direct tonen wat we hebben; dat is het hele punt van stale-while-revalidate.
      setData(entry.data);
      setLastUpdated(entry.timestamp);
      setLoading(false);
      setError(null);
      const fresh = Date.now() - entry.timestamp <= FRESH_TTL;
      setStale(!fresh);
      if (fresh) {
        setRefreshFailed(false);
        return;
      }
      fetchInto(true);
      return;
    }
    setStale(false);
    setRefreshFailed(false);
    setLastUpdated(null);
    fetchInto(false);
  }

  function retry() {
    // Geforceerd vers ophalen. Als er al data staat: als achtergrond-refresh,
    // zodat het scherm bruikbaar blijft in plaats van terug te vallen op een spinner.
    setRefreshFailed(false);
    fetchInto(data !== null);
  }

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, stale, refreshFailed, lastUpdated, retry };
}
