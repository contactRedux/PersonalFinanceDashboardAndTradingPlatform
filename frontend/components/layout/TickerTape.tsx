"use client";

import React from "react";
import { motion } from "framer-motion";
import { useMarketDataStore } from "@/store/marketDataStore";
import { useWatchlistStore } from "@/store/watchlistStore";
import { formatPrice, formatPct, priceChangeClass } from "@/lib/formatters";

/**
 * TickerTape — real-time scrolling price tape across the top of the dashboard.
 * Reads from the shared Zustand marketDataStore (no direct WebSocket).
 */
export function TickerTape() {
  const quotes = useMarketDataStore((s) => s.quotes);
  const activeWatchlist = useWatchlistStore((s) => s.getActive());
  const symbols = activeWatchlist?.symbols ?? ["AAPL", "MSFT", "BTC-USD", "EUR-USD"];

  const items = symbols.map((sym) => ({
    symbol: sym,
    quote: quotes[sym],
  }));

  return (
    <div className="ticker-tape">
      <motion.div
        style={{
          display: "flex",
          gap: 0,
          paddingLeft: "100%",
          whiteSpace: "nowrap",
        }}
        animate={{ x: [0, -2000] }}
        transition={{
          duration: 40,
          ease: "linear",
          repeat: Infinity,
        }}
      >
        {[...items, ...items].map(({ symbol, quote }, i) => (
          <TickerItem key={`${symbol}-${i}`} symbol={symbol} quote={quote} />
        ))}
      </motion.div>
    </div>
  );
}

interface TickerItemProps {
  symbol: string;
  quote?: { price: number; change_pct: number } | null;
}

function TickerItem({ symbol, quote }: TickerItemProps) {
  const changeClass = priceChangeClass(quote?.change_pct ?? 0);
  return (
    <span
      style={{
        padding: "0 16px",
        display: "inline-flex",
        gap: 6,
        alignItems: "center",
        borderRight: "1px solid var(--color-bg-separator)",
        fontFamily: "var(--font-mono)",
        fontSize: 11,
      }}
    >
      <span style={{ color: "var(--color-text-primary)", fontWeight: 600 }}>{symbol}</span>
      {quote ? (
        <>
          <span className={changeClass}>{formatPrice(quote.price)}</span>
          <span className={changeClass}>{formatPct(quote.change_pct)}</span>
        </>
      ) : (
        <span style={{ color: "var(--color-text-muted)" }}>—</span>
      )}
    </span>
  );
}
