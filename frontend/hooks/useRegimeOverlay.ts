/**
 * useRegimeOverlay — fetches HMM regime for a symbol.
 *
 * Returns { regime, probabilities, loading }
 * Gracefully handles 404 (no model trained) and network errors by returning regime: null.
 */
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api/client";

export interface RegimeResult {
  regime: "bull" | "bear" | "sideways" | null;
  probabilities: Record<string, number> | null;
  loading: boolean;
}

export function useRegimeOverlay(symbol: string): RegimeResult {
  const [regime, setRegime] = useState<"bull" | "bear" | "sideways" | null>(null);
  const [probabilities, setProbabilities] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);

    apiRequest<{ regime: string; probabilities: Record<string, number> }>(
      `/ml/hmm/regime?ticker=${encodeURIComponent(symbol)}`
    )
      .then((data) => {
        if (cancelled) return;
        setRegime(data.regime as "bull" | "bear" | "sideways");
        setProbabilities(data.probabilities);
      })
      .catch(() => {
        if (cancelled) return;
        // 404 = no model trained; any error = no overlay
        setRegime(null);
        setProbabilities(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [symbol]);

  return { regime, probabilities, loading };
}
