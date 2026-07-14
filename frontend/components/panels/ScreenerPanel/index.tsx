"use client";

/**
 * ScreenerPanel — fundamental + technical stock screener.
 *
 * Features:
 *  - Built-in preset conditions (Value, Momentum, Oversold, Dividend, GARP)
 *  - Custom condition builder (field / operator / value)
 *  - Results table sorted by market cap
 *  - Quick-apply preset with one click
 */

import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import {
  runScreener,
  getScreenerPresets,
  type ScreenerCondition,
  type ScreenerPreset,
  type ScreenerRow,
} from "@/lib/api/screener";
import { formatPct, priceChangeClass } from "@/lib/formatters";

interface ScreenerPanelProps {
  panelId?: string;
}

const FIELDS = [
  { value: "pe_ratio",       label: "P/E Ratio" },
  { value: "pb_ratio",       label: "P/B Ratio" },
  { value: "ps_ratio",       label: "P/S Ratio" },
  { value: "market_cap",     label: "Market Cap ($M)" },
  { value: "dividend_yield", label: "Dividend Yield %" },
  { value: "revenue_growth", label: "Revenue Growth %" },
  { value: "eps_growth",     label: "EPS Growth %" },
  { value: "profit_margin",  label: "Profit Margin %" },
  { value: "rsi_14",         label: "RSI (14)" },
  { value: "change_pct_1d",  label: "1D Change %" },
  { value: "volume_ratio",   label: "Volume Ratio" },
  { value: "above_sma200",   label: "Above 200 SMA" },
  { value: "above_sma50",    label: "Above 50 SMA" },
  { value: "adx_14",         label: "ADX (14)" },
];

