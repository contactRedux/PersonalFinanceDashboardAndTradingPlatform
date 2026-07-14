"use client";

/**
 * DrawdownChart — renders a drawdown series derived from an equity curve.
 *
 * Drawdown at each point = (equity[i] - runningMax) / runningMax * 100
 * Rendered as a lightweight-charts AreaSeries in red.
 */

import React, { useEffect, useRef } from "react";

interface DrawdownChartProps {
  equityCurve: number[];
  timestamps?: string[];
  height?: number;
}

/** Compute drawdown series from an equity curve. */
export function computeDrawdown(equityCurve: number[]): number[] {
  if (equityCurve.length === 0) return [];
  const result: number[] = [];
  let runningMax = equityCurve[0];
  for (const equity of equityCurve) {
    if (equity > runningMax) runningMax = equity;
    const dd = runningMax === 0 ? 0 : ((equity - runningMax) / runningMax) * 100;
    result.push(dd);
  }
  return result;
}

export function DrawdownChart({
  equityCurve,
  timestamps,
  height = 120,
}: DrawdownChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || equityCurve.length === 0) return;

    let chart: import("lightweight-charts").IChartApi | undefined;

    (async () => {
      try {
        const { createChart, AreaSeries } = await import("lightweight-charts");
        if (!containerRef.current) return;

        chart = createChart(containerRef.current, {
          autoSize: true,
          layout: {
            background: { color: "#0a0a0a" },
            textColor: "#8a8a8a",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
          },
          grid: {
            vertLines: { color: "#1a1a1a", style: 1 },
            horzLines: { color: "#1a1a1a", style: 1 },
          },
          rightPriceScale: { borderColor: "#222" },
          timeScale: { borderColor: "#222", timeVisible: false },
        });

        const series = chart.addSeries(AreaSeries, {
          lineColor: "#ef4444",
          topColor: "rgba(239,68,68,0.3)",
          bottomColor: "rgba(239,68,68,0.0)",
          lineWidth: 1,
          priceLineVisible: false,
        });

        const drawdown = computeDrawdown(equityCurve);

        series.setData(
          drawdown.map((value, i) => ({
            time: (timestamps?.[i] ?? String(i)) as import("lightweight-charts").Time,
            value,
          }))
        );

        chart.timeScale().fitContent();
      } catch {
        // canvas unavailable in jsdom — graceful no-op
      }
    })();

    return () => {
      try {
        chart?.remove();
      } catch {
        // ignore cleanup errors in test env
      }
    };
  }, [equityCurve, timestamps]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <div
        style={{
          fontSize: 8,
          fontFamily: "'JetBrains Mono', monospace",
          color: "#444",
          letterSpacing: "0.08em",
          padding: "0 2px",
        }}
      >
        DRAWDOWN %
      </div>
      <div
        ref={containerRef}
        data-testid="drawdown-chart"
        style={{
          width: "100%",
          height,
          minHeight: height,
          background: "#0a0a0a",
        }}
      />
    </div>
  );
}
