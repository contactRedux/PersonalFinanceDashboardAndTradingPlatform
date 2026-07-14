"use client";

/**
 * WatchlistPanel — real-time quote watchlist.
 *
 * Displays symbol, last price, $ change, % change, volume, and a sparkline.
 * Prices update live from the marketDataStore (WebSocket).
 * Users can add/remove symbols and switch between multiple watchlists.
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import { Sparkline } from "@/components/ui/Sparkline";
import { useMarketDataStore } from "@/store/marketDataStore";
import { useWatchlistStore } from "@/store/watchlistStore";
import { formatPrice, formatPct, priceChangeClass } from "@/lib/formatters";
import { searchSymbols } from "@/lib/api/market";
import type { SymbolSearchResult } from "@/lib/api/market";

interface WatchlistPanelProps {
  panelId?: string;
}

export function WatchlistPanel({ panelId = "watchlist" }: WatchlistPanelProps) {
  const quotes = useMarketDataStore((s) => s.quotes);
  const priceHistory = useMarketDataStore((s) => s.priceHistory);
  const { watchlists, activeWatchlistId, setActive, addSymbol, removeSymbol } =
    useWatchlistStore();

  const activeWatchlist = watchlists.find((w) => w.id === activeWatchlistId);
  const symbols = activeWatchlist?.symbols ?? [];

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SymbolSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Debounced symbol search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    const timer = setTimeout(() => {
      searchSymbols(searchQuery)
        .then((r) => setSearchResults(r.results.slice(0, 8)))
        .catch(() => setSearchResults([]))
        .finally(() => setSearchLoading(false));
    }, 350);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleAddSymbol = useCallback(
    (symbol: string) => {
      if (activeWatchlistId) {
        addSymbol(activeWatchlistId, symbol.toUpperCase());
        setSearchQuery("");
        setSearchResults([]);
      }
    },
    [activeWatchlistId, addSymbol]
  );

  const handleRemoveSymbol = useCallback(
    (symbol: string) => {
      if (activeWatchlistId) removeSymbol(activeWatchlistId, symbol);
    },
    [activeWatchlistId, removeSymbol]
  );

  const toolbar = (
    <span style={styles.watchlistName}>{activeWatchlist?.name ?? "Watchlist"}</span>
  );

  return (
    <Panel id={panelId} title="Watchlist" toolbar={toolbar}>
      {/* Watchlist tabs */}
      {watchlists.length > 1 && (
        <div style={styles.tabs}>
          {watchlists.map((wl) => (
            <button
              key={wl.id}
              style={{
                ...styles.tab,
                ...(wl.id === activeWatchlistId ? styles.tabActive : {}),
              }}
              onClick={() => setActive(wl.id)}
            >
              {wl.name}
            </button>
          ))}
        </div>
      )}

      {/* Symbol search */}
      <div style={styles.searchWrapper}>
        <input
          type="text"
          placeholder="+ Add symbol…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={styles.searchInput}
          spellCheck={false}
          autoComplete="off"
          aria-label="Search symbols to add"
        />
        {searchLoading && <span style={styles.searchSpinner}>⟳</span>}

        {/* Search results dropdown */}
        {searchResults.length > 0 && (
          <div style={styles.searchDropdown}>
            {searchResults.map((r) => (
              <button
                key={r.symbol}
                style={styles.searchResult}
                onClick={() => handleAddSymbol(r.symbol)}
              >
                <span style={styles.searchResultSymbol}>{r.symbol}</span>
                <span style={styles.searchResultName}>{r.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Symbol rows */}
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={{ ...styles.th, textAlign: "left" }}>Symbol</th>
            <th style={styles.th}>Price</th>
            <th style={styles.th}>Chg</th>
            <th style={styles.th}>Chg%</th>
            <th style={styles.th}>Vol</th>
            <th style={styles.th}>Spark</th>
            <th style={styles.th} />
          </tr>
        </thead>
        <tbody>
          <AnimatePresence>
            {symbols.map((symbol) => {
              const quote = quotes[symbol];
              return (
                <WatchlistRow
                  key={symbol}
                  symbol={symbol}
                  price={quote?.price ?? null}
                  change={quote?.change ?? null}
                  changePct={quote?.change_pct ?? null}
                  volume={quote?.volume ?? null}
                  sparkline={priceHistory[symbol] ?? []}
                  onRemove={handleRemoveSymbol}
                />
              );
            })}
          </AnimatePresence>
          {symbols.length === 0 && (
            <tr>
              <td
                colSpan={6}
                style={{
                  textAlign: "center",
                  padding: "16px",
                  color: "var(--color-text-muted)",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                }}
              >
                No symbols — type above to add
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Panel>
  );
}

// ─── WatchlistRow ─────────────────────────────────────────────────────────────
interface WatchlistRowProps {
  symbol: string;
  price: number | null;
  change: number | null;
  changePct: number | null;
  volume: number | null;
  sparkline: number[];
  onRemove: (symbol: string) => void;
}

function WatchlistRow({
  symbol,
  price,
  change,
  changePct,
  volume,
  sparkline,
  onRemove,
}: WatchlistRowProps) {
  const colorClass = priceChangeClass(changePct ?? 0);
  const isPositive = (changePct ?? 0) >= 0;

  return (
    <motion.tr
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.15 }}
      style={styles.row}
    >
      {/* Symbol */}
      <td style={{ ...styles.td, textAlign: "left" }}>
        <span style={styles.symbolText}>{symbol}</span>
      </td>

      {/* Price — flashes on update */}
      <td style={styles.td}>
        <motion.span
          key={price ?? 0}
          initial={{ color: isPositive ? "#00d084" : "#ef4444" }}
          animate={{ color: "var(--color-text-primary)" }}
          transition={{ duration: 0.6 }}
          style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
        >
          {price !== null ? formatPrice(price) : "—"}
        </motion.span>
      </td>

      {/* Dollar change */}
      <td style={{ ...styles.td, className: colorClass } as React.CSSProperties}>
        <span className={colorClass} style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
          {change !== null
            ? (change >= 0 ? "+" : "") + formatPrice(change)
            : "—"}
        </span>
      </td>

      {/* Percent change */}
      <td style={styles.td}>
        <span className={colorClass} style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
          {changePct !== null ? formatPct(changePct) : "—"}
        </span>
      </td>

      {/* Volume */}
      <td style={styles.td}>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--color-text-muted)" }}>
          {volume !== null ? formatVolume(volume) : "—"}
        </span>
      </td>

      {/* Sparkline */}
      <td style={{ ...styles.td, padding: "2px 4px" }}>
        {sparkline.length >= 2 ? (
          <Sparkline data={sparkline} width={60} height={22} />
        ) : (
          <span style={{ fontSize: 9, color: "#333", fontFamily: "var(--font-mono)" }}>—</span>
        )}
      </td>

      {/* Remove button */}
      <td style={styles.td}>
        <button
          style={styles.removeBtn}
          onClick={() => onRemove(symbol)}
          aria-label={`Remove ${symbol} from watchlist`}
          title="Remove"
        >
          ×
        </button>
      </td>
    </motion.tr>
  );
}

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(1) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toFixed(0);
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  watchlistName: {
    fontSize: 10,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  tabs: {
    display: "flex",
    gap: 2,
    padding: "4px 8px",
    borderBottom: "1px solid var(--color-bg-separator)",
  },
  tab: {
    padding: "2px 8px",
    background: "none",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
  },
  tabActive: {
    background: "var(--color-accent-green-bg)",
    border: "1px solid rgba(0,208,132,0.3)",
    color: "var(--color-accent-green)",
  },
  searchWrapper: {
    position: "relative",
    padding: "4px 8px",
    borderBottom: "1px solid var(--color-bg-separator)",
  },
  searchInput: {
    width: "100%",
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "4px 8px",
    fontSize: 11,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    outline: "none",
    boxSizing: "border-box" as const,
    textTransform: "uppercase" as const,
  },
  searchSpinner: {
    position: "absolute",
    right: 16,
    top: "50%",
    transform: "translateY(-50%)",
    color: "var(--color-text-muted)",
    fontSize: 14,
  },
  searchDropdown: {
    position: "absolute",
    left: 8,
    right: 8,
    top: "100%",
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 4,
    zIndex: 50,
    boxShadow: "0 8px 24px rgba(0,0,0,0.8)",
    maxHeight: 240,
    overflowY: "auto" as const,
  },
  searchResult: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    width: "100%",
    padding: "6px 10px",
    background: "none",
    border: "none",
    borderBottom: "1px solid var(--color-bg-separator)",
    cursor: "pointer",
    textAlign: "left" as const,
  },
  searchResultSymbol: {
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    fontWeight: 700,
    color: "var(--color-accent-blue)",
  },
  searchResultName: {
    fontSize: 10,
    color: "var(--color-text-muted)",
    maxWidth: 120,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    padding: "4px 8px",
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "var(--color-text-muted)",
    borderBottom: "1px solid var(--color-bg-separator)",
    fontFamily: "var(--font-mono)",
    textAlign: "right" as const,
    userSelect: "none",
  },
  td: {
    padding: "3px 8px",
    textAlign: "right" as const,
    borderBottom: "1px solid rgba(255,255,255,0.03)",
  },
  row: {},
  symbolText: {
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    fontWeight: 700,
    color: "var(--color-accent-blue)",
    letterSpacing: "0.02em",
  },
  removeBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "var(--color-text-muted)",
    fontSize: 14,
    lineHeight: 1,
    padding: "0 2px",
    opacity: 0.4,
  },
};
