"use client";

/**
 * OptionsChainPanel — full options chain with Greeks.
 *
 * Features:
 *  - Expiry date selector (fetches available expirations)
 *  - Side-by-side Calls / Puts table
 *  - Delta, Gamma, Theta, Vega, Rho, Theoretical Price columns
 *  - Moneyness highlighting (ITM rows tinted)
 *  - Underlying price display
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import {
  getOptionsChain,
  getExpirations,
  type OptionContract,
  type OptionsChainResponse,
} from "@/lib/api/options";

interface OptionsChainPanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

export function OptionsChainPanel({
  panelId = "options",
  defaultSymbol = "AAPL",
}: OptionsChainPanelProps) {
  const [symbol, setSymbol] = useState(defaultSymbol.toUpperCase());
  const [inputValue, setInputValue] = useState(defaultSymbol.toUpperCase());
  const [expirations, setExpirations] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState<string>("");
  const [chain, setChain] = useState<OptionsChainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load expirations when symbol changes
  const loadExpirations = useCallback(async (sym: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getExpirations(sym);
      setExpirations(res.expirations);
      const first = res.expirations[0] ?? "";
      setSelectedExpiry(first);
    } catch {
      setError("Failed to load expirations");
      setExpirations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load chain when symbol or expiry changes
  const loadChain = useCallback(async (sym: string, expiry: string) => {
    if (!expiry) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getOptionsChain(sym, expiry);
      setChain(res);
    } catch {
      setError("Failed to load options chain");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadExpirations(symbol);
  }, [symbol, loadExpirations]);

  useEffect(() => {
    if (selectedExpiry) {
      void loadChain(symbol, selectedExpiry);
    }
  }, [symbol, selectedExpiry, loadChain]);

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim().toUpperCase();
    if (trimmed && trimmed !== symbol) {
      setSymbol(trimmed);
    }
  };

  const calls = chain?.chain.filter((c) => c.contract_type === "call") ?? [];
  const puts = chain?.chain.filter((c) => c.contract_type === "put") ?? [];

  // Build unified strike list
  const strikes = Array.from(
    new Set([...calls.map((c) => c.strike), ...puts.map((p) => p.strike)])
  ).sort((a, b) => a - b);

  const callsByStrike = new Map(calls.map((c) => [c.strike, c]));
  const putsByStrike = new Map(puts.map((p) => [p.strike, p]));
  const underlyingPrice = chain?.underlying_price ?? null;

  const toolbar = (
    <form onSubmit={handleSymbolSubmit} style={{ display: "flex", gap: 4 }}>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value.toUpperCase())}
        style={styles.symbolInput}
        aria-label="Options symbol"
        spellCheck={false}
        maxLength={10}
      />
      <button type="submit" style={styles.goBtn}>GO</button>
    </form>
  );

  return (
    <Panel id={panelId} title="Options Chain" toolbar={toolbar}>
      {/* Expiry selector + underlying price */}
      <div style={styles.topBar}>
        <div style={styles.expiryRow}>
          <span style={styles.label}>Expiry:</span>
          {expirations.length > 0 ? (
            <select
              value={selectedExpiry}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              style={styles.select}
              aria-label="Expiration date"
            >
              {expirations.map((exp) => (
                <option key={exp} value={exp}>
                  {exp}
                </option>
              ))}
            </select>
          ) : (
            <span style={styles.noData}>—</span>
          )}
        </div>

        {underlyingPrice != null && (
          <div style={styles.underlyingPrice}>
            <span style={styles.label}>{symbol}</span>
            <span style={styles.priceVal}>${underlyingPrice.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* State */}
      {loading && <div style={styles.stateMsg}>Loading options chain…</div>}
      {error && (
        <div style={{ ...styles.stateMsg, color: "var(--color-accent-red)" }}>
          {error}
        </div>
      )}
      {!loading && !error && expirations.length === 0 && (
        <div style={{ ...styles.stateMsg, fontSize: 10 }}>
          No options data — configure Polygon.io API key to enable.
        </div>
      )}

      {/* Chain table */}
      {!loading && strikes.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.15 }}
          style={{ overflowX: "auto" }}
        >
          <table style={styles.table}>
            <thead>
              <tr>
                <th colSpan={5} style={{ ...styles.th, textAlign: "center", color: "var(--color-accent-green)" }}>
                  CALLS
                </th>
                <th style={{ ...styles.th, textAlign: "center", background: "var(--color-bg-overlay)" }}>
                  STRIKE
                </th>
                <th colSpan={5} style={{ ...styles.th, textAlign: "center", color: "var(--color-accent-red)" }}>
                  PUTS
                </th>
              </tr>
              <tr>
                {["Δ Delta", "Θ Theta", "Vega", "Theo", "IV"].map((h) => (
                  <th key={`c-${h}`} style={styles.th}>{h}</th>
                ))}
                <th style={{ ...styles.th, background: "var(--color-bg-overlay)", textAlign: "center" }}>—</th>
                {["Δ Delta", "Θ Theta", "Vega", "Theo", "IV"].map((h) => (
                  <th key={`p-${h}`} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {strikes.map((strike) => {
                const call = callsByStrike.get(strike);
                const put = putsByStrike.get(strike);
                const isATM =
                  underlyingPrice != null &&
                  Math.abs(strike - underlyingPrice) / underlyingPrice < 0.01;
                const isITMCall =
                  underlyingPrice != null && strike < underlyingPrice;
                const isITMPut =
                  underlyingPrice != null && strike > underlyingPrice;

                return (
                  <tr
                    key={strike}
                    style={{
                      background: isATM
                        ? "rgba(14,165,233,0.06)"
                        : "transparent",
                      borderBottom: "1px solid rgba(255,255,255,0.03)",
                    }}
                  >
                    <GreeksCell contract={call} field="delta" itm={isITMCall} />
                    <GreeksCell contract={call} field="theta" itm={isITMCall} />
                    <GreeksCell contract={call} field="vega" itm={isITMCall} />
                    <GreeksCell contract={call} field="theoretical_price" itm={isITMCall} />
                    <td style={styles.td}>—</td>

                    {/* Strike */}
                    <td
                      style={{
                        ...styles.td,
                        textAlign: "center",
                        fontWeight: 700,
                        background: "var(--color-bg-overlay)",
                        color: isATM
                          ? "var(--color-accent-blue)"
                          : "var(--color-text-primary)",
                        fontSize: 11,
                      }}
                    >
                      {strike.toFixed(0)}
                    </td>

                    <GreeksCell contract={put} field="delta" itm={isITMPut} putSide />
                    <GreeksCell contract={put} field="theta" itm={isITMPut} putSide />
                    <GreeksCell contract={put} field="vega" itm={isITMPut} putSide />
                    <GreeksCell contract={put} field="theoretical_price" itm={isITMPut} putSide />
                    <td style={styles.td}>—</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </motion.div>
      )}
    </Panel>
  );
}

// ─── Greeks cell ──────────────────────────────────────────────────────────────
function GreeksCell({
  contract,
  field,
  itm,
  putSide = false,
}: {
  contract: OptionContract | undefined;
  field: keyof OptionContract["greeks"];
  itm: boolean;
  putSide?: boolean;
}) {
  const value = contract?.greeks[field];
  const itmBg = itm
    ? putSide
      ? "rgba(239,68,68,0.05)"
      : "rgba(0,208,132,0.05)"
    : "transparent";

  return (
    <td
      style={{
        ...styles.td,
        background: itmBg,
        color:
          field === "delta"
            ? putSide
              ? "var(--color-accent-red)"
              : "var(--color-accent-green)"
            : "var(--color-text-primary)",
      }}
    >
      {value != null ? value.toFixed(4) : "—"}
    </td>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  topBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "4px 8px",
    borderBottom: "1px solid var(--color-bg-separator)",
  },
  expiryRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  label: {
    fontSize: 10,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  select: {
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    color: "var(--color-text-primary)",
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    padding: "2px 4px",
  },
  noData: {
    fontSize: 10,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  underlyingPrice: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  priceVal: {
    fontFamily: "var(--font-mono)",
    fontSize: 13,
    fontWeight: 700,
    color: "var(--color-accent-blue)",
  },
  symbolInput: {
    width: 72,
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    color: "var(--color-text-primary)",
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    padding: "2px 6px",
    textTransform: "uppercase" as const,
    outline: "none",
  },
  goBtn: {
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    color: "var(--color-accent-blue)",
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    padding: "2px 6px",
    cursor: "pointer",
    letterSpacing: "0.05em",
  },
  stateMsg: {
    textAlign: "center" as const,
    padding: "16px",
    fontSize: 11,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 10,
  },
  th: {
    padding: "4px 6px",
    fontSize: 8,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "var(--color-text-muted)",
    borderBottom: "1px solid var(--color-bg-separator)",
    fontFamily: "var(--font-mono)",
    textAlign: "right" as const,
    whiteSpace: "nowrap" as const,
  },
  td: {
    padding: "2px 6px",
    textAlign: "right" as const,
    fontFamily: "var(--font-mono)",
    fontSize: 10,
  },
};
