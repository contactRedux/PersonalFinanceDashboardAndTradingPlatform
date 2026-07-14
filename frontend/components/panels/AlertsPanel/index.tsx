"use client";

/**
 * AlertsPanel — full CRUD alert manager with real-time notification feed.
 *
 * Features:
 *  - List all user alerts with status badges
 *  - Create new alert (type / symbol / threshold)
 *  - Re-arm / acknowledge / delete
 *  - WebSocket subscription for real-time triggered alert toasts
 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import {
  listAlerts,
  createAlert,
  deleteAlert,
  acknowledgeAlert,
  getAlertTypes,
  type Alert,
  type AlertType,
} from "@/lib/api/screener";
import { WS_URLS } from "@/lib/api/websocket";

interface AlertsPanelProps {
  panelId?: string;
}

interface WsAlertEvent {
  type: string;
  alert_id: string;
  message: string;
  label: string;
  symbol: string | null;
  triggered_at: string;
}

type Tab = "list" | "create";

export function AlertsPanel({ panelId = "alerts" }: AlertsPanelProps) {
  const [tab, setTab] = useState<Tab>("list");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertTypes, setAlertTypes] = useState<AlertType[]>([]);
  const [loading, setLoading] = useState(true);
  const [notifications, setNotifications] = useState<WsAlertEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // Form state
  const [form, setForm] = useState({
    symbol: "",
    alert_type: "price_above",
    threshold: "",
    label: "",
  });
  const [creating, setCreating] = useState(false);

  const loadAlerts = useCallback(async () => {
    try {
      const [alertsRes, typesRes] = await Promise.all([listAlerts(), getAlertTypes()]);
      setAlerts(alertsRes.alerts);
      setAlertTypes(typesRes.types);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAlerts();

    // Connect to alerts WebSocket for real-time notifications
    const url = WS_URLS.alerts();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data as string) as WsAlertEvent;
        if (data.type === "alert_triggered") {
          setNotifications((prev) => [data, ...prev].slice(0, 5));
          void loadAlerts(); // refresh list
        }
      } catch { /* ignore */ }
    };

    return () => { ws.close(); };
  }, [loadAlerts]);

  const handleCreate = useCallback(async () => {
    if (!form.alert_type || !form.threshold) return;
    setCreating(true);
    try {
      await createAlert({
        symbol: form.symbol.trim().toUpperCase() || undefined,
        alert_type: form.alert_type,
        threshold: parseFloat(form.threshold),
        label: form.label || undefined,
      });
      setForm({ symbol: "", alert_type: "price_above", threshold: "", label: "" });
      setTab("list");
      await loadAlerts();
    } catch { /* ignore */ }
    finally { setCreating(false); }
  }, [form, loadAlerts]);

  const handleDelete = useCallback(async (id: string) => {
    await deleteAlert(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const handleAck = useCallback(async (id: string) => {
    const updated = await acknowledgeAlert(id);
    setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
  }, []);

  const toolbar = (
    <div style={{ display: "flex", gap: 2 }}>
      {(["list", "create"] as Tab[]).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
          onClick={() => setTab(t)}
        >
          {t === "list" ? "MY ALERTS" : "+ NEW"}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="Alert Manager" toolbar={toolbar}>
      {/* Triggered notifications banner */}
      <AnimatePresence>
        {notifications.map((n) => (
          <motion.div
            key={n.triggered_at}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            style={styles.notification}
          >
            <span style={styles.notifBell}>🔔</span>
            <span style={styles.notifMsg}>{n.message}</span>
            <button
              style={styles.notifClose}
              onClick={() => setNotifications((prev) => prev.filter((x) => x.triggered_at !== n.triggered_at))}
            >×</button>
          </motion.div>
        ))}
      </AnimatePresence>

      {loading && <div style={styles.stateMsg}>Loading alerts…</div>}

      {!loading && tab === "list" && (
        <motion.div key="list" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.12 }}>
          {alerts.length === 0 && (
            <div style={styles.stateMsg}>No alerts — click + NEW to create one</div>
          )}
          {alerts.map((alert) => (
            <AlertRow
              key={alert.id}
              alert={alert}
              onDelete={handleDelete}
              onAck={handleAck}
            />
          ))}
        </motion.div>
      )}

      {!loading && tab === "create" && (
        <motion.div
          key="create"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.12 }}
          style={{ padding: "8px 10px" }}
        >
          <CreateForm
            form={form}
            alertTypes={alertTypes}
            creating={creating}
            onChange={(k, v) => setForm((f) => ({ ...f, [k]: v }))}
            onSubmit={handleCreate}
          />
        </motion.div>
      )}
    </Panel>
  );
}

