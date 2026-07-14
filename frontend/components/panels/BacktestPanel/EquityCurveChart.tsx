"use client";

/**
 * EquityCurveChart — renders the equity curve from a backtest result.
 *
 * Extracted from BacktestPanel inline rendering.
 * Uses lightweight-charts LineSeries in a useEffect.
 */

import React, { useEffect, useRef } from "react";

interface EquityCurveChartProps {
  equityCurve: number[];
  timestamps?: string[];
  initialCapital?: number;
  height?: number;
}

export function EquityCurveChart({
  equityCurve,
  timestamps,
  height = 200,
}: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || equityCurve.length === 0) return;

    let chart: import("lightweight-charts").IChartApi | undefined;

    (async () => {
      try {
        const { createChart, LineSeries } = await import("lightweight-charts");
        if (!containerRef.current) return;

        chart = createChart(containerRef.current, {
          autoSize: true,
          layout: {
            background: { color: "#0a0a0a" },
            textColor: "#8a8a8a",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
          },
          grid: {
            vertLines: { color: "#1a1a1a", style: 1 },
            horzLines: { color: "#1a1a1a", style: 1 },
          },
          rightPriceScale: { borderColor: "#222" },
          timeScale: { borderColor: "#222", timeVisible: false },
        });

        const series = chart.addSeries(LineSeries, {
          color: "#00d084",
          lineWidth: 2,
          priceLineVisible: false,
        });

        series.setData(
          equityCurve.map((value, i) => ({
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
    <div
      ref={containerRef}
      data-testid="equity-curve-chart"
      style={{
        width: "100%",
        height,
        minHeight: height,
        background: "#0a0a0a",
      }}
    />
  );
}
