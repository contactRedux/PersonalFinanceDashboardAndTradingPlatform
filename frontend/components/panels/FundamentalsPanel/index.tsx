"use client";

/**
 * FundamentalsPanel — company fundamentals powered by FMP.
 *
 * Tabs:
 *   Profile     — company overview, sector, industry, description
 *   Financials  — income statement + balance sheet + cash flow (last 4 quarters)
 *   Metrics     — key metrics (EV/EBITDA, ROE, FCF yield) + DCF intrinsic value
 *   Earnings    — historical EPS beats/misses + analyst estimates
 *   Insiders    — Form 4 insider buy/sell transactions
 *   Institutions — top 13-F institutional holders
 *
 * Falls back to a "demo" state when FMP_API_KEY is not configured on the server.
 */

import React, { useState, useCallback, useEffect } from "react";
import { Panel } from "@/components/layout/Panel";
import { apiRequest } from "@/lib/api/client";

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = "profile" | "financials" | "metrics" | "earnings" | "insiders" | "institutions";

interface FundamentalsPayload {
  symbol: string;
  as_of?: string;
  note?: string;
  profile?: Record<string, unknown> | null;
  income_statement?: Record<string, unknown>[];
  balance_sheet?: Record<string, unknown>[];
  cash_flow?: Record<string, unknown>[];
  key_metrics?: Record<string, unknown>[];
  dcf?: Record<string, unknown> | null;
  earnings_history?: Record<string, unknown>[];
  analyst_estimates?: Record<string, unknown>[];
  insider_transactions?: Record<string, unknown>[];
  institutional_holders?: Record<string, unknown>[];
}

interface FundamentalsPanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

// ─── Number / currency helpers ────────────────────────────────────────────────

