"use client";

/**
 * OrderBookPanel — Level 2 bid/ask ladder with size visualization.
 *
 * Connects to WebSocket /ws/orderbook/{symbol} for real-time depth.
 * Falls back to a synthetic demo order book when no data is available.
 *
 * Each price level shows:
 *  - Price
 *  - Size (quantity at that level)
 *  - Total (cumulative size)
 *  - A colored bar proportional to size (bids = green, asks = red)
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import { WS_URLS } from "@/lib/api/websocket";

interface PriceLevel {
  price: number;
  size: number;
  total: number;
}

interface OrderBookSnapshot {
  symbol: string;
  bids: [number, number][];  // [price, size]
  asks: [number, number][];
  timestamp: string;
}

interface OrderBookPanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

const DEPTH = 10; // levels to display on each side

export function OrderBookPanel({
  panelId = "orderbook",
  defaultSymbol = "AAPL",
}: OrderBookPanelProps) {
  const [symbol, setSymbol] = useState(defaultSymbol.toUpperCase());
  const [inputValue, setInputValue] = useState(defaultSymbol.toUpperCase());
  const [bids, setBids] = useState<PriceLevel[]>([]);
  const [asks, setAsks] = useState<PriceLevel[]>([]);
  const [spread, setSpread] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Synthetic demo book used when no real data arrives
  const seedDemoBook = useCallback((sym: string) => {
    const base = sym === "AAPL" ? 198.75 : sym === "NVDA" ? 498.5 : 100;
    const genLevels = (side: "bid" | "ask"): PriceLevel[] => {
      let cumulative = 0;
      return Array.from({ length: DEPTH }, (_, i) => {
        const price =
          side === "bid"
            ? base - (i + 1) * 0.05
            : base + (i + 1) * 0.05;
        const size = Math.round(100 + Math.random() * 900);
        cumulative += size;
        return { price, size, cumulative: cumulative };
      }).map((l) => ({ price: l.price, size: l.size, total: l.cumulative }));
    };
    const demoAsks = genLevels("ask").reverse();
    const demoBids = genLevels("bid");
    setAsks(demoAsks);
    setBids(demoBids);
    const bestAsk = demoAsks[demoAsks.length - 1]?.price ?? 0;
    const bestBid = demoBids[0]?.price ?? 0;
    setSpread(bestAsk - bestBid);
  }, []);

  useEffect(() => {
    // Seed demo data immediately for UX
    seedDemoBook(symbol);

    // Attempt real WebSocket connection
    const url = WS_URLS.orderbook(symbol);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data as string) as OrderBookSnapshot;
        if (!data.bids || !data.asks) return;

        const toLevel = (pairs: [number, number][]): PriceLevel[] => {
          let cum = 0;
          return pairs.map(([price, size]) => {
            cum += size;
            return { price, size, total: cum };
          });
        };

        const askLevels = toLevel(data.asks.slice(0, DEPTH)).reverse();
        const bidLevels = toLevel(data.bids.slice(0, DEPTH));
        setAsks(askLevels);
        setBids(bidLevels);

        const bestAsk = data.asks[0]?.[0] ?? 0;
        const bestBid = data.bids[0]?.[0] ?? 0;
        setSpread(bestAsk - bestBid);
      } catch {
        // Malformed message — ignore
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [symbol, seedDemoBook]);

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim().toUpperCase();
    if (trimmed && trimmed !== symbol) setSymbol(trimmed);
  };

  // Max total for bar width scaling
  const maxTotal = Math.max(
    bids[bids.length - 1]?.total ?? 1,
    asks[0]?.total ?? 1
  );

  const toolbar = (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: connected ? "var(--color-accent-green)" : "var(--color-text-muted)",
          display: "inline-block",
        }}
        title={connected ? "Live" : "Demo data"}
      />
      <form onSubmit={handleSymbolSubmit} style={{ display: "flex", gap: 3 }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value.toUpperCase())}
          style={styles.symbolInput}
          aria-label="Order book symbol"
          spellCheck={false}
          maxLength={10}
        />
        <button type="submit" style={styles.goBtn}>GO</button>
      </form>
    </div>
  );

  return (
    <Panel id={panelId} title={`Level 2 — ${symbol}`} toolbar={toolbar}>
      <div style={styles.container}>
        {/* Column headers */}
        <div style={styles.headerRow}>
          <span style={styles.colHeader}>PRICE</span>
          <span style={styles.colHeader}>SIZE</span>
          <span style={styles.colHeader}>TOTAL</span>
        </div>

        {/* Asks — displayed in reverse so closest to mid is at bottom */}
        <div style={{ borderBottom: "1px solid var(--color-bg-separator)" }}>
          <AnimatePresence>
            {asks.map((level) => (
              <BidAskRow
                key={`ask-${level.price.toFixed(5)}`}
                level={level}
                side="ask"
                maxTotal={maxTotal}
              />
            ))}
          </AnimatePresence>
        </div>

        {/* Spread */}
        <div style={styles.spreadRow}>
          <span style={styles.spreadLabel}>SPREAD</span>
          <span style={styles.spreadValue}>
            {spread != null ? spread.toFixed(2) : "—"}
          </span>
        </div>

        {/* Bids */}
        <div>
          <AnimatePresence>
            {bids.map((level) => (
              <BidAskRow
                key={`bid-${level.price.toFixed(5)}`}
                level={level}
                side="bid"
                maxTotal={maxTotal}
              />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </Panel>
  );
}

// ─── BidAskRow ─────────────────────────────────────────────────────────────────
function BidAskRow({
  level,
  side,
  maxTotal,
}: {
  level: PriceLevel;
  side: "bid" | "ask";
  maxTotal: number;
}) {
  const barPct = maxTotal > 0 ? (level.total / maxTotal) * 100 : 0;
  const barColor =
    side === "bid" ? "rgba(0,208,132,0.12)" : "rgba(239,68,68,0.12)";
  const priceColor =
    side === "bid" ? "var(--color-accent-green)" : "var(--color-accent-red)";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.1 }}
      style={{ ...styles.levelRow, position: "relative" }}
    >
      {/* Background bar — volume visualization */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          right: 0,
          width: `${barPct}%`,
          background: barColor,
          borderRadius: 1,
        }}
      />

      {/* Data — on top of bar */}
      <span style={{ ...styles.levelPrice, color: priceColor }}>
        {level.price.toFixed(2)}
      </span>
      <span style={styles.levelSize}>{level.size.toLocaleString()}</span>
      <span style={styles.levelTotal}>{level.total.toLocaleString()}</span>
    </motion.div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  container: {
    userSelect: "none",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    padding: "3px 8px",
    borderBottom: "1px solid var(--color-bg-separator)",
  },
  colHeader: {
    fontSize: 8,
    fontWeight: 600,
    letterSpacing: "0.06em",
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  levelRow: {
    display: "flex",
    justifyContent: "space-between",
    padding: "1px 8px",
    overflow: "hidden",
  },
  levelPrice: {
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    fontWeight: 700,
    zIndex: 1,
    position: "relative" as const,
  },
  levelSize: {
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    color: "var(--color-text-secondary)",
    zIndex: 1,
    position: "relative" as const,
  },
  levelTotal: {
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    color: "var(--color-text-muted)",
    zIndex: 1,
    position: "relative" as const,
  },
  spreadRow: {
    display: "flex",
    justifyContent: "center",
    gap: 8,
    padding: "2px 8px",
    background: "var(--color-bg-overlay)",
  },
  spreadLabel: {
    fontSize: 8,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-muted)",
    letterSpacing: "0.06em",
  },
  spreadValue: {
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-accent-amber)",
    fontWeight: 700,
  },
  symbolInput: {
    width: 64,
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    color: "var(--color-text-primary)",
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    padding: "2px 5px",
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
    padding: "2px 5px",
    cursor: "pointer",
    letterSpacing: "0.05em",
  },
};
