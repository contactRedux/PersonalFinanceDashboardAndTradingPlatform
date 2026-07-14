"use client";

import React from "react";
import { PanelGrid } from "@/components/layout/PanelGrid";
import { Panel } from "@/components/layout/Panel";

/**
 * Main dashboard page — the core panel grid.
 * Each panel ID matches the layout store's layout items.
 * Full panel implementations are built in ST-6 through ST-10.
 */
export default function DashboardPage() {
  return (
    <PanelGrid>
      {/* Candlestick chart — the flagship panel */}
      <div key="chart">
        <Panel id="chart" title="Chart">
          <ChartPlaceholder />
        </Panel>
      </div>

      {/* Watchlist */}
      <div key="watchlist">
        <Panel id="watchlist" title="Watchlist">
          <WatchlistPlaceholder />
        </Panel>
      </div>

      {/* Portfolio overview */}
      <div key="portfolio">
        <Panel id="portfolio" title="Portfolio">
          <PortfolioPlaceholder />
        </Panel>
      </div>

      {/* News & AI Sentiment */}
      <div key="news">
        <Panel id="news" title="News & Sentiment">
          <NewsPlaceholder />
        </Panel>
      </div>
    </PanelGrid>
  );
}

// ─── Placeholder components (replaced in ST-6 through ST-10) ─────────────────

function ChartPlaceholder() {
  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8 }}>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-accent-green)", letterSpacing: "0.1em" }}>
        CHART ENGINE
      </span>
      <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
        TradingView Lightweight Charts — built in ST-6
      </span>
    </div>
  );
}

function WatchlistPlaceholder() {
  const symbols = ["AAPL", "MSFT", "NVDA", "BTC-USD", "ETH-USD", "EUR-USD"];
  return (
    <table className="terminal-table" style={{ width: "100%" }}>
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Price</th>
          <th>Chg%</th>
        </tr>
      </thead>
      <tbody>
        {symbols.map((s) => (
          <tr key={s}>
            <td style={{ textAlign: "left", color: "var(--color-accent-blue)", fontWeight: 600 }}>{s}</td>
            <td>—</td>
            <td>—</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PortfolioPlaceholder() {
  const rows = [
    { label: "Total Equity",    value: "$0.00" },
    { label: "Cash",            value: "$0.00" },
    { label: "Unrealized P&L",  value: "$0.00" },
    { label: "Realized P&L",    value: "$0.00" },
    { label: "Day P&L",         value: "$0.00" },
    { label: "Max Drawdown",    value: "0.00%" },
  ];
  return (
    <div style={{ padding: "8px 10px" }}>
      {rows.map(({ label, value }) => (
        <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid var(--color-bg-separator)" }}>
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{label}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

function NewsPlaceholder() {
  return (
    <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 8 }}>
      {["No news articles loaded yet.", "Sentiment pipeline built in ST-8.", "AI scoring via FinBERT + GPT-4o."].map((t, i) => (
        <div key={i} style={{ fontSize: 11, color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-bg-separator)", paddingBottom: 6 }}>
          {t}
        </div>
      ))}
    </div>
  );
}
