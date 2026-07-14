"use client";

/**
 * StrategyBuilderPanel — drag-and-drop strategy composer.
 *
 * Users drag node types from the palette onto a canvas to compose entry/exit
 * logic. The graph serializes to a JSON config sent to POST /api/v1/backtest/run
 * using DynamicStrategy on the backend.
 *
 * Node palette:
 *   Indicator nodes: RSI, SMA, EMA, MACD
 *   Comparator nodes: <, >, crosses above, crosses below
 *   Logic nodes: AND, OR
 *   Action nodes: BUY (entry), SELL (entry)
 */

import React, { useCallback, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Panel } from "@/components/layout/Panel";

// ─── Custom node renderers ────────────────────────────────────────────────────

function IndicatorNode({ data }: { data: Record<string, string> }) {
  return (
    <div style={nodeStyles.indicator}>
      <div style={nodeStyles.nodeTitle}>📈 {data.label}</div>
      {data.period && <div style={nodeStyles.nodeParam}>period={data.period}</div>}
    </div>
  );
}

function ComparatorNode({ data }: { data: Record<string, string> }) {
  return (
    <div style={nodeStyles.comparator}>
      <div style={nodeStyles.nodeTitle}>{data.label}</div>
      {data.value !== undefined && <div style={nodeStyles.nodeParam}>vs {data.value}</div>}
    </div>
  );
}

function LogicNode({ data }: { data: Record<string, string> }) {
  return (
    <div style={nodeStyles.logic}>
      <div style={nodeStyles.nodeTitle}>{data.label}</div>
    </div>
  );
}

function EntryNode({ data }: { data: Record<string, string> }) {
  const isBuy = data.side === "buy";
  return (
    <div style={{ ...nodeStyles.action, borderColor: isBuy ? "#22c55e" : "#ef4444" }}>
      <div style={nodeStyles.nodeTitle}>{isBuy ? "▲ BUY" : "▼ SELL"}</div>
    </div>
  );
}

const nodeTypes: NodeTypes = {
  indicator: IndicatorNode as NodeTypes[string],
  comparator: ComparatorNode as NodeTypes[string],
  logic: LogicNode as NodeTypes[string],
  entry: EntryNode as NodeTypes[string],
};

// ─── Palette config ───────────────────────────────────────────────────────────

const PALETTE: Array<{
  group: string;
  items: Array<{ label: string; type: string; data: Record<string, unknown> }>;
}> = [
  {
    group: "Indicators",
    items: [
      { label: "RSI(14)", type: "indicator", data: { label: "RSI", indicator: "rsi", period: "14" } },
      { label: "SMA(20)", type: "indicator", data: { label: "SMA", indicator: "sma", period: "20" } },
      { label: "EMA(50)", type: "indicator", data: { label: "EMA", indicator: "ema", period: "50" } },
      { label: "MACD", type: "indicator", data: { label: "MACD", indicator: "macd", fast: "12", slow: "26", signal: "9" } },
    ],
  },
  {
    group: "Comparators",
    items: [
      { label: "< value", type: "comparator", data: { label: "<", op: "lt", value: "30" } },
      { label: "> value", type: "comparator", data: { label: ">", op: "gt", value: "70" } },
      { label: "Crosses ↑", type: "comparator", data: { label: "Crosses ↑", op: "crosses_above", value: "50" } },
      { label: "Crosses ↓", type: "comparator", data: { label: "Crosses ↓", op: "crosses_below", value: "50" } },
    ],
  },
  {
    group: "Logic",
    items: [
      { label: "AND", type: "logic", data: { label: "AND", op: "and" } },
      { label: "OR", type: "logic", data: { label: "OR", op: "or" } },
    ],
  },
  {
    group: "Actions",
    items: [
      { label: "BUY Entry", type: "entry", data: { label: "BUY", side: "buy" } },
      { label: "SELL Entry", type: "entry", data: { label: "SELL", side: "sell" } },
    ],
  },
];

// ─── Default starter graph: RSI < 30 → BUY ───────────────────────────────────

const INITIAL_NODES: Node[] = [
  { id: "n-rsi", type: "indicator", position: { x: 60, y: 80 }, data: { label: "RSI", indicator: "rsi", period: "14" } },
  { id: "n-lt",  type: "comparator", position: { x: 240, y: 80 }, data: { label: "<", op: "lt", value: "30" } },
  { id: "n-buy", type: "entry", position: { x: 420, y: 80 }, data: { label: "BUY", side: "buy" } },
];

const INITIAL_EDGES: Edge[] = [
  { id: "e1", source: "n-rsi", target: "n-lt" },
  { id: "e2", source: "n-lt", target: "n-buy" },
];

// ─── Panel ────────────────────────────────────────────────────────────────────

interface StrategyBuilderPanelProps {
  panelId?: string;
}

