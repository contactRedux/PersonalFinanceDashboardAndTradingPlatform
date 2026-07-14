"use client";

/**
 * DarkPoolPanel — unusual options activity and dark pool flow.
 *
 * Displays large premium options transactions that may indicate
 * institutional positioning ("smart money" flow).
 *
 * Features:
 *  - Unusual options activity feed (from /options/unusual-activity)
 *  - Sortable by premium, OI, volume
 *  - Bullish / Bearish / Mixed directional bias badge
 *  - Demo data shown when API key not configured
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import { getUnusualActivity, type UnusualActivity } from "@/lib/api/options";
import { formatCompact } from "@/lib/formatters";

interface DarkPoolPanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

// Demo unusual activity — shown when API returns empty
const DEMO_ACTIVITY: UnusualActivity[] = [
  { symbol: "NVDA", contract_type: "call", strike: 550, expiry: "2025-02-21", premium: 4_200_000, volume: 8_420, open_interest: 12_500, timestamp: new Date().toISOString() },
  { symbol: "SPY",  contract_type: "put",  strike: 490, expiry: "2025-02-07", premium: 3_800_000, volume: 15_200, open_interest: 48_000, timestamp: new Date().toISOString() },
  { symbol: "AAPL", contract_type: "call", strike: 210, expiry: "2025-03-21", premium: 2_150_000, volume: 6_800, open_interest: 9_200, timestamp: new Date().toISOString() },
  { symbol: "QQQ",  contract_type: "put",  strike: 400, expiry: "2025-02-14", premium: 1_900_000, volume: 9_100, open_interest: 31_000, timestamp: new Date().toISOString() },
  { symbol: "TSLA", contract_type: "call", strike: 280, expiry: "2025-02-28", premium: 1_650_000, volume: 4_200, open_interest: 7_800, timestamp: new Date().toISOString() },
  { symbol: "META", contract_type: "call", strike: 600, expiry: "2025-03-21", premium: 1_420_000, volume: 3_800, open_interest: 5_400, timestamp: new Date().toISOString() },
  { symbol: "AMD",  contract_type: "put",  strike: 140, expiry: "2025-02-07", premium: 1_100_000, volume: 5_600, open_interest: 18_200, timestamp: new Date().toISOString() },
  { symbol: "GLD",  contract_type: "call", strike: 225, expiry: "2025-04-17", premium: 980_000,   volume: 2_900, open_interest: 4_100, timestamp: new Date().toISOString() },
];

type SortKey = "premium" | "volume" | "open_interest";

export function DarkPoolPanel({ panelId = "darkpool", defaultSymbol }: DarkPoolPanelProps) {
  const [activity, setActivity] = useState<UnusualActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortKey>("premium");
  const [filterSymbol, setFilterSymbol] = useState(defaultSymbol ?? "");
  const [isDemo, setIsDemo] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await getUnusualActivity(filterSymbol || undefined, 500_000);
      if (res.activity.length > 0) {
        setActivity(res.activity);
        setIsDemo(false);
      } else {
        setActivity(DEMO_ACTIVITY);
        setIsDemo(true);
      }
    } catch {
      setActivity(DEMO_ACTIVITY);
      setIsDemo(true);
    } finally {
      setLoading(false);
    }
  }, [filterSymbol]);

  useEffect(() => { void load(); }, [load]);

  const sorted = [...activity].sort((a, b) => b[sortBy] - a[sortBy]);

  // Compute bullish / bearish bias
  const callPremium = activity.filter((a) => a.contract_type === "call").reduce((s, a) => s + a.premium, 0);
  const putPremium  = activity.filter((a) => a.contract_type === "put").reduce((s, a) => s + a.premium, 0);
  const biasRatio = callPremium / (callPremium + putPremium + 1);
  const bias = biasRatio > 0.6 ? "BULLISH" : biasRatio < 0.4 ? "BEARISH" : "MIXED";
  const biasColor = bias === "BULLISH" ? "var(--color-accent-green)" : bias === "BEARISH" ? "var(--color-accent-red)" : "var(--color-accent-amber)";

  const toolbar = (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <input
        type="text"
        value={filterSymbol}
        onChange={(e) => setFilterSymbol(e.target.value.toUpperCase())}
        placeholder="Filter symbol…"
        style={styles.filterInput}
        aria-label="Filter symbol"
        maxLength={6}
      />
      <select
        value={sortBy}
        onChange={(e) => setSortBy(e.target.value as SortKey)}
        style={styles.sortSelect}
        aria-label="Sort by"
      >
        <option value="premium">PREMIUM</option>
        <option value="volume">VOLUME</option>
        <option value="open_interest">OI</option>
      </select>
    </div>
  );

  return (
    <Panel id={panelId} title="Unusual Options Activity" toolbar={toolbar}>
      {/* Flow bias summary */}
      <div style={styles.biasRow}>
        <span style={styles.biasLabel}>FLOW BIAS</span>
        <span style={{ ...styles.biasValue, color: biasColor }}>{bias}</span>
        <span style={styles.biasSub}>
          Calls: ${formatCompact(callPremium)} | Puts: ${formatCompact(putPremium)}
        </span>
        {isDemo && <span style={styles.demoTag}>DEMO</span>}
      </div>

      {loading && <div style={styles.stateMsg}>Loading unusual activity…</div>}

      {!loading && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.12 }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["Sym", "Type", "Strike", "Expiry", "Premium", "Vol", "OI"].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, idx) => {
                const isCall = row.contract_type === "call";
                const sideColor = isCall ? "var(--color-accent-green)" : "var(--color-accent-red)";
                return (
                  <tr key={idx} style={styles.tableRow}>
                    <td style={{ ...styles.td, color: "var(--color-accent-blue)", fontWeight: 700, textAlign: "left" }}>{row.symbol}</td>
                    <td style={{ ...styles.td, color: sideColor, fontWeight: 700 }}>{isCall ? "CALL" : "PUT"}</td>
                    <td style={styles.td}>${row.strike}</td>
                    <td style={{ ...styles.td, color: "var(--color-text-muted)" }}>{row.expiry}</td>
                    <td style={{ ...styles.td, color: "var(--color-accent-amber)", fontWeight: 700 }}>
                      ${formatCompact(row.premium)}
                    </td>
                    <td style={styles.td}>{formatCompact(row.volume)}</td>
                    <td style={{ ...styles.td, color: "var(--color-text-muted)" }}>{formatCompact(row.open_interest)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {isDemo && (
            <div style={styles.demoNote}>
              Demo data — configure Unusual Whales or Polygon Options API for live flow.
            </div>
          )}
        </motion.div>
      )}
    </Panel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  stateMsg:    { textAlign: "center" as const, padding: "12px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  biasRow:     { display: "flex", alignItems: "center", gap: 8, padding: "4px 10px", borderBottom: "1px solid var(--color-bg-separator)", background: "var(--color-bg-elevated)" },
  biasLabel:   { fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em" },
  biasValue:   { fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 700 },
  biasSub:     { fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", flex: 1 },
  demoTag:     { padding: "1px 4px", background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.3)", borderRadius: 3, fontSize: 8, color: "var(--color-accent-amber)", fontFamily: "var(--font-mono)" },
  filterInput: { width: 80, background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 9, fontFamily: "var(--font-mono)", padding: "2px 5px", outline: "none", textTransform: "uppercase" as const },
  sortSelect:  { background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 9, fontFamily: "var(--font-mono)", padding: "2px 4px" },
  table:       { width: "100%", borderCollapse: "collapse", fontSize: 10 },
  th:          { padding: "3px 6px", fontSize: 8, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const, color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-bg-separator)", fontFamily: "var(--font-mono)", textAlign: "right" as const, whiteSpace: "nowrap" as const },
  td:          { padding: "2px 6px", textAlign: "right" as const, fontFamily: "var(--font-mono)", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  tableRow:    {},
  demoNote:    { padding: "5px 10px", fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", borderTop: "1px solid var(--color-bg-separator)" },
};
