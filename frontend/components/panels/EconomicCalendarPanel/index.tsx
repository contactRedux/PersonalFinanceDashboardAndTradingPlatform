"use client";

/**
 * EconomicCalendarPanel — upcoming economic events with impact filter.
 *
 * Features:
 *  - High / Medium / Low impact filter toggles
 *  - Events grouped by date
 *  - Impact dot coloring (red = high, amber = medium, gray = low)
 *  - Countdown to next high-impact event
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import { getCalendarEvents, type CalendarEvent } from "@/lib/api/screener";

interface EconomicCalendarPanelProps { panelId?: string; }

const IMPACT_COLOR: Record<string, string> = {
  high:   "var(--color-accent-red)",
  medium: "var(--color-accent-amber)",
  low:    "var(--color-text-muted)",
};

export function EconomicCalendarPanel({ panelId = "calendar" }: EconomicCalendarPanelProps) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ high: true, medium: true, low: false });

  const load = useCallback(async () => {
    try {
      const res = await getCalendarEvents();
      setEvents(res.events);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const activeImpacts = Object.entries(filter)
    .filter(([, on]) => on)
    .map(([k]) => k);

  const visible = events.filter((e) => activeImpacts.includes(e.impact));

  // Group by date
  const byDate = visible.reduce<Record<string, CalendarEvent[]>>((acc, ev) => {
    (acc[ev.date] = acc[ev.date] ?? []).push(ev);
    return acc;
  }, {});

  // Next high-impact event countdown
  const nextHighImpact = events.find((e) => e.impact === "high" && e.is_upcoming);
  const daysUntilNext = nextHighImpact?.days_until;

  const toolbar = (
    <div style={{ display: "flex", gap: 3 }}>
      {(["high", "medium", "low"] as const).map((level) => (
        <button
          key={level}
          style={{
            ...styles.filterBtn,
            background: filter[level] ? `${IMPACT_COLOR[level]}20` : "none",
            borderColor: filter[level] ? IMPACT_COLOR[level] : "var(--color-bg-border)",
            color: filter[level] ? IMPACT_COLOR[level] : "var(--color-text-muted)",
          }}
          onClick={() => setFilter((f) => ({ ...f, [level]: !f[level] }))}
        >
          {level.toUpperCase()}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="Economic Calendar" toolbar={toolbar}>
      {/* Next high-impact event */}
      {nextHighImpact && daysUntilNext != null && (
        <div style={styles.nextEventBanner}>
          <span style={styles.nextLabel}>NEXT HIGH IMPACT</span>
          <span style={styles.nextEvent}>{nextHighImpact.event}</span>
          <span style={styles.nextDays}>
            {daysUntilNext === 0 ? "TODAY" : daysUntilNext === 1 ? "TOMORROW" : `${daysUntilNext}D`}
          </span>
        </div>
      )}

      {loading && <div style={styles.stateMsg}>Loading calendar…</div>}

      {!loading && visible.length === 0 && (
        <div style={styles.stateMsg}>No events match current filter</div>
      )}

      {/* Events grouped by date */}
      {!loading && Object.entries(byDate).map(([date, dateEvents]) => (
        <motion.div key={date} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.1 }}>
          <div style={styles.dateHeader}>
            {new Date(date + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
          </div>
          {dateEvents.map((ev) => (
            <div key={ev.id} style={styles.eventRow}>
              {/* Impact indicator */}
              <span style={{ ...styles.impactDot, background: IMPACT_COLOR[ev.impact] ?? "var(--color-text-muted)" }} />

              {/* Time */}
              <span style={styles.eventTime}>{ev.time}</span>

              {/* Event name */}
              <span style={styles.eventName}>{ev.event}</span>

              {/* Data columns */}
              <div style={styles.dataGroup}>
                <DataCell label="Prev" value={ev.previous} />
                <DataCell label="Fcst" value={ev.forecast} highlight />
                <DataCell label="Actual" value={ev.actual} actual />
              </div>
            </div>
          ))}
        </motion.div>
      ))}
    </Panel>
  );
}

function DataCell({
  label,
  value,
  highlight = false,
  actual = false,
}: {
  label: string;
  value: string | null;
  highlight?: boolean;
  actual?: boolean;
}) {
  return (
    <div style={styles.dataCell}>
      <span style={styles.dataCellLabel}>{label}</span>
      <span style={{
        ...styles.dataCellValue,
        color: actual
          ? value != null ? "var(--color-accent-blue)" : "var(--color-text-muted)"
          : highlight
            ? "var(--color-accent-amber)"
            : "var(--color-text-secondary)",
      }}>
        {value ?? "—"}
      </span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  stateMsg:       { textAlign: "center" as const, padding: "12px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  filterBtn:      { padding: "1px 5px", border: "1px solid", borderRadius: 3, fontSize: 8, fontFamily: "var(--font-mono)", cursor: "pointer", letterSpacing: "0.05em" },
  nextEventBanner:{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", background: "rgba(239,68,68,0.08)", borderBottom: "1px solid rgba(239,68,68,0.15)" },
  nextLabel:      { fontSize: 8, color: "var(--color-accent-red)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" },
  nextEvent:      { flex: 1, fontSize: 10, color: "var(--color-text-primary)", fontFamily: "var(--font-sans)" },
  nextDays:       { fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--color-accent-red)" },
  dateHeader:     { padding: "3px 10px", fontSize: 9, fontWeight: 700, color: "var(--color-accent-blue)", fontFamily: "var(--font-mono)", background: "var(--color-bg-elevated)", borderBottom: "1px solid var(--color-bg-separator)", letterSpacing: "0.06em" },
  eventRow:       { display: "flex", alignItems: "center", gap: 6, padding: "3px 10px", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  impactDot:      { width: 5, height: 5, borderRadius: "50%", display: "inline-block", flexShrink: 0 },
  eventTime:      { width: 36, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", flexShrink: 0 },
  eventName:      { flex: 1, fontSize: 10, color: "var(--color-text-primary)", fontFamily: "var(--font-sans)" },
  dataGroup:      { display: "flex", gap: 8, flexShrink: 0 },
  dataCell:       { display: "flex", flexDirection: "column" as const, alignItems: "flex-end", minWidth: 40 },
  dataCellLabel:  { fontSize: 7, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" },
  dataCellValue:  { fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 },
};