function fmt(v: unknown, decimals = 2): string {
  if (v == null || v === "" || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return n.toFixed(decimals);
}

function pct(v: unknown): string {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(2)}%`;
}

function ratio(v: unknown): string {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n.toFixed(2);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.kv}>
      <span style={styles.kvLabel}>{label}</span>
      <span style={styles.kvValue}>{value}</span>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return <div style={styles.sectionHeader}>{children}</div>;
}

// ─── Tab content ──────────────────────────────────────────────────────────────

function ProfileTab({ data }: { data: FundamentalsPayload }) {
  const p = (data.profile ?? {}) as Record<string, unknown>;
  return (
    <div style={styles.tabContent}>
      {p.companyName && (
        <div style={styles.companyName}>{String(p.companyName)}</div>
      )}
      <div style={styles.kvGrid}>
        <KV label="Sector" value={String(p.sector ?? "—")} />
        <KV label="Industry" value={String(p.industry ?? "—")} />
        <KV label="Exchange" value={String(p.exchangeShortName ?? "—")} />
        <KV label="Employees" value={p.fullTimeEmployees ? Number(p.fullTimeEmployees).toLocaleString() : "—"} />
        <KV label="Market Cap" value={fmt(p.mktCap)} />
        <KV label="Beta" value={ratio(p.beta)} />
        <KV label="Dividend Yield" value={pct(Number(p.lastDiv ?? 0) / Math.max(Number(p.price ?? 1), 1))} />
        <KV label="52W High" value={fmt(p["52WeekHigh"], 2)} />
        <KV label="52W Low" value={fmt(p["52WeekLow"], 2)} />
        {p.website && (
          <div style={{ ...styles.kv, gridColumn: "1 / -1" }}>
            <span style={styles.kvLabel}>Website</span>
            <a href={String(p.website)} target="_blank" rel="noopener noreferrer" style={styles.link}>
              {String(p.website)}
            </a>
          </div>
        )}
      </div>
      {p.description && (
        <div style={styles.description}>{String(p.description)}</div>
      )}
      {data.note && <div style={styles.demoNote}>{data.note}</div>}
    </div>
  );
}

function FinancialsTab({ data }: { data: FundamentalsPayload }) {
  const income = (data.income_statement ?? []).slice(0, 4);
  return (
    <div style={styles.tabContent}>
      <SectionHeader>Income Statement (Annual)</SectionHeader>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Period", "Revenue", "Gross Profit", "Net Income", "EPS"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {income.length === 0 ? (
              <tr><td colSpan={5} style={styles.emptyCell}>No data</td></tr>
            ) : (
              income.map((row, i) => (
                <tr key={i}>
                  <td style={styles.td}>{String(row.date ?? "—").slice(0, 7)}</td>
                  <td style={styles.tdNum}>{fmt(row.revenue)}</td>
                  <td style={styles.tdNum}>{fmt(row.grossProfit)}</td>
                  <td style={styles.tdNum}>{fmt(row.netIncome)}</td>
                  <td style={styles.tdNum}>{ratio(row.eps)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <SectionHeader>Balance Sheet (Latest)</SectionHeader>
      {data.balance_sheet && data.balance_sheet[0] ? (
        <div style={styles.kvGrid}>
          <KV label="Total Assets" value={fmt(data.balance_sheet[0].totalAssets)} />
          <KV label="Total Liabilities" value={fmt(data.balance_sheet[0].totalLiabilities)} />
          <KV label="Total Equity" value={fmt(data.balance_sheet[0].totalStockholdersEquity)} />
          <KV label="Cash & Equiv." value={fmt(data.balance_sheet[0].cashAndCashEquivalents)} />
          <KV label="Total Debt" value={fmt(data.balance_sheet[0].totalDebt)} />
        </div>
      ) : (
        <div style={styles.emptyCell}>No data</div>
      )}

      <SectionHeader>Cash Flow (Latest)</SectionHeader>
      {data.cash_flow && data.cash_flow[0] ? (
        <div style={styles.kvGrid}>
          <KV label="Operating CF" value={fmt(data.cash_flow[0].operatingCashFlow)} />
          <KV label="Free Cash Flow" value={fmt(data.cash_flow[0].freeCashFlow)} />
          <KV label="Capital Expenditure" value={fmt(data.cash_flow[0].capitalExpenditure)} />
          <KV label="Dividends Paid" value={fmt(data.cash_flow[0].dividendsPaid)} />
        </div>
      ) : (
        <div style={styles.emptyCell}>No data</div>
      )}
    </div>
  );
}

function MetricsTab({ data }: { data: FundamentalsPayload }) {
  const m = (data.key_metrics ?? [])[0] ?? {};
  const dcf = data.dcf ?? {};
  return (
    <div style={styles.tabContent}>
      <SectionHeader>Valuation Metrics</SectionHeader>
      <div style={styles.kvGrid}>
        <KV label="P/E Ratio" value={ratio(m.peRatio)} />
        <KV label="P/B Ratio" value={ratio(m.pbRatio)} />
        <KV label="EV / EBITDA" value={ratio(m.evToEbitda)} />
        <KV label="EV / Revenue" value={ratio(m.evToSales)} />
        <KV label="P/FCF" value={ratio(m.pfcfRatio)} />
        <KV label="Price/Sales" value={ratio(m.priceToSalesRatio)} />
      </div>

      <SectionHeader>Profitability</SectionHeader>
      <div style={styles.kvGrid}>
        <KV label="ROE" value={pct(m.roe)} />
        <KV label="ROA" value={pct(m.returnOnAssets)} />
        <KV label="ROIC" value={pct(m.roic)} />
        <KV label="Gross Margin" value={pct(m.grossProfitMargin)} />
        <KV label="Net Margin" value={pct(m.netProfitMargin)} />
        <KV label="FCF Yield" value={pct(m.freeCashFlowYield)} />
      </div>

      <SectionHeader>DCF Intrinsic Value</SectionHeader>
      <div style={styles.kvGrid}>
        <KV label="DCF Value" value={fmt(dcf.dcf, 2)} />
        <KV label="Current Price" value={fmt(dcf["Stock Price"], 2)} />
        {dcf.dcf && dcf["Stock Price"] && (
          <KV
            label="Margin of Safety"
            value={`${(((Number(dcf.dcf) - Number(dcf["Stock Price"])) / Number(dcf["Stock Price"])) * 100).toFixed(1)}%`}
          />
        )}
      </div>
    </div>
  );
}

function EarningsTab({ data }: { data: FundamentalsPayload }) {
  const history = (data.earnings_history ?? []).slice(0, 8);
  const estimates = (data.analyst_estimates ?? []).slice(0, 4);
  return (
    <div style={styles.tabContent}>
      <SectionHeader>Historical Earnings</SectionHeader>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Date", "EPS Est.", "EPS Actual", "Surprise"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {history.length === 0 ? (
              <tr><td colSpan={4} style={styles.emptyCell}>No data</td></tr>
            ) : (
              history.map((row, i) => {
                const surprise = row.epsActual != null && row.epsEstimated != null
                  ? ((Number(row.epsActual) - Number(row.epsEstimated)) / Math.abs(Number(row.epsEstimated) || 1)) * 100
                  : null;
                return (
                  <tr key={i}>
                    <td style={styles.td}>{String(row.date ?? "—").slice(0, 10)}</td>
                    <td style={styles.tdNum}>{ratio(row.epsEstimated)}</td>
                    <td style={styles.tdNum}>{ratio(row.epsActual)}</td>
                    <td style={{ ...styles.tdNum, color: surprise != null ? (surprise >= 0 ? "#00d084" : "#ef4444") : "#888" }}>
                      {surprise != null ? `${surprise > 0 ? "+" : ""}${surprise.toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <SectionHeader>Analyst Estimates (Forward)</SectionHeader>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Period", "Rev. Est.", "EPS Est.", "# Analysts"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {estimates.length === 0 ? (
              <tr><td colSpan={4} style={styles.emptyCell}>No data</td></tr>
            ) : (
              estimates.map((row, i) => (
                <tr key={i}>
                  <td style={styles.td}>{String(row.date ?? "—").slice(0, 7)}</td>
                  <td style={styles.tdNum}>{fmt(row.estimatedRevenueAvg)}</td>
                  <td style={styles.tdNum}>{ratio(row.estimatedEpsAvg)}</td>
                  <td style={styles.tdNum}>{String(row.numberAnalystEstimatedEps ?? "—")}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InsidersTab({ data }: { data: FundamentalsPayload }) {
  const transactions = (data.insider_transactions ?? []).slice(0, 20);
  return (
    <div style={styles.tabContent}>
      <SectionHeader>Insider Transactions (Form 4)</SectionHeader>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Date", "Insider", "Type", "Shares", "Price", "Value"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0 ? (
              <tr><td colSpan={6} style={styles.emptyCell}>No data</td></tr>
            ) : (
              transactions.map((row, i) => {
                const txType = String(row.transactionType ?? "").toLowerCase();
                const isBuy = txType.includes("p-purchase") || txType === "p";
                return (
                  <tr key={i}>
                    <td style={styles.td}>{String(row.transactionDate ?? "—").slice(0, 10)}</td>
                    <td style={styles.td}>{String(row.reportingName ?? "—")}</td>
                    <td style={{ ...styles.td, color: isBuy ? "#00d084" : "#ef4444", fontWeight: 600 }}>
                      {isBuy ? "BUY" : "SELL"}
                    </td>
                    <td style={styles.tdNum}>{Number(row.securitiesTransacted ?? 0).toLocaleString()}</td>
                    <td style={styles.tdNum}>{ratio(row.price)}</td>
                    <td style={styles.tdNum}>{fmt(Number(row.securitiesTransacted ?? 0) * Number(row.price ?? 0))}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InstitutionsTab({ data }: { data: FundamentalsPayload }) {
  const holders = (data.institutional_holders ?? []).slice(0, 10);
  return (
    <div style={styles.tabContent}>
      <SectionHeader>Top Institutional Holders (13-F)</SectionHeader>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["Institution", "Shares", "Value", "% Portfolio"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {holders.length === 0 ? (
              <tr><td colSpan={4} style={styles.emptyCell}>No data</td></tr>
            ) : (
              holders.map((row, i) => (
                <tr key={i}>
                  <td style={styles.td}>{String(row.holderName ?? row.holder ?? "—")}</td>
                  <td style={styles.tdNum}>{Number(row.shares ?? 0).toLocaleString()}</td>
                  <td style={styles.tdNum}>{fmt(row.value)}</td>
                  <td style={styles.tdNum}>{pct(Number(row.weightPercent ?? 0) / 100)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function FundamentalsPanel({
  panelId = "fundamentals",
  defaultSymbol = "AAPL",
}: FundamentalsPanelProps) {
  const [inputSymbol, setInputSymbol] = useState(defaultSymbol);
  const [activeSymbol, setActiveSymbol] = useState(defaultSymbol);
  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [data, setData] = useState<FundamentalsPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (sym: string) => {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await apiRequest<FundamentalsPayload>(
        `/fundamentals/${encodeURIComponent(sym.toUpperCase())}`
      );
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load fundamentals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(activeSymbol);
  }, [activeSymbol, fetchData]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const sym = inputSymbol.trim().toUpperCase();
      if (sym) setActiveSymbol(sym);
    },
    [inputSymbol]
  );

  const TABS: { id: Tab; label: string }[] = [
    { id: "profile", label: "Profile" },
    { id: "financials", label: "Financials" },
    { id: "metrics", label: "Metrics" },
    { id: "earnings", label: "Earnings" },
    { id: "insiders", label: "Insiders" },
    { id: "institutions", label: "Institutions" },
  ];

  return (
    <Panel id={panelId} title="FUNDAMENTALS">
      <div style={styles.root}>
        {/* Symbol input */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="text"
            value={inputSymbol}
            onChange={(e) => setInputSymbol(e.target.value.toUpperCase())}
            style={styles.input}
            aria-label="Fundamentals symbol"
            spellCheck={false}
            autoComplete="off"
          />
          <button type="submit" style={styles.goBtn} aria-label="Load fundamentals">
            GO
          </button>
        </form>

        {/* Tab bar */}
        <div style={styles.tabBar}>
          {TABS.map((t) => (
            <button
              key={t.id}
              style={{ ...styles.tabBtn, ...(activeTab === t.id ? styles.tabBtnActive : {}) }}
              onClick={() => setActiveTab(t.id)}
              type="button"
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={styles.body}>
          {loading && <div style={styles.status}>Loading…</div>}
          {error && <div style={styles.errorMsg}>{error}</div>}
          {!loading && !error && data && (
            <>
              {activeTab === "profile" && <ProfileTab data={data} />}
              {activeTab === "financials" && <FinancialsTab data={data} />}
              {activeTab === "metrics" && <MetricsTab data={data} />}
              {activeTab === "earnings" && <EarningsTab data={data} />}
              {activeTab === "insiders" && <InsidersTab data={data} />}
              {activeTab === "institutions" && <InstitutionsTab data={data} />}
            </>
          )}
          {!loading && !error && !data && (
            <div style={styles.status}>Enter a ticker above.</div>
          )}
        </div>
      </div>
    </Panel>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  root: {
    background: "#0a0a0a",
    color: "#e8e8e8",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    fontFamily: "'JetBrains Mono', monospace",
    boxSizing: "border-box",
    overflow: "hidden",
  },
  form: {
    display: "flex",
    gap: 6,
    alignItems: "center",
    padding: "6px 10px 4px",
    flexShrink: 0,
  },
  input: {
    flex: 1,
    background: "#111",
    border: "1px solid #2a2a2a",
    borderRadius: 3,
    padding: "3px 8px",
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e8e8e8",
    outline: "none",
    textTransform: "uppercase" as const,
  },
  goBtn: {
    padding: "3px 10px",
    background: "rgba(59,130,212,0.12)",
    border: "1px solid rgba(59,130,212,0.35)",
    borderRadius: 3,
    fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#3b82d4",
    cursor: "pointer",
    letterSpacing: "0.06em",
  },
  tabBar: {
    display: "flex",
    gap: 0,
    borderBottom: "1px solid #1e1e1e",
    flexShrink: 0,
    overflowX: "auto" as const,
    padding: "0 10px",
  },
  tabBtn: {
    background: "none",
    border: "none",
    borderBottom: "2px solid transparent",
    color: "#555",
    cursor: "pointer",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 9,
    letterSpacing: "0.06em",
    padding: "5px 8px",
    whiteSpace: "nowrap" as const,
  },
  tabBtnActive: {
    color: "#3b82d4",
    borderBottomColor: "#3b82d4",
  },
  body: {
    flex: 1,
    overflowY: "auto" as const,
    minHeight: 0,
  },
  tabContent: {
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  sectionHeader: {
    fontSize: 8,
    color: "#444",
    letterSpacing: "0.1em",
    marginTop: 6,
    marginBottom: 2,
    textTransform: "uppercase" as const,
  },
  companyName: {
    fontSize: 13,
    fontWeight: 700,
    color: "#e8e8e8",
    marginBottom: 4,
  },
  kvGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "2px 16px",
  },
  kv: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 10,
    padding: "2px 0",
    borderBottom: "1px solid #111",
  },
  kvLabel: {
    color: "#555",
  },
  kvValue: {
    color: "#ccc",
    textAlign: "right" as const,
  },
  description: {
    fontSize: 9,
    color: "#666",
    lineHeight: 1.6,
    marginTop: 4,
  },
  demoNote: {
    fontSize: 9,
    color: "#444",
    fontStyle: "italic",
    marginTop: 8,
    padding: "4px 8px",
    border: "1px solid #1e1e1e",
    borderRadius: 3,
  },
  tableWrap: {
    overflowX: "auto" as const,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: 9,
  },
  th: {
    padding: "3px 6px",
    textAlign: "left" as const,
    color: "#444",
    fontWeight: 500,
    borderBottom: "1px solid #1e1e1e",
    letterSpacing: "0.05em",
    whiteSpace: "nowrap" as const,
  },
  td: {
    padding: "3px 6px",
    color: "#aaa",
    borderBottom: "1px solid #0f0f0f",
    whiteSpace: "nowrap" as const,
  },
  tdNum: {
    padding: "3px 6px",
    color: "#aaa",
    borderBottom: "1px solid #0f0f0f",
    textAlign: "right" as const,
    fontVariantNumeric: "tabular-nums",
    whiteSpace: "nowrap" as const,
  },
  emptyCell: {
    padding: "8px 6px",
    color: "#333",
    fontStyle: "italic",
    textAlign: "center" as const,
  },
  link: {
    color: "#3b82d4",
    textDecoration: "none",
  },
  status: {
    padding: 16,
    fontSize: 11,
    color: "#444",
    textAlign: "center" as const,
  },
  errorMsg: {
    padding: "6px 10px",
    fontSize: 10,
    color: "#ef4444",
  },
};
