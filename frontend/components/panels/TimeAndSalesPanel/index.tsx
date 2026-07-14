"use client";

/**
 * TimeAndSalesPanel — real-time trade tape (Time & Sales).
 *
 * Streams trade prints from /ws/tape WebSocket (all symbols) or
 * per-symbol via subscribe message. Each print shows:
 *  - Time (HH:MM:SS.mmm)
 *  - Symbol
 *  - Price (green = uptick, red = downtick vs previous)
 *  - Size
 *  - Exchange / condition
 *
 * Falls back to synthetic demo prints when no WebSocket data arrives.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { WS_URLS } from "@/lib/api/websocket";

interface TradePrint {
  id: string;
  timestamp: string;
  symbol: string;
  price: number;
  size: number;
  exchange?: string;
  condition?: string;
  side?: "buy" | "sell" | "unknown";
}

interface WsTapePrint {
  type?: string;
  timestamp?: string;
  symbol?: string;
  price?: number;
  size?: number;
  exchange?: string;
  condition?: string;
  side?: "buy" | "sell" | "unknown";
}

interface TimeAndSalesPanelProps {
  panelId?: string;
  defaultSymbol?: string;
  maxRows?: number;
}

const MAX_ROWS = 200;

export function TimeAndSalesPanel({
  panelId = "tape",
  defaultSymbol = "AAPL",
  maxRows = MAX_ROWS,
}: TimeAndSalesPanelProps) {
  const [symbol, setSymbol] = useState(defaultSymbol.toUpperCase());
  const [inputValue, setInputValue] = useState(defaultSymbol.toUpperCase());
  const [prints, setPrints] = useState<TradePrint[]>([]);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pausedRef = useRef(false);
  const listRef = useRef<HTMLDivElement>(null);
  const demoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Sync paused state into ref so callbacks can read latest value without re-render
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  const appendPrint = useCallback(
    (print: TradePrint) => {
      if (pausedRef.current) return;
      setPrints((prev) => {
        const next = [print, ...prev];
        return next.length > maxRows ? next.slice(0, maxRows) : next;
      });
    },
    [maxRows]
  );

  // Demo tape generator — fires until real WebSocket connects
  const startDemoTape = useCallback(
    (sym: string) => {
      if (demoTimerRef.current) clearInterval(demoTimerRef.current);
      const base = sym === "AAPL" ? 198.75 : sym === "NVDA" ? 498.5 : 100;
      let lastPrice = base;
      let idCounter = 0;

      demoTimerRef.current = setInterval(() => {
        lastPrice = lastPrice + (Math.random() - 0.5) * 0.1;
        idCounter++;
        const side = Math.random() > 0.5 ? "buy" : "sell";
        appendPrint({
          id: `demo-${idCounter}`,
          timestamp: new Date().toISOString(),
          symbol: sym,
          price: lastPrice,
          size: Math.round(100 + Math.random() * 900),
          exchange: "DEMO",
          side: side as "buy" | "sell",
        });
      }, 800);
    },
    [appendPrint]
  );

  useEffect(() => {
    setPrints([]);
    startDemoTape(symbol);

    const url = WS_URLS.tape();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      if (demoTimerRef.current) {
        clearInterval(demoTimerRef.current);
        demoTimerRef.current = null;
      }
      // Subscribe to specific symbol
      ws.send(JSON.stringify({ action: "subscribe", symbols: [symbol] }));
    };

    ws.onclose = () => {
      setConnected(false);
      // Restart demo if WS disconnects
      startDemoTape(symbol);
    };

    ws.onmessage = (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data as string) as WsTapePrint;
        if (!data.price || !data.symbol) return;
        appendPrint({
          id: `ws-${Date.now()}-${Math.random()}`,
          timestamp: data.timestamp ?? new Date().toISOString(),
          symbol: data.symbol,
          price: data.price,
          size: data.size ?? 0,
          exchange: data.exchange,
          side: data.side,
        });
      } catch {
        // Ignore parse errors
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
      if (demoTimerRef.current) {
        clearInterval(demoTimerRef.current);
        demoTimerRef.current = null;
      }
    };
  }, [symbol, startDemoTape, appendPrint]);

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim().toUpperCase();
    if (trimmed && trimmed !== symbol) setSymbol(trimmed);
  };

  const toolbar = (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: connected ? "var(--color-accent-green)" : "var(--color-accent-amber)",
          display: "inline-block",
        }}
        title={connected ? "Live WebSocket" : "Demo mode"}
      />
      <button
        style={{
          ...styles.ctrlBtn,
          color: paused ? "var(--color-accent-amber)" : "var(--color-text-muted)",
        }}
        onClick={() => setPaused((p) => !p)}
        title={paused ? "Resume" : "Pause"}
        aria-label={paused ? "Resume tape" : "Pause tape"}
      >
        {paused ? "▶" : "⏸"}
      </button>
      <button
        style={styles.ctrlBtn}
        onClick={() => setPrints([])}
        title="Clear"
        aria-label="Clear tape"
      >
        ✕
      </button>
      <form onSubmit={handleSymbolSubmit} style={{ display: "flex", gap: 3 }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value.toUpperCase())}
          style={styles.symbolInput}
          aria-label="Tape symbol filter"
          spellCheck={false}
          maxLength={10}
        />
        <button type="submit" style={styles.goBtn}>GO</button>
      </form>
    </div>
  );

  return (
    <Panel id={panelId} title={`Time & Sales — ${symbol}`} toolbar={toolbar}>
      {/* Column headers */}
      <div style={styles.headerRow}>
        <span style={{ ...styles.col, flex: 1.2 }}>TIME</span>
        <span style={{ ...styles.col, flex: 0.7 }}>SYM</span>
        <span style={{ ...styles.col, flex: 1, textAlign: "right" }}>PRICE</span>
        <span style={{ ...styles.col, flex: 1, textAlign: "right" }}>SIZE</span>
        <span style={{ ...styles.col, flex: 0.8, textAlign: "right" }}>EXC</span>
      </div>

      {/* Scrollable tape */}
      <div ref={listRef} style={styles.tape}>
        {prints.length === 0 && (
          <div style={styles.empty}>Waiting for prints…</div>
        )}
        {prints.map((print, idx) => (
          <TapeRow key={print.id} print={print} prevPrice={prints[idx + 1]?.price} />
        ))}
      </div>
    </Panel>
  );
}

