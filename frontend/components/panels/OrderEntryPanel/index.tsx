"use client";

/**
 * OrderEntryPanel — paper-trading order entry form.
 *
 * Features:
 *   - Market / Limit / Stop / Stop-Limit order types
 *   - Buy / Sell side with color indication
 *   - Real-time symbol input, quantity, limit price, stop price
 *   - Time-in-force selector (day, gtc, ioc, fok)
 *   - Live order status updates via WebSocket feed
 *   - Recent orders list (last 10)
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Panel } from "@/components/layout/Panel";
import { formatCurrency } from "@/lib/formatters";

interface Order {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  order_type: string;
  quantity: number;
  status: string;
  filled_qty: number;
  filled_avg_price: number | null;
  limit_price: number | null;
  created_at: string;
}

type OrderType = "market" | "limit" | "stop" | "stop_limit";
type TimeInForce = "day" | "gtc" | "ioc" | "fok";

interface OrderEntryPanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

export function OrderEntryPanel({
  panelId = "order-entry",
  defaultSymbol = "AAPL",
}: OrderEntryPanelProps) {
  // Form state
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [quantity, setQuantity] = useState("100");
  const [limitPrice, setLimitPrice] = useState("");
  const [stopPrice, setStopPrice] = useState("");
  const [tif, setTif] = useState<TimeInForce>("day");

  // Order management
  const [orders, setOrders] = useState<Order[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Tab
  const [tab, setTab] = useState<"entry" | "orders">("entry");

  // Load recent orders
  const loadOrders = useCallback(async () => {
    try {
      const { apiRequest } = await import("@/lib/api/client");
      const data = await apiRequest<{ orders: Order[] }>("/api/v1/orders");
      setOrders(data.orders.slice(0, 10));
    } catch {
      // Gracefully degrade if orders endpoint unavailable
    }
  }, []);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  // WebSocket order status updates
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    const token = typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null;
    if (!token) return;
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const ws = new WebSocket(`${wsBase}/ws/orders?token=${token}`);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string) as { type: string; order?: Order };
        if (msg.type === "order_update" && msg.order) {
          setOrders((prev) => {
            const idx = prev.findIndex((o) => o.id === msg.order!.id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = msg.order!;
              return next;
            }
            return [msg.order!, ...prev].slice(0, 10);
          });
        }
      } catch {
        // ignore malformed WS messages
      }
    };
    return () => ws.close();
  }, []);

  const handleSubmit = useCallback(async () => {
    const qty = parseFloat(quantity);
    if (!symbol || isNaN(qty) || qty <= 0) {
      setSubmitError("Symbol and valid quantity are required.");
      return;
    }
    if ((orderType === "limit" || orderType === "stop_limit") && !limitPrice) {
      setSubmitError("Limit price required for limit orders.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      const { apiRequest } = await import("@/lib/api/client");
      const payload: Record<string, unknown> = {
        symbol: symbol.toUpperCase(),
        side,
        order_type: orderType,
        quantity: qty,
        time_in_force: tif,
      };
      if (limitPrice) payload.limit_price = parseFloat(limitPrice);
      if (stopPrice) payload.stop_price = parseFloat(stopPrice);

      const order = await apiRequest<Order>("/api/v1/orders", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setOrders((prev) => [order, ...prev].slice(0, 10));
      setSubmitSuccess(
        `${side.toUpperCase()} ${qty} ${symbol.toUpperCase()} — ${order.status}`
      );
      // Reset quantity after fill
      if (order.status === "filled") setQuantity("100");
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Order failed.");
    } finally {
      setSubmitting(false);
    }
  }, [symbol, side, orderType, quantity, limitPrice, stopPrice, tif]);

  const showLimitPrice = orderType === "limit" || orderType === "stop_limit";
  const showStopPrice = orderType === "stop" || orderType === "stop_limit";

  const toolbar = (
    <div style={styles.tabs}>
      {(["entry", "orders"] as const).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
          onClick={() => {
            setTab(t);
            if (t === "orders") void loadOrders();
          }}
        >
          {t === "entry" ? "ORDER ENTRY" : "MY ORDERS"}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="ORDER ENTRY" toolbar={toolbar}>
      {tab === "entry" && (
        <div style={styles.form}>
          {/* Symbol */}
          <FieldRow label="Symbol">
            <input
              style={{ ...styles.input, textTransform: "uppercase" }}
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="AAPL"
              aria-label="Symbol"
            />
          </FieldRow>

          {/* Side */}
          <FieldRow label="Side">
            <div style={styles.btnGroup}>
              {(["buy", "sell"] as const).map((s) => (
                <button
                  key={s}
                  style={{
                    ...styles.sideBtn,
                    ...(side === s
                      ? s === "buy"
                        ? styles.buyActive
                        : styles.sellActive
                      : {}),
                  }}
                  onClick={() => setSide(s)}
                  aria-label={s.toUpperCase()}
                >
                  {s.toUpperCase()}
                </button>
              ))}
            </div>
          </FieldRow>

          {/* Order type */}
          <FieldRow label="Type">
            <select
              style={styles.select}
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as OrderType)}
              aria-label="Order type"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
              <option value="stop_limit">Stop Limit</option>
            </select>
          </FieldRow>

          {/* Quantity */}
          <FieldRow label="Quantity">
            <input
              style={styles.input}
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="100"
              aria-label="Quantity"
            />
          </FieldRow>

          {/* Limit price */}
          {showLimitPrice && (
            <FieldRow label="Limit $">
              <input
                style={styles.input}
                type="number"
                step="0.01"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                placeholder="150.00"
                aria-label="Limit price"
              />
            </FieldRow>
          )}

          {/* Stop price */}
          {showStopPrice && (
            <FieldRow label="Stop $">
              <input
                style={styles.input}
                type="number"
                step="0.01"
                value={stopPrice}
                onChange={(e) => setStopPrice(e.target.value)}
                placeholder="145.00"
                aria-label="Stop price"
              />
            </FieldRow>
          )}

          {/* Time in force */}
          <FieldRow label="TIF">
            <select
              style={styles.select}
              value={tif}
              onChange={(e) => setTif(e.target.value as TimeInForce)}
              aria-label="Time in force"
            >
              <option value="day">Day</option>
              <option value="gtc">GTC</option>
              <option value="ioc">IOC</option>
              <option value="fok">FOK</option>
            </select>
          </FieldRow>

          {/* Submit */}
          <div style={styles.submitRow}>
            <button
              style={{
                ...styles.submitBtn,
                background: side === "buy" ? "var(--color-accent-green)" : "var(--color-accent-red)",
                opacity: submitting ? 0.6 : 1,
              }}
              onClick={() => void handleSubmit()}
              disabled={submitting}
              aria-label={`${side === "buy" ? "Buy" : "Sell"} ${symbol}`}
            >
              {submitting
                ? "SUBMITTING…"
                : `${side === "buy" ? "BUY" : "SELL"} ${symbol}`}
            </button>
          </div>

          {/* Feedback */}
          {submitError && (
            <div style={styles.errorMsg}>{submitError}</div>
          )}
          {submitSuccess && (
            <div style={styles.successMsg}>{submitSuccess}</div>
          )}

          {/* Paper trading disclaimer */}
          <div style={styles.disclaimer}>
            ⚠ Paper trading — no real capital at risk
          </div>
        </div>
      )}

      {tab === "orders" && (
        <OrdersTable orders={orders} onRefresh={() => void loadOrders()} />
      )}
    </Panel>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={styles.fieldRow}>
      <span style={styles.fieldLabel}>{label}</span>
      {children}
    </div>
  );
}

