"use client";

/**
 * KagiCanvas — renders Kagi chart lines on an HTML canvas element.
 *
 * Shown when chart type is "kagi" in ChartPanel.
 * Yang (rising) lines are thick; Yin (falling) lines are thin.
 */

import React, { useRef, useEffect, useCallback } from "react";
import { kagi } from "@/lib/indicators/chartTypes";
import type { OHLCBar } from "@/lib/indicators/chartTypes";
import type { BarData } from "@/lib/api/market";

interface KagiCanvasProps {
  bars: BarData[];
  reversalThreshold?: number;  // 0 = auto (1% of first close)
  width: number;
  height: number;
}

const YANG_COLOR = "#00d084";   // rising thick
const YIN_COLOR = "#ef4444";    // falling thin
const GRID_COLOR = "#1a1a1a";
const TEXT_COLOR = "#555";
const BG_COLOR = "#0a0a0a";
const YANG_WIDTH = 2.5;
const YIN_WIDTH = 1;

export function KagiCanvas({
  bars,
  reversalThreshold = 0,
  width,
  height,
}: KagiCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || bars.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const ohlcBars: OHLCBar[] = bars.map((b) => ({
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));

    const result = kagi(ohlcBars, reversalThreshold);

    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, width, height);

    if (result.lines.length === 0) {
      ctx.fillStyle = TEXT_COLOR;
      ctx.font = "11px monospace";
      ctx.textAlign = "center";
      ctx.fillText("Insufficient data for Kagi chart", width / 2, height / 2);
      return;
    }

    // Price range
    const allPrices = result.lines.flatMap((l) => [l.startPrice, l.endPrice]);
    const minPrice = Math.min(...allPrices);
    const maxPrice = Math.max(...allPrices);
    const priceRange = maxPrice - minPrice || 1;

    const PADDING = { top: 20, right: 30, bottom: 30, left: 60 };
    const chartW = width - PADDING.left - PADDING.right;
    const chartH = height - PADDING.top - PADDING.bottom;

    const segmentWidth = Math.max(12, chartW / (result.lines.length + 1));

    const toY = (price: number) =>
      PADDING.top + chartH - ((price - minPrice) / priceRange) * chartH;

    // Grid + y-axis labels
    const nLabels = Math.floor(chartH / 30);
    ctx.font = "9px monospace";
    ctx.textAlign = "right";
    for (let i = 0; i <= nLabels; i++) {
      const price = minPrice + (i / nLabels) * priceRange;
      const y = toY(price);
      ctx.fillStyle = TEXT_COLOR;
      ctx.fillText(price.toFixed(2), PADDING.left - 4, y + 3);
      ctx.strokeStyle = GRID_COLOR;
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(PADDING.left, y);
      ctx.lineTo(width - PADDING.right, y);
      ctx.stroke();
    }

    // Draw Kagi lines
    for (let i = 0; i < result.lines.length; i++) {
      const line = result.lines[i];
      const x = PADDING.left + i * segmentWidth + segmentWidth / 2;
      const yStart = toY(line.startPrice);
      const yEnd = toY(line.endPrice);
      const isYang = line.direction === "up";

      ctx.strokeStyle = isYang ? YANG_COLOR : YIN_COLOR;
      ctx.lineWidth = isYang ? YANG_WIDTH : YIN_WIDTH;
      ctx.lineCap = "round";

      // Vertical segment
      ctx.beginPath();
      ctx.moveTo(x, yStart);
      ctx.lineTo(x, yEnd);
      ctx.stroke();

      // Horizontal connector to next segment (step line)
      if (i < result.lines.length - 1) {
        const xNext = PADDING.left + (i + 1) * segmentWidth + segmentWidth / 2;
        const nextLine = result.lines[i + 1];
        const nextIsYang = nextLine.direction === "up";
        // Use the color of the next segment for the connector
        ctx.strokeStyle = nextIsYang ? YANG_COLOR : YIN_COLOR;
        ctx.lineWidth = nextIsYang ? YANG_WIDTH : YIN_WIDTH;
        ctx.beginPath();
        ctx.moveTo(x, yEnd);
        ctx.lineTo(xNext, yEnd);
        ctx.stroke();
      }

      // Shoulder/waist dots at reversal points
      ctx.fillStyle = isYang ? YANG_COLOR : YIN_COLOR;
      ctx.beginPath();
      ctx.arc(x, yEnd, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Label
    const threshold = reversalThreshold > 0 ? reversalThreshold.toFixed(2) : "auto";
    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    ctx.fillText(`Kagi  reversal=${threshold}`, width / 2, height - 6);
  }, [bars, reversalThreshold, width, height]);

  useEffect(() => {
    draw();
  }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ display: "block", background: BG_COLOR }}
      aria-label="Kagi chart"
    />
  );
}
