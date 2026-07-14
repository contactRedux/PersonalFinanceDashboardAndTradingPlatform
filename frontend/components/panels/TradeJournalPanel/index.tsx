"use client";

/**
 * TradeJournalPanel — AI-generated trade journal entries.
 *
 * Shows: symbol, side, quantity, entry_price, sentiment score chip (green/red),
 * and the AI analysis text produced by GPT-4o.
 *
 * Fetches GET /api/v1/journal on mount. Falls back gracefully when the
 * backend or MongoDB is unavailable.
 */

import React, { useEffect, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { apiRequest } from "@/lib/api/client";

interface JournalEntry {
  order_id: string;
  user_id: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number | null;
  sentiment_score: number | null;
  technical_context: Record<string, unknown>;
  ai_analysis: string;
  created_at: string;
}

interface JournalResponse {
  entries: JournalEntry[];
  count: number;
}

interface TradeJournalPanelProps {
  panelId?: string;
}

export function TradeJournalPanel({ panelId = "journal" }: TradeJournalPanelProps) {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const resp = await apiRequest<JournalResponse>("/journal");
      setEntries(resp.entries ?? []);
    } catch {
      /* silently degrade — backend may not have MongoDB */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Panel id={panelId} title="Trade Journal">
      {loading && <div style={styles.stateMsg}>Loading…</div>}

      {!loading && entries.length === 0 && (
        <div style={styles.stateMsg}>No journal entries yet</div>
      )}

      {!loading && entries.length > 0 && (
        <div style={styles.list}>
          {entries.map((entry) => (
            <JournalEntryCard key={entry.order_id} entry={entry} />
          ))}
        </div>
      )}
    </Panel>
  );
}

// ─── Entry card ───────────────────────────────────────────────────────────────

function JournalEntryCard({ entry }: { entry: JournalEntry }) {
  const sideColor =
    entry.side === "buy"
      ? "var(--color-accent-green)"
      : "var(--color-accent-red)";

  const sentimentColor =
    entry.sentiment_score === null
      ? "var(--color-text-muted)"
      : entry.sentiment_score >= 0
        ? "var(--color-accent-green)"
        : "var(--color-accent-red)";

  const sentimentBg =
    entry.sentiment_score === null
      ? "transparent"
      : entry.sentiment_score >= 0
        ? "rgba(0,208,132,0.10)"
        : "rgba(239,68,68,0.10)";

  const sentimentBorder =
    entry.sentiment_score === null
      ? "transparent"
      : entry.sentiment_score >= 0
        ? "rgba(0,208,132,0.30)"
        : "rgba(239,68,68,0.30)";

  return (
    <div style={styles.card}>
      {/* Header row */}
      <div style={styles.cardHeader}>
        <span style={styles.symbol}>{entry.symbol}</span>
        <span style={{ ...styles.side, color: sideColor }}>
          {entry.side.toUpperCase()}
        </span>
        <span style={styles.qty}>{entry.quantity} @ {entry.entry_price?.toFixed(2) ?? "—"}</span>

        {/* Sentiment chip */}
        {entry.sentiment_score !== null && (
          <span
            style={{
              ...styles.sentimentChip,
              color: sentimentColor,
              background: sentimentBg,
              borderColor: sentimentBorder,
            }}
          >
            {entry.sentiment_score >= 0 ? "+" : ""}
            {entry.sentiment_score.toFixed(2)}
          </span>
        )}
      </div>

      {/* AI analysis */}
      <div style={styles.analysis}>{entry.ai_analysis}</div>

      {/* Timestamp */}
      <div style={styles.timestamp}>{formatRelativeTime(entry.created_at)}</div>
    </div>
  );
}

function formatRelativeTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    const diffMs = Date.now() - dt.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${Math.floor(diffHrs / 24)}d ago`;
  } catch {
    return "";
  }
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  stateMsg: {
    textAlign: "center",
    padding: "16px",
    fontSize: 11,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  list: {
    display: "flex",
    flexDirection: "column",
    overflow: "auto",
  },
  card: {
    padding: "8px 10px",
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  symbol: {
    fontSize: 12,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    color: "var(--color-accent-blue)",
    letterSpacing: "0.04em",
  },
  side: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    letterSpacing: "0.06em",
  },
  qty: {
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
  },
  sentimentChip: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    letterSpacing: "0.04em",
    padding: "1px 5px",
    borderRadius: 2,
    border: "1px solid",
  },
  analysis: {
    fontSize: 11,
    fontFamily: "var(--font-sans)",
    color: "var(--color-text-primary)",
    lineHeight: 1.5,
  },
  timestamp: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-muted)",
  },
};
