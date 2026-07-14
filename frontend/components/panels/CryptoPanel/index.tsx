"use client";

/**
 * CryptoPanel — crypto-specific dashboard.
 *
 * Features:
 *  - Perpetual swap funding rates (Binance)
 *  - Top 24h movers (gainers / losers)
 *  - On-chain metrics for BTC / ETH
 *  - Liquidation level bars
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import {
  getFundingRates,
  getCryptoTopMovers,
  getCryptoOnchain,
  type FundingRate,
  type CryptoMover,
} from "@/lib/api/screener";
import { priceChangeClass, formatCompact } from "@/lib/formatters";

interface CryptoPanelProps { panelId?: string; }
type Tab = "funding" | "movers" | "onchain";

export function CryptoPanel({ panelId = "crypto" }: CryptoPanelProps) {
  const [tab, setTab] = useState<Tab>("funding");
  const [fundingRates, setFundingRates] = useState<FundingRate[]>([]);
  const [movers, setMovers] = useState<CryptoMover[]>([]);
  const [btcMetrics, setBtcMetrics] = useState<Record<string, number | null>>({});
  const [ethMetrics, setEthMetrics] = useState<Record<string, number | null>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [frRes, moversRes, btcRes, ethRes] = await Promise.all([
        getFundingRates(),
        getCryptoTopMovers(8),
        getCryptoOnchain("BTC"),
        getCryptoOnchain("ETH"),
      ]);
      setFundingRates(frRes.rates);
      setMovers(moversRes.movers);
      setBtcMetrics(btcRes.metrics);
      setEthMetrics(ethRes.metrics);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const toolbar = (
    <div style={{ display: "flex", gap: 2 }}>
      {(["funding", "movers", "onchain"] as Tab[]).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
          onClick={() => setTab(t)}
        >
          {t.toUpperCase()}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="Crypto" toolbar={toolbar}>
      {loading && <div style={styles.stateMsg}>Loading…</div>}

      {!loading && (
        <motion.div key={tab} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.12 }}>
          {tab === "funding"  && <FundingRatesView rates={fundingRates} />}
          {tab === "movers"   && <TopMoversView movers={movers} />}
          {tab === "onchain"  && <OnChainView btc={btcMetrics} eth={ethMetrics} />}
        </motion.div>
      )}
    </Panel>
  );
}

function FundingRatesView({ rates }: { rates: FundingRate[] }) {
  const maxRate = Math.max(...rates.map((r) => Math.abs(r.funding_rate)), 0.01);
  return (
    <div>
      <div style={styles.sectionHeader}>PERPETUAL FUNDING RATES (8H)</div>
      {rates.map((r) => {
        const pct = r.funding_rate;
        const barW = Math.abs(pct) / maxRate * 80;
        const barColor = pct > 0 ? "var(--color-accent-green)" : "var(--color-accent-red)";
        return (
          <div key={r.symbol} style={styles.fundingRow}>
            <span style={styles.fundingSymbol}>{r.symbol.replace("USDT", "")}</span>
            <span style={{ ...styles.fundingRate, color: pct >= 0 ? "var(--color-accent-green)" : "var(--color-accent-red)" }}>
              {pct >= 0 ? "+" : ""}{pct.toFixed(4)}%
            </span>
            <div style={styles.barTrack}>
              <div style={{ height: "100%", width: `${barW}%`, background: barColor, borderRadius: 1, marginLeft: pct < 0 ? `${80 - barW}%` : 0 }} />
            </div>
          </div>
        );
      })}
      <div style={styles.note}>Positive rate = longs pay shorts</div>
    </div>
  );
}

function MoverList({ title, items, color }: { title: string; items: CryptoMover[]; color: string }) {
  return (
    <div>
      <div style={{ ...styles.sectionHeader, color }}>{title}</div>
      {items.map((m) => (
        <div key={m.symbol} style={styles.moverRow}>
          <span style={styles.moverSymbol}>{m.symbol}</span>
          <span style={styles.moverPrice}>${m.price < 1 ? m.price.toFixed(5) : m.price.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
          <span style={{ ...styles.moverChange, color }} className={priceChangeClass(m.change_24h ?? 0)}>
            {(m.change_24h ?? 0) >= 0 ? "+" : ""}{(m.change_24h ?? 0).toFixed(2)}%
          </span>
          <span style={styles.moverVol}>{formatCompact(m.volume_24h ?? 0)}</span>
        </div>
      ))}
    </div>
  );
}

function TopMoversView({ movers }: { movers: CryptoMover[] }) {
  const gainers = [...movers].filter((m) => (m.change_24h ?? 0) > 0).sort((a, b) => (b.change_24h ?? 0) - (a.change_24h ?? 0)).slice(0, 4);
  const losers  = [...movers].filter((m) => (m.change_24h ?? 0) < 0).sort((a, b) => (a.change_24h ?? 0) - (b.change_24h ?? 0)).slice(0, 4);

  return (
    <div>
      <MoverList title="TOP GAINERS" items={gainers} color="var(--color-accent-green)" />
      <MoverList title="TOP LOSERS"  items={losers}  color="var(--color-accent-red)" />
    </div>
  );
}

function OnChainView({
  btc,
  eth,
}: {
  btc: Record<string, number | null>;
  eth: Record<string, number | null>;
}) {
  const fmt = (v: number | null | undefined, prefix = "", suffix = "") =>
    v != null ? `${prefix}${formatCompact(v)}${suffix}` : "—";

  const assets = [
    { name: "BTC", metrics: btc, color: "#f7931a" },
    { name: "ETH", metrics: eth, color: "#627eea" },
  ];

  return (
    <div>
      {assets.map(({ name, metrics, color }) => (
        <div key={name}>
          <div style={{ ...styles.sectionHeader, color }}>{name} ON-CHAIN</div>
          {[
            { label: "Price",         value: fmt(metrics.price, "$") },
            { label: "Market Cap",    value: fmt(metrics.market_cap, "$") },
            { label: "24h Volume",    value: fmt(metrics.volume_24h, "$") },
            { label: "24h Change",    value: metrics.change_24h != null ? `${metrics.change_24h >= 0 ? "+" : ""}${metrics.change_24h.toFixed(2)}%` : "—" },
            { label: "ATH",           value: fmt(metrics.ath, "$") },
            { label: "ATH Change",    value: metrics.ath_change_pct != null ? `${metrics.ath_change_pct.toFixed(1)}%` : "—" },
          ].map(({ label, value }) => (
            <div key={label} style={styles.onchainRow}>
              <span style={styles.onchainLabel}>{label}</span>
              <span style={styles.onchainValue}>{value}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  stateMsg:       { textAlign: "center" as const, padding: "16px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  tab:            { padding: "2px 5px", background: "none", border: "1px solid transparent", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", cursor: "pointer" },
  tabActive:      { background: "var(--color-accent-blue-bg)", border: "1px solid rgba(14,165,233,0.3)", color: "var(--color-accent-blue)" },
  sectionHeader:  { padding: "3px 10px 2px", fontSize: 8, fontWeight: 700, letterSpacing: "0.1em", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", background: "var(--color-bg-elevated)", borderBottom: "1px solid var(--color-bg-separator)" },
  fundingRow:     { display: "flex", alignItems: "center", gap: 6, padding: "3px 10px", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  fundingSymbol:  { width: 48, fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, color: "var(--color-accent-blue)" },
  fundingRate:    { width: 68, fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, textAlign: "right" as const },
  barTrack:       { flex: 1, height: 4, background: "var(--color-bg-elevated)", borderRadius: 1, overflow: "hidden" },
  note:           { padding: "4px 10px", fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  moverRow:       { display: "flex", alignItems: "center", gap: 4, padding: "2px 10px", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  moverSymbol:    { width: 44, fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, color: "var(--color-accent-blue)" },
  moverPrice:     { flex: 1, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--color-text-primary)" },
  moverChange:    { width: 52, fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, textAlign: "right" as const },
  moverVol:       { width: 44, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--color-text-muted)", textAlign: "right" as const },
  onchainRow:     { display: "flex", justifyContent: "space-between", padding: "2px 10px", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  onchainLabel:   { fontSize: 10, color: "var(--color-text-secondary)", fontFamily: "var(--font-sans)" },
  onchainValue:   { fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--color-text-primary)" },
};
