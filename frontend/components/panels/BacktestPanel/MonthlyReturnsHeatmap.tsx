"use client";

/**
 * MonthlyReturnsHeatmap — SVG grid showing monthly P&L returns.
 *
 * Rows = years (descending), Cols = Jan–Dec.
 * Colors: green spectrum (positive), red spectrum (negative), grey (no data).
 */

import React, { useMemo } from "react";

interface MonthlyReturnsHeatmapProps {
  equityCurve: number[];
  timestamps: string[];
}

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Compute month-over-month returns grouped by year and month (0-indexed). */
function computeMonthlyReturns(
  equityCurve: number[],
  timestamps: string[]
): Map<string, number> {
  const result = new Map<string, number>();
  if (equityCurve.length < 2 || timestamps.length < 2) return result;

  // Group equity values by year-month, keep last value of each month
  const monthEnd = new Map<string, number>();
  for (let i = 0; i < Math.min(equityCurve.length, timestamps.length); i++) {
    const d = new Date(timestamps[i]);
    if (isNaN(d.getTime())) continue;
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    monthEnd.set(key, equityCurve[i]);
  }

  // Compute return vs previous month end
  const sorted = Array.from(monthEnd.entries()).sort((a, b) =>
    a[0].localeCompare(b[0])
  );

  for (let i = 1; i < sorted.length; i++) {
    const [key, endVal] = sorted[i];
    const prevVal = sorted[i - 1][1];
    if (prevVal !== 0) {
      result.set(key, ((endVal - prevVal) / prevVal) * 100);
    }
  }

  return result;
}

function cellColor(ret: number | undefined): string {
  if (ret === undefined) return "#1a1a1a";
  if (ret === 0) return "#222";
  const intensity = Math.min(Math.abs(ret) / 10, 1); // cap at 10%
  if (ret > 0) {
    const g = Math.round(80 + intensity * 128);
    const r = Math.round(0 + (1 - intensity) * 20);
    return `rgb(${r},${g},${Math.round(50 + intensity * 20)})`;
  } else {
    const r = Math.round(100 + intensity * 155);
    return `rgb(${r},${Math.round(20 + (1 - intensity) * 20)},${Math.round(20 + (1 - intensity) * 20)})`;
  }
}

export function MonthlyReturnsHeatmap({
  equityCurve,
  timestamps,
}: MonthlyReturnsHeatmapProps) {
  const monthlyReturns = useMemo(
    () => computeMonthlyReturns(equityCurve, timestamps),
    [equityCurve, timestamps]
  );

  // Collect unique years, sorted descending
  const years = useMemo(() => {
    const set = new Set<number>();
    for (const key of monthlyReturns.keys()) {
      set.add(parseInt(key.split("-")[0]));
    }
    return Array.from(set).sort((a, b) => b - a);
  }, [monthlyReturns]);

  if (years.length === 0) {
    return (
      <div
        style={{
          padding: 12,
          fontSize: 10,
          fontFamily: "'JetBrains Mono', monospace",
          color: "#333",
          textAlign: "center",
        }}
      >
        No monthly data available.
      </div>
    );
  }

  // Layout constants
  const rowH = 22;
  const colW = 38;
  const labelW = 36;
  const headerH = 20;
  const svgW = labelW + colW * 12 + 4;
  const svgH = headerH + rowH * years.length + 4;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        width={svgW}
        height={svgH}
        data-testid="monthly-heatmap"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {/* Month header row */}
        {MONTH_ABBR.map((m, mi) => (
          <text
            key={m}
            x={labelW + mi * colW + colW / 2}
            y={headerH - 5}
            textAnchor="middle"
            style={{ fontSize: 8, fill: "#555", letterSpacing: "0.04em" }}
          >
            {m}
          </text>
        ))}

        {/* Year rows */}
        {years.map((year, yi) => {
          const y0 = headerH + yi * rowH;
          return (
            <g key={year}>
              {/* Year label */}
              <text
                x={labelW - 4}
                y={y0 + rowH / 2 + 4}
                textAnchor="end"
                style={{ fontSize: 8, fill: "#555" }}
              >
                {year}
              </text>
              {/* Month cells */}
              {Array.from({ length: 12 }, (_, mi) => {
                const key = `${year}-${mi}`;
                const ret = monthlyReturns.get(key);
                const fill = cellColor(ret);
                const textVal =
                  ret !== undefined ? `${ret >= 0 ? "+" : ""}${ret.toFixed(1)}%` : "";
                const showText = colW >= 34; // only if cell wide enough
                return (
                  <g key={mi}>
                    <rect
                      x={labelW + mi * colW + 1}
                      y={y0 + 1}
                      width={colW - 2}
                      height={rowH - 2}
                      fill={fill}
                      rx={2}
                      data-testid={`cell-${year}-${mi}`}
                    />
                    {showText && ret !== undefined && (
                      <text
                        x={labelW + mi * colW + colW / 2}
                        y={y0 + rowH / 2 + 4}
                        textAnchor="middle"
                        style={{
                          fontSize: 7,
                          fill: Math.abs(ret) > 5 ? "#fff" : "#ccc",
                          fontWeight: 600,
                        }}
                      >
                        {textVal}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