// ─── TapeRow ──────────────────────────────────────────────────────────────────
function TapeRow({
  print,
  prevPrice,
}: {
  print: TradePrint;
  prevPrice: number | undefined;
}) {
  const uptick = prevPrice == null || print.price > prevPrice;
  const downtick = prevPrice != null && print.price < prevPrice;

  const priceColor = uptick
    ? "var(--color-accent-green)"
    : downtick
      ? "var(--color-accent-red)"
      : "var(--color-text-primary)";

  const time = new Date(print.timestamp);
  const timeStr = `${time.getHours().toString().padStart(2, "0")}:${time.getMinutes().toString().padStart(2, "0")}:${time.getSeconds().toString().padStart(2, "0")}.${time.getMilliseconds().toString().padStart(3, "0")}`;

  const rowBg =
    (print.size ?? 0) >= 5000
      ? "rgba(245,158,11,0.06)" // large print — amber highlight
      : "transparent";

  return (
    <div style={{ ...styles.tapeRow, background: rowBg }}>
      <span style={{ ...styles.tapeTd, flex: 1.2, color: "var(--color-text-muted)", fontSize: 9 }}>
        {timeStr}
      </span>
      <span style={{ ...styles.tapeTd, flex: 0.7, color: "var(--color-accent-blue)", fontWeight: 700 }}>
        {print.symbol}
      </span>
      <span
        style={{
          ...styles.tapeTd,
          flex: 1,
          textAlign: "right",
          color: priceColor,
          fontWeight: uptick || downtick ? 700 : 400,
        }}
      >
        {uptick ? "▲ " : downtick ? "▼ " : "  "}
        {print.price.toFixed(2)}
      </span>
      <span
        style={{
          ...styles.tapeTd,
          flex: 1,
          textAlign: "right",
          color: (print.size ?? 0) >= 5000 ? "var(--color-accent-amber)" : "var(--color-text-secondary)",
          fontWeight: (print.size ?? 0) >= 5000 ? 700 : 400,
        }}
      >
        {(print.size ?? 0).toLocaleString()}
      </span>
      <span style={{ ...styles.tapeTd, flex: 0.8, textAlign: "right", color: "var(--color-text-muted)", fontSize: 9 }}>
        {print.exchange ?? "—"}
      </span>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  headerRow: {
    display: "flex",
    padding: "3px 8px",
    borderBottom: "1px solid var(--color-bg-separator)",
    background: "var(--color-bg-elevated)",
  },
  col: {
    fontSize: 8,
    fontWeight: 600,
    letterSpacing: "0.06em",
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
    textTransform: "uppercase",
    textAlign: "left" as const,
  },
  tape: {
    overflowY: "auto" as const,
    maxHeight: 340,
    fontFamily: "var(--font-mono)",
  },
  empty: {
    textAlign: "center" as const,
    padding: "16px",
    fontSize: 11,
    color: "var(--color-text-muted)",
  },
  tapeRow: {
    display: "flex",
    padding: "1px 8px",
    borderBottom: "1px solid rgba(255,255,255,0.02)",
    transition: "background 0.2s",
  },
  tapeTd: {
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    textAlign: "left" as const,
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
  },
  ctrlBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 10,
    color: "var(--color-text-muted)",
    padding: "0 2px",
    lineHeight: 1,
  },
  symbolInput: {
    width: 60,
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