function OrdersTable({
  orders,
  onRefresh,
}: {
  orders: Order[];
  onRefresh: () => void;
}) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", padding: "4px 8px" }}>
        <button style={styles.refreshBtn} onClick={onRefresh}>
          ↺ Refresh
        </button>
      </div>
      {orders.length === 0 ? (
        <div style={styles.empty}>No orders yet</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              {["Symbol", "Side", "Type", "Qty", "Filled", "Avg Price", "Status"].map((h) => (
                <th key={h} style={styles.th}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} style={styles.tr}>
                <td style={{ ...styles.td, fontWeight: 700, color: "var(--color-accent-blue)" }}>
                  {o.symbol}
                </td>
                <td
                  style={{
                    ...styles.td,
                    color: o.side === "buy"
                      ? "var(--color-accent-green)"
                      : "var(--color-accent-red)",
                    textTransform: "uppercase",
                  }}
                >
                  {o.side}
                </td>
                <td style={styles.td}>{o.order_type}</td>
                <td style={styles.td}>{o.quantity}</td>
                <td style={styles.td}>{o.filled_qty}</td>
                <td style={styles.td}>
                  {o.filled_avg_price != null ? formatCurrency(o.filled_avg_price) : "—"}
                </td>
                <td style={{ ...styles.td, ...statusStyle(o.status) }}>{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function statusStyle(status: string): React.CSSProperties {
  switch (status) {
    case "filled":
      return { color: "var(--color-accent-green)" };
    case "cancelled":
    case "rejected":
      return { color: "var(--color-accent-red)" };
    case "partially_filled":
      return { color: "var(--color-accent-amber)" };
    default:
      return { color: "var(--color-text-secondary)" };
  }
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  form: { padding: "6px 8px" },
  fieldRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  fieldLabel: {
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    minWidth: 60,
    letterSpacing: "0.04em",
  },
  input: {
    flex: 1,
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "4px 7px",
    fontSize: 11,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    outline: "none",
    width: "100%",
  },
  select: {
    flex: 1,
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "4px 7px",
    fontSize: 11,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    outline: "none",
    width: "100%",
    cursor: "pointer",
  },
  btnGroup: { display: "flex", gap: 4, flex: 1 },
  sideBtn: {
    flex: 1,
    padding: "4px 0",
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    color: "var(--color-text-secondary)",
    cursor: "pointer",
    letterSpacing: "0.06em",
  },
  buyActive: {
    background: "var(--color-accent-green-bg)",
    border: "1px solid var(--color-accent-green)",
    color: "var(--color-accent-green)",
  },
  sellActive: {
    background: "rgba(239,68,68,0.12)",
    border: "1px solid var(--color-accent-red)",
    color: "var(--color-accent-red)",
  },
  submitRow: { marginTop: 12, marginBottom: 6 },
  submitBtn: {
    width: "100%",
    padding: "8px 0",
    border: "none",
    borderRadius: 4,
    fontSize: 12,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    color: "#fff",
    cursor: "pointer",
    letterSpacing: "0.08em",
  },
  errorMsg: {
    fontSize: 10,
    color: "var(--color-accent-red)",
    fontFamily: "var(--font-mono)",
    padding: "4px 0",
    textAlign: "center" as const,
  },
  successMsg: {
    fontSize: 10,
    color: "var(--color-accent-green)",
    fontFamily: "var(--font-mono)",
    padding: "4px 0",
    textAlign: "center" as const,
  },
  disclaimer: {
    fontSize: 9,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
    textAlign: "center" as const,
    marginTop: 6,
    opacity: 0.6,
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 10 },
  th: {
    padding: "4px 8px",
    fontSize: 8,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "var(--color-text-muted)",
    borderBottom: "1px solid var(--color-bg-separator)",
    fontFamily: "var(--font-mono)",
    textAlign: "right" as const,
  },
  td: {
    padding: "3px 8px",
    textAlign: "right" as const,
    fontFamily: "var(--font-mono)",
    borderBottom: "1px solid rgba(255,255,255,0.03)",
  },
  tr: {},
  tabs: { display: "flex", gap: 2 },
  tab: {
    padding: "2px 6px",
    background: "none",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
    letterSpacing: "0.04em",
  },
  tabActive: {
    background: "var(--color-accent-blue-bg)",
    border: "1px solid rgba(14,165,233,0.3)",
    color: "var(--color-accent-blue)",
  },
  refreshBtn: {
    background: "none",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "2px 7px",
    fontSize: 9,
    color: "var(--color-text-muted)",
    cursor: "pointer",
    fontFamily: "var(--font-mono)",
  },
  empty: {
    textAlign: "center" as const,
    padding: 16,
    fontSize: 11,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
};