const OPS = [
  { value: "gt",  label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt",  label: "<" },
  { value: "lte", label: "≤" },
  { value: "eq",  label: "=" },
];

export function ScreenerPanel({ panelId = "screener" }: ScreenerPanelProps) {
  const [conditions, setConditions] = useState<ScreenerCondition[]>([
    { field: "rsi_14", op: "gt", value: 55 },
  ]);
  const [logic, setLogic] = useState<"AND" | "OR">("AND");
  const [results, setResults] = useState<ScreenerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [ran, setRan] = useState(false);
  const [presets, setPresets] = useState<ScreenerPreset[]>([]);
  const [presetsLoaded, setPresetsLoaded] = useState(false);

  const loadPresets = useCallback(async () => {
    if (presetsLoaded) return;
    try {
      const res = await getScreenerPresets();
      setPresets(res.presets);
      setPresetsLoaded(true);
    } catch {
      /* silently ignore */
    }
  }, [presetsLoaded]);

  const handleRun = useCallback(async () => {
    setLoading(true);
    try {
      const res = await runScreener({ conditions, logic, limit: 50 });
      setResults(res.results);
      setRan(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [conditions, logic]);

  const applyPreset = (preset: ScreenerPreset) => {
    setConditions(preset.conditions);
    setLogic(preset.logic);
  };

  const addCondition = () =>
    setConditions((prev) => [...prev, { field: "pe_ratio", op: "lt", value: 20 }]);

  const removeCondition = (idx: number) =>
    setConditions((prev) => prev.filter((_, i) => i !== idx));

  const updateCondition = (idx: number, field: string, val: string | number) =>
    setConditions((prev) =>
      prev.map((c, i) =>
        i === idx
          ? { ...c, [field]: field === "value" ? parseFloat(String(val)) || val : val }
          : c
      )
    );

  const toolbar = (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <button style={styles.ctrlBtn} onClick={loadPresets} title="Load presets">
        PRESETS
      </button>
      <select
        style={styles.logicSelect}
        value={logic}
        onChange={(e) => setLogic(e.target.value as "AND" | "OR")}
        aria-label="Logic operator"
      >
        <option value="AND">AND</option>
        <option value="OR">OR</option>
      </select>
      <button style={styles.runBtn} onClick={handleRun} disabled={loading}>
        {loading ? "SCANNING…" : "▶ SCAN"}
      </button>
    </div>
  );

  return (
    <Panel id={panelId} title="Screener" toolbar={toolbar}>
      {/* Preset chips */}
      {presets.length > 0 && (
        <div style={styles.presetRow}>
          {presets.map((p) => (
            <button key={p.id} style={styles.presetChip} onClick={() => applyPreset(p)} title={p.description}>
              {p.name}
            </button>
          ))}
        </div>
      )}

      {/* Condition builder */}
      <div style={styles.conditionSection}>
        {conditions.map((cond, idx) => (
          <div key={idx} style={styles.conditionRow}>
            <select
              style={styles.condSelect}
              value={cond.field}
              onChange={(e) => updateCondition(idx, "field", e.target.value)}
              aria-label="Filter field"
            >
              {FIELDS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
            <select
              style={{ ...styles.condSelect, width: 40 }}
              value={cond.op}
              onChange={(e) => updateCondition(idx, "op", e.target.value)}
              aria-label="Operator"
            >
              {OPS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <input
              type="number"
              style={styles.condInput}
              value={String(cond.value)}
              onChange={(e) => updateCondition(idx, "value", e.target.value)}
              aria-label="Filter value"
            />
            <button style={styles.removeBtn} onClick={() => removeCondition(idx)} aria-label="Remove condition">×</button>
          </div>
        ))}
        <button style={styles.addBtn} onClick={addCondition}>+ Add Filter</button>
      </div>

      {/* Results */}
      {ran && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.15 }}
        >
          <div style={styles.resultHeader}>
            {results.length} matches
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {["Symbol", "Name", "Sector", "Mkt Cap", "Price", "1D%", "P/E", "RSI"].map((h) => (
                    <th key={h} style={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {results.map((row) => (
                    <ScreenerRow key={row.symbol} row={row} />
                  ))}
                </AnimatePresence>
                {results.length === 0 && (
                  <tr>
                    <td colSpan={8} style={styles.empty}>No matches for current filters</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </Panel>
  );
}

function ScreenerRow({ row }: { row: ScreenerRow }) {
  const changeClass = priceChangeClass(row.change_pct_1d ?? 0);
  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.1 }}
      style={styles.tableRow}
    >
      <td style={{ ...styles.td, color: "var(--color-accent-blue)", fontWeight: 700 }}>{row.symbol}</td>
      <td style={{ ...styles.td, textAlign: "left", maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.name}</td>
      <td style={{ ...styles.td, color: "var(--color-text-muted)" }}>{row.sector}</td>
      <td style={styles.td}>{row.market_cap != null ? `$${(row.market_cap / 1000).toFixed(0)}B` : "—"}</td>
      <td style={styles.td}>{row.price != null ? row.price.toFixed(2) : "—"}</td>
      <td style={{ ...styles.td }} className={changeClass}>
        {row.change_pct_1d != null ? formatPct(row.change_pct_1d) : "—"}
      </td>
      <td style={styles.td}>{row.pe_ratio != null ? row.pe_ratio.toFixed(1) : "—"}</td>
      <td style={{
        ...styles.td,
        color: row.rsi_14 != null
          ? row.rsi_14 > 70 ? "var(--color-accent-red)"
          : row.rsi_14 < 30 ? "var(--color-accent-green)"
          : "var(--color-text-primary)"
          : "var(--color-text-muted)",
      }}>
        {row.rsi_14 != null ? row.rsi_14.toFixed(1) : "—"}
      </td>
    </motion.tr>
  );
}

const styles: Record<string, React.CSSProperties> = {
  presetRow: { display: "flex", flexWrap: "wrap" as const, gap: 4, padding: "4px 8px", borderBottom: "1px solid var(--color-bg-separator)" },
  presetChip: { padding: "2px 7px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-accent-amber)", cursor: "pointer" },
  conditionSection: { padding: "4px 8px", borderBottom: "1px solid var(--color-bg-separator)" },
  conditionRow: { display: "flex", gap: 4, alignItems: "center", marginBottom: 3 },
  condSelect: { background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 10, fontFamily: "var(--font-mono)", padding: "2px 4px" },
  condInput: { width: 60, background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 10, fontFamily: "var(--font-mono)", padding: "2px 4px", outline: "none" },
  removeBtn: { background: "none", border: "none", cursor: "pointer", color: "var(--color-text-muted)", fontSize: 13, padding: "0 2px" },
  addBtn: { marginTop: 3, padding: "2px 8px", background: "none", border: "1px dashed var(--color-bg-border)", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", cursor: "pointer" },
  logicSelect: { background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 9, fontFamily: "var(--font-mono)", padding: "2px 4px" },
  runBtn: { padding: "2px 8px", background: "var(--color-accent-green-bg)", border: "1px solid rgba(0,208,132,0.3)", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-accent-green)", cursor: "pointer", letterSpacing: "0.05em" },
  ctrlBtn: { padding: "2px 6px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", cursor: "pointer" },
  resultHeader: { padding: "3px 8px", fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", background: "var(--color-bg-elevated)", borderBottom: "1px solid var(--color-bg-separator)" },
  empty: { textAlign: "center" as const, padding: "12px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 10 },
  th: { padding: "3px 6px", fontSize: 8, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const, color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-bg-separator)", fontFamily: "var(--font-mono)", textAlign: "right" as const, whiteSpace: "nowrap" as const },
  td: { padding: "2px 6px", textAlign: "right" as const, fontFamily: "var(--font-mono)", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  tableRow: {},
};