function AlertRow({
  alert,
  onDelete,
  onAck,
}: {
  alert: Alert;
  onDelete: (id: string) => void;
  onAck: (id: string) => void;
}) {
  const statusColor = alert.status === "triggered"
    ? "var(--color-accent-amber)"
    : alert.status === "acknowledged"
      ? "var(--color-text-muted)"
      : "var(--color-accent-green)";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={styles.alertRow}
    >
      <div style={styles.alertLeft}>
        <span style={{ ...styles.statusDot, background: statusColor }} />
        <div>
          <div style={styles.alertLabel}>{alert.label}</div>
          <div style={styles.alertMeta}>
            {alert.symbol && <span style={styles.alertSymbol}>{alert.symbol} · </span>}
            <span style={{ color: "var(--color-text-muted)" }}>
              {alert.alert_type.replace(/_/g, " ")} {alert.threshold}
            </span>
          </div>
        </div>
      </div>
      <div style={styles.alertActions}>
        {alert.status === "triggered" && (
          <button style={styles.ackBtn} onClick={() => onAck(alert.id)}>ACK</button>
        )}
        <button style={styles.delBtn} onClick={() => onDelete(alert.id)} aria-label="Delete alert">×</button>
      </div>
    </motion.div>
  );
}

function CreateForm({
  form,
  alertTypes,
  creating,
  onChange,
  onSubmit,
}: {
  form: { symbol: string; alert_type: string; threshold: string; label: string };
  alertTypes: AlertType[];
  creating: boolean;
  onChange: (key: string, value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column" as const, gap: 8 }}>
      {[
        { key: "symbol",     label: "Symbol (optional)",   type: "text",   placeholder: "AAPL" },
        { key: "threshold",  label: "Threshold Value",     type: "number", placeholder: "200.00" },
        { key: "label",      label: "Label (optional)",    type: "text",   placeholder: "AAPL above $200" },
      ].map(({ key, label, type, placeholder }) => (
        <div key={key} style={styles.formRow}>
          <label style={styles.formLabel}>{label}</label>
          <input
            type={type}
            value={form[key as keyof typeof form]}
            placeholder={placeholder}
            onChange={(e) => onChange(key, e.target.value)}
            style={styles.formInput}
          />
        </div>
      ))}
      <div style={styles.formRow}>
        <label style={styles.formLabel}>Alert Type</label>
        <select
          value={form.alert_type}
          onChange={(e) => onChange("alert_type", e.target.value)}
          style={styles.formInput}
        >
          {alertTypes.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>
      <button style={styles.submitBtn} onClick={onSubmit} disabled={creating}>
        {creating ? "CREATING…" : "CREATE ALERT"}
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  tab: { padding: "2px 6px", background: "none", border: "1px solid transparent", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", cursor: "pointer" },
  tabActive: { background: "var(--color-accent-amber-bg)", border: "1px solid rgba(245,158,11,0.3)", color: "var(--color-accent-amber)" },
  stateMsg: { textAlign: "center" as const, padding: "16px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  notification: { display: "flex", alignItems: "center", gap: 6, padding: "4px 8px", background: "rgba(245,158,11,0.12)", borderBottom: "1px solid rgba(245,158,11,0.2)" },
  notifBell: { fontSize: 10 },
  notifMsg: { flex: 1, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-accent-amber)" },
  notifClose: { background: "none", border: "none", cursor: "pointer", color: "var(--color-text-muted)", fontSize: 13 },
  alertRow: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 10px", borderBottom: "1px solid rgba(255,255,255,0.04)" },
  alertLeft: { display: "flex", alignItems: "center", gap: 8 },
  statusDot: { width: 6, height: 6, borderRadius: "50%", display: "inline-block", flexShrink: 0 },
  alertLabel: { fontSize: 11, color: "var(--color-text-primary)", fontFamily: "var(--font-sans)" },
  alertMeta: { fontSize: 9, marginTop: 1 },
  alertSymbol: { color: "var(--color-accent-blue)", fontFamily: "var(--font-mono)", fontWeight: 700 },
  alertActions: { display: "flex", gap: 4 },
  ackBtn: { padding: "1px 5px", background: "var(--color-accent-amber-bg)", border: "1px solid rgba(245,158,11,0.3)", borderRadius: 3, fontSize: 8, fontFamily: "var(--font-mono)", color: "var(--color-accent-amber)", cursor: "pointer" },
  delBtn: { background: "none", border: "none", cursor: "pointer", color: "var(--color-text-muted)", fontSize: 14, padding: "0 2px" },
  formRow: { display: "flex", flexDirection: "column" as const, gap: 3 },
  formLabel: { fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" },
  formInput: { background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 11, fontFamily: "var(--font-mono)", padding: "4px 7px", outline: "none" },
  submitBtn: { padding: "5px 12px", background: "var(--color-accent-green-bg)", border: "1px solid rgba(0,208,132,0.3)", borderRadius: 3, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-accent-green)", cursor: "pointer", letterSpacing: "0.06em", marginTop: 4 },
};
