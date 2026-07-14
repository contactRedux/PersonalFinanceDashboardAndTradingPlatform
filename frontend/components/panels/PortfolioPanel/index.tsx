"use client";

/**
 * PortfolioPanel — live portfolio overview.
 *
 * Shows: equity, cash, unrealized/realized P&L, day P&L, buying power,
 * drawdown meter, and open positions table with live price coloring.
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import {
  getPortfolio,
  getPositions,
  type PortfolioSummary,
  type PositionData,
} from "@/lib/api/portfolio";
import { formatCurrency, formatPct, priceChangeClass } from "@/lib/formatters";
import { useOrdersStore } from "@/store/ordersStore";

interface PortfolioPanelProps {
  panelId?: string;
}

type Tab = "overview" | "positions";

export function PortfolioPanel({ panelId = "portfolio" }: PortfolioPanelProps) {
  const [tab, setTab] = useState<Tab>("overview");
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<PositionData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [p, pos] = await Promise.all([getPortfolio(), getPositions()]);
      setPortfolio(p);
      setPositions(pos.positions);
      setError(null);
    } catch {
      setError("Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 30_000);
    return () => clearInterval(interval);
  }, [load]);

  // Refresh positions when an order fill event arrives from OrderEntryPanel
  const lastFill = useOrdersStore((s) => s.lastFill);
  const clearLastFill = useOrdersStore((s) => s.clearLastFill);
  useEffect(() => {
    if (lastFill) {
      void load();
      clearLastFill();
    }
  }, [lastFill, load, clearLastFill]);

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!e.target.files) return;
    e.target.value = "";
    if (!file) return;
    setImportMsg(null);
    try {
      const { getAccessToken } = await import("@/lib/api/client");
      const token = getAccessToken();
      const fd = new FormData();
      fd.append("file", file);
      const resp = await fetch("/api/v1/portfolio/import", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (resp.ok) {
        const data = (await resp.json()) as { imported: number };
        setImportMsg(`Imported ${data.imported} position${data.imported !== 1 ? "s" : ""}`);
        void load();
      } else {
        const err = (await resp.json()) as { detail?: string | { message?: string } };
        const msg =
          typeof err.detail === "string"
            ? err.detail
            : err.detail?.message ?? "Import failed";
        setImportMsg(`Error: ${msg}`);
      }
    } catch {
      setImportMsg("Error: network error");
    }
  };

  const toolbar = (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      {(["overview", "positions"] as Tab[]).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
          onClick={() => setTab(t)}
        >
          {t.toUpperCase()}
        </button>
      ))}
      <button
        style={styles.importBtn}
        onClick={() => fileInputRef.current?.click()}
        title="Import CSV positions"
        aria-label="Import CSV"
      >
        Import CSV
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        style={{ display: "none" }}
        aria-hidden="true"
        onChange={handleImportFile}
      />
    </div>
  );

  return (
    <Panel id={panelId} title="Portfolio" toolbar={toolbar}>
      {importMsg && (
        <div
          style={{
            ...styles.stateMsg,
            color: importMsg.startsWith("Error")
              ? "var(--color-accent-red)"
              : "var(--color-accent-green)",
          }}
        >
          {importMsg}
        </div>
      )}
      {loading && <div style={styles.stateMsg}>Loading…</div>}
      {error && <div style={{ ...styles.stateMsg, color: "var(--color-accent-red)" }}>{error}</div>}

      {!loading && !error && (
        <AnimatePresence mode="wait">
          {tab === "overview" && portfolio && (
            <motion.div
              key="overview"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
            >
              <PortfolioOverview portfolio={portfolio} />
            </motion.div>
          )}
          {tab === "positions" && (
            <motion.div
              key="positions"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
            >
              <PositionsTable positions={positions} />
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </Panel>
  );
}

// ─── Overview ─────────────────────────────────────────────────────────────────
function PortfolioOverview({ portfolio }: { portfolio: PortfolioSummary }) {
  const dayPnlClass = priceChangeClass(portfolio.day_pnl);
  const totalPnlClass = priceChangeClass(
    portfolio.unrealized_pnl + portfolio.realized_pnl
  );

  // Drawdown meter: 0-30% bad, treat >20% as full red
  const drawdownPct = portfolio.unrealized_pnl < 0
    ? Math.abs(portfolio.unrealized_pnl / portfolio.equity) * 100
    : 0;
  const drawdownWidth = Math.min(100, (drawdownPct / 20) * 100);

  const rows: { label: string; value: string; cls?: string }[] = [
    {
      label: "Total Equity",
      value: formatCurrency(portfolio.equity),
    },
    {
      label: "Cash",
      value: formatCurrency(portfolio.cash),
    },
    {
      label: "Buying Power",
      value: formatCurrency(portfolio.buying_power),
    },
    {
      label: "Unrealized P&L",
      value: formatCurrency(portfolio.unrealized_pnl),
      cls: priceChangeClass(portfolio.unrealized_pnl),
    },
    {
      label: "Realized P&L",
      value: formatCurrency(portfolio.realized_pnl),
      cls: priceChangeClass(portfolio.realized_pnl),
    },
    {
      label: "Day P&L",
      value: `${formatCurrency(portfolio.day_pnl)} (${formatPct(portfolio.day_pnl_pct)})`,
      cls: dayPnlClass,
    },
    {
      label: "Total P&L",
      value: formatCurrency(portfolio.unrealized_pnl + portfolio.realized_pnl),
      cls: totalPnlClass,
    },
    {
      label: "Margin Used",
      value: formatCurrency(portfolio.margin_used),
    },
  ];

  return (
    <div style={{ padding: "4px 0" }}>
      {rows.map(({ label, value, cls }) => (
        <div key={label} style={styles.row}>
          <span style={styles.rowLabel}>{label}</span>
          <span
            style={styles.rowValue}
            className={cls}
          >
            {value}
          </span>
        </div>
      ))}

      {/* Drawdown meter */}
      <div style={{ padding: "6px 10px 8px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
          <span style={styles.rowLabel}>Drawdown Exposure</span>
          <span style={{ ...styles.rowValue, color: drawdownPct > 5 ? "var(--color-accent-red)" : "var(--color-text-muted)" }}>
            {drawdownPct.toFixed(2)}%
          </span>
        </div>
        <div style={styles.meterTrack}>
          <motion.div
            style={{
              height: "100%",
              width: `${drawdownWidth}%`,
              background: drawdownPct > 10
                ? "var(--color-accent-red)"
                : drawdownPct > 5
                  ? "var(--color-accent-amber)"
                  : "var(--color-accent-green)",
              borderRadius: 2,
            }}
            initial={{ width: 0 }}
            animate={{ width: `${drawdownWidth}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Positions table ───────────────────────────────────────────────────────────
function PositionsTable({ positions }: { positions: PositionData[] }) {
  if (positions.length === 0) {
    return (
      <div style={styles.stateMsg}>No open positions</div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={styles.table}>
        <thead>
          <tr>
            {["Symbol", "Side", "Qty", "Entry", "Current", "Mkt Val", "P&L", "P&L%", "SL", "TP"].map(
              (h) => (
                <th key={h} style={styles.th}>
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody>
          <AnimatePresence>
            {positions.map((pos) => (
              <PositionRow key={pos.symbol} pos={pos} />
            ))}
          </AnimatePresence>
        </tbody>
      </table>
    </div>
  );
}

function PositionRow({ pos }: { pos: PositionData }) {
  const pnlClass = priceChangeClass(pos.unrealized_pnl);
  const sideColor =
    pos.side === "long"
      ? "var(--color-accent-green)"
      : "var(--color-accent-red)";

  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      style={styles.tableRow}
    >
      <td style={{ ...styles.td, textAlign: "left", color: "var(--color-accent-blue)", fontWeight: 700 }}>
        {pos.symbol}
      </td>
      <td style={{ ...styles.td, color: sideColor, textTransform: "uppercase", fontSize: 9 }}>
        {pos.side}
      </td>
      <td style={styles.td}>{pos.quantity}</td>
      <td style={styles.td}>{pos.avg_entry_price.toFixed(2)}</td>
      <td style={styles.td}>
        <motion.span
          key={pos.current_price}
          initial={{ color: pnlClass === "price-up" ? "#00d084" : "#ef4444" }}
          animate={{ color: "var(--color-text-primary)" }}
          transition={{ duration: 0.6 }}
        >
          {pos.current_price.toFixed(2)}
        </motion.span>
      </td>
      <td style={styles.td}>{formatCurrency(pos.market_value)}</td>
      <td style={{ ...styles.td }} className={pnlClass}>
        {formatCurrency(pos.unrealized_pnl)}
      </td>
      <td style={{ ...styles.td }} className={pnlClass}>
        {pos.unrealized_pnl_pct >= 0 ? "+" : ""}
        {pos.unrealized_pnl_pct.toFixed(2)}%
      </td>
      <td style={{ ...styles.td, color: "var(--color-accent-red-dim)" }}>
        {pos.stop_loss != null ? pos.stop_loss.toFixed(2) : "—"}
      </td>
      <td style={{ ...styles.td, color: "var(--color-accent-green-dim)" }}>
        {pos.take_profit != null ? pos.take_profit.toFixed(2) : "—"}
      </td>
    </motion.tr>
  );
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
  tabs: {
    display: "flex",
    gap: 2,
  },
  tab: {
    padding: "2px 7px",
    background: "none",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
    letterSpacing: "0.05em",
  },
  importBtn: {
    padding: "2px 7px",
    background: "none",
    border: "1px solid rgba(14,165,233,0.35)",
    borderRadius: 3,
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-accent-blue)",
    cursor: "pointer",
    letterSpacing: "0.05em",
    marginLeft: 4,
  },
  tabActive: {
    background: "var(--color-accent-blue-bg)",
    border: "1px solid rgba(14,165,233,0.3)",
    color: "var(--color-accent-blue)",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "3px 10px",
    borderBottom: "1px solid var(--color-bg-separator)",
  },
  rowLabel: {
    fontSize: 10,
    color: "var(--color-text-secondary)",
    fontFamily: "var(--font-sans)",
  },
  rowValue: {
    fontSize: 11,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    textAlign: "right" as const,
  },
  meterTrack: {
    width: "100%",
    height: 4,
    background: "var(--color-bg-elevated)",
    borderRadius: 2,
    overflow: "hidden",
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
    padding: "3px 6px",
    textAlign: "right" as const,
    fontFamily: "var(--font-mono)",
    borderBottom: "1px solid rgba(255,255,255,0.03)",
  },
  tableRow: {},
};