export function StrategyBuilderPanel({ panelId = "strategy-builder" }: StrategyBuilderPanelProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(INITIAL_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES);
  const [strategyName, setStrategyName] = useState("My Strategy");
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [nodeCounter, setNodeCounter] = useState(10);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const addNode = useCallback(
    (type: string, data: Record<string, unknown>) => {
      const id = `n-${nodeCounter}`;
      const newNode: Node = {
        id,
        type,
        position: { x: 80 + (nodeCounter % 5) * 160, y: 80 + Math.floor(nodeCounter / 5) * 120 },
        data: { ...data },
      };
      setNodes((nds) => [...nds, newNode]);
      setNodeCounter((c) => c + 1);
    },
    [nodeCounter, setNodes]
  );

  const buildConfig = useCallback(() => ({
    nodes: nodes.map((n) => ({ id: n.id, type: n.type, data: n.data })),
    edges: edges.map((e) => ({ source: e.source, target: e.target })),
  }), [nodes, edges]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveStatus(null);
    try {
      const { apiRequest } = await import("@/lib/api/client");
      await apiRequest("/api/v1/strategies", {
        method: "POST",
        body: JSON.stringify({
          name: strategyName,
          description: "",
          config: buildConfig(),
        }),
      });
      setSaveStatus("Saved ✓");
    } catch {
      setSaveStatus("Save failed");
    } finally {
      setSaving(false);
    }
  }, [strategyName, buildConfig]);

  const handleRun = useCallback(async () => {
    setRunning(true);
    setRunResult(null);
    try {
      const { apiRequest } = await import("@/lib/api/client");
      const result = await apiRequest<{ total_return_pct: number; total_trades: number; sharpe_ratio: number }>(
        "/api/v1/backtest/run",
        {
          method: "POST",
          body: JSON.stringify({
            symbol: "AAPL",
            strategy: "dynamic",
            params: { config: buildConfig() },
            start: "2022-01-01",
            end: "2024-01-01",
          }),
        }
      );
      setRunResult(
        `Return: ${result.total_return_pct.toFixed(2)}% | Sharpe: ${result.sharpe_ratio.toFixed(2)} | Trades: ${result.total_trades}`
      );
    } catch {
      setRunResult("Backtest failed — check console");
    } finally {
      setRunning(false);
    }
  }, [buildConfig]);

  const toolbar = (
    <div style={styles.toolbar}>
      <input
        style={styles.nameInput}
        value={strategyName}
        onChange={(e) => setStrategyName(e.target.value)}
        placeholder="Strategy name"
        aria-label="Strategy name"
      />
      <button
        style={styles.saveBtn}
        onClick={() => void handleSave()}
        disabled={saving}
        aria-label="Save strategy"
      >
        {saving ? "Saving…" : "Save"}
      </button>
      <button
        style={styles.runBtn}
        onClick={() => void handleRun()}
        disabled={running}
        aria-label="Run backtest"
      >
        {running ? "Running…" : "▶ Run"}
      </button>
    </div>
  );

  return (
    <Panel id={panelId} title="STRATEGY BUILDER" toolbar={toolbar}>
      <div style={styles.container}>
        {/* Palette */}
        <div style={styles.palette}>
          {PALETTE.map((group) => (
            <div key={group.group}>
              <div style={styles.paletteGroup}>{group.group}</div>
              {group.items.map((item) => (
                <button
                  key={item.label}
                  style={styles.paletteItem}
                  onClick={() => addNode(item.type, item.data)}
                  aria-label={`Add ${item.label} node`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </div>

        {/* Canvas */}
        <div style={styles.canvas}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background variant={BackgroundVariant.Dots} gap={20} color="#2a2a2e" />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                if (n.type === "indicator") return "#3b82f6";
                if (n.type === "comparator") return "#a855f7";
                if (n.type === "logic") return "#f59e0b";
                return n.data?.side === "sell" ? "#ef4444" : "#22c55e";
              }}
              style={{ background: "#1a1a1e" }}
            />
          </ReactFlow>
        </div>
      </div>

      {/* Status bar */}
      {(saveStatus || runResult) && (
        <div style={styles.statusBar}>
          {saveStatus && <span style={{ color: saveStatus.includes("✓") ? "#22c55e" : "#ef4444" }}>{saveStatus}</span>}
          {runResult && <span style={{ color: "#a3e635", marginLeft: 12 }}>{runResult}</span>}
        </div>
      )}
    </Panel>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    height: 420,
    overflow: "hidden",
  },
  palette: {
    width: 130,
    minWidth: 130,
    background: "var(--color-bg-elevated)",
    borderRight: "1px solid var(--color-bg-border)",
    overflowY: "auto",
    padding: "6px 4px",
  },
  paletteGroup: {
    fontSize: 8,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-muted)",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    padding: "6px 4px 2px",
  },
  paletteItem: {
    display: "block",
    width: "100%",
    textAlign: "left",
    background: "none",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "3px 6px",
    marginBottom: 3,
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
  },
  canvas: {
    flex: 1,
    background: "#141417",
  },
  toolbar: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  nameInput: {
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "2px 6px",
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    width: 140,
    outline: "none",
  },
  saveBtn: {
    background: "none",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "2px 8px",
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
  },
  runBtn: {
    background: "var(--color-accent-green-bg)",
    border: "1px solid var(--color-accent-green)",
    borderRadius: 3,
    padding: "2px 8px",
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-accent-green)",
    cursor: "pointer",
  },
  statusBar: {
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    padding: "4px 8px",
    borderTop: "1px solid var(--color-bg-separator)",
  },
};

const nodeStyles: Record<string, React.CSSProperties> = {
  indicator: {
    background: "rgba(59,130,246,0.15)",
    border: "1px solid #3b82f6",
    borderRadius: 4,
    padding: "6px 10px",
    minWidth: 90,
  },
  comparator: {
    background: "rgba(168,85,247,0.15)",
    border: "1px solid #a855f7",
    borderRadius: 4,
    padding: "6px 10px",
    minWidth: 80,
  },
  logic: {
    background: "rgba(245,158,11,0.15)",
    border: "1px solid #f59e0b",
    borderRadius: 4,
    padding: "6px 10px",
    minWidth: 60,
  },
  action: {
    background: "rgba(34,197,94,0.12)",
    border: "1px solid #22c55e",
    borderRadius: 4,
    padding: "6px 10px",
    minWidth: 70,
  },
  nodeTitle: {
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    color: "#e2e8f0",
  },
  nodeParam: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "#94a3b8",
    marginTop: 2,
  },
};
