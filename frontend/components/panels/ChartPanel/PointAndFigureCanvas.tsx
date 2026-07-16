"use client";

/**
 * PointAndFigureCanvas — renders P&F X/O columns on an HTML canvas element.
 *
 * This component is shown when the chart type is set to "pnf" in ChartPanel.
 * It uses bars data already loaded in ChartPanel state — no additional API calls.
 */

import React, { useRef, useEffect, useCallback } from "react";
import { pointAndFigure, computeAutoBoxSize } from "@/lib/indicators/chartTypes";
import type { OHLCBar } from "@/lib/indicators/chartTypes";
import type { BarData } from "@/lib/api/market";

interface PointAndFigureCanvasProps {
  bars: BarData[];
  boxSize?: number;     // 0 = auto-compute from price level
  reversal?: number;    // default 3
  width: number;
  height: number;
}

const X_COLOR = "#00d084";
const O_COLOR = "#ef4444";
const GRID_COLOR = "#1a1a1a";
const TEXT_COLOR = "#555";
const BG_COLOR = "#0a0a0a";

export function PointAndFigureCanvas({
  bars,
  boxSize: boxSizeProp = 0,
  reversal = 3,
  width,
  height,
}: PointAndFigureCanvasProps) {
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

    const boxSize =
      boxSizeProp > 0 ? boxSizeProp : computeAutoBoxSize(ohlcBars);
    const result = pointAndFigure(ohlcBars, boxSize, reversal);

    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, width, height);

    if (result.columns.length === 0) {
      ctx.fillStyle = TEXT_COLOR;
      ctx.font = "11px monospace";
      ctx.textAlign = "center";
      ctx.fillText("Insufficient data for P&F chart", width / 2, height / 2);
      return;
    }

    // Determine price range for y-axis scaling
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    for (const col of result.columns) {
      const colTop =
        col.type === "X"
          ? col.startPrice + col.boxCount * boxSize
          : col.startPrice;
      const colBottom =
        col.type === "X"
          ? col.startPrice
          : col.startPrice - col.boxCount * boxSize;
      minPrice = Math.min(minPrice, colBottom);
      maxPrice = Math.max(maxPrice, colTop);
    }

    const PADDING = { top: 20, right: 20, bottom: 30, left: 55 };
    const chartW = width - PADDING.left - PADDING.right;
    const chartH = height - PADDING.top - PADDING.bottom;

    const COL_WIDTH = Math.max(8, Math.min(24, chartW / (result.columns.length + 2)));
    const priceRange = maxPrice - minPrice || boxSize;

    const toY = (price: number) =>
      PADDING.top + chartH - ((price - minPrice) / priceRange) * chartH;

    // Draw price axis labels
    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "9px monospace";
    ctx.textAlign = "right";
    const nLabels = Math.floor(chartH / 30);
    for (let i = 0; i <= nLabels; i++) {
      const price = minPrice + (i / nLabels) * priceRange;
      const y = toY(price);
      ctx.fillText(price.toFixed(2), PADDING.left - 4, y + 3);
      ctx.strokeStyle = GRID_COLOR;
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(PADDING.left, y);
      ctx.lineTo(width - PADDING.right, y);
      ctx.stroke();
    }

    // Draw columns
    for (let ci = 0; ci < result.columns.length; ci++) {
      const col = result.columns[ci];
      const x = PADDING.left + ci * COL_WIDTH + COL_WIDTH / 2;
      const isX = col.type === "X";
      const colTop =
        isX
          ? col.startPrice + col.boxCount * boxSize
          : col.startPrice;
      const colBottom =
        isX
          ? col.startPrice
          : col.startPrice - col.boxCount * boxSize;

      ctx.strokeStyle = isX ? X_COLOR : O_COLOR;
      ctx.lineWidth = 1.5;
      ctx.font = `${Math.min(COL_WIDTH - 2, 14)}px monospace`;
      ctx.textAlign = "center";
      ctx.fillStyle = isX ? X_COLOR : O_COLOR;

      // Draw each box symbol
      const boxH = (toY(colBottom) - toY(colTop)) / col.boxCount;
      for (let b = 0; b < col.boxCount; b++) {
        const boxTopPrice = isX
          ? col.startPrice + (b + 1) * boxSize
          : col.startPrice - b * boxSize;
        const boxBottomPrice = isX
          ? col.startPrice + b * boxSize
          : col.startPrice - (b + 1) * boxSize;

        const yTop = toY(boxTopPrice);
        const yBot = toY(boxBottomPrice);
        const cy = (yTop + yBot) / 2;
        const bh = Math.max(4, yBot - yTop - 1);

        if (isX) {
          // Draw X
          const half = Math.min(bh / 2, COL_WIDTH / 2) * 0.7;
          ctx.beginPath();
          ctx.moveTo(x - half, cy - half);
          ctx.lineTo(x + half, cy + half);
          ctx.moveTo(x + half, cy - half);
          ctx.lineTo(x - half, cy + half);
          ctx.stroke();
        } else {
          // Draw O
          const r = Math.min(bh / 2, COL_WIDTH / 2) * 0.7;
          ctx.beginPath();
          ctx.arc(x, cy, Math.max(2, r), 0, Math.PI * 2);
          ctx.stroke();
        }
      }
    }

    // Column count label at bottom
    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    ctx.fillText(
      `P&F  box=${boxSize.toFixed(2)}  rev=${reversal}×`,
      width / 2,
      height - 6
    );
  }, [bars, boxSizeProp, reversal, width, height]);

  useEffect(() => {
    draw();
  }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ display: "block", background: BG_COLOR }}
      aria-label="Point and Figure chart"
    />
  );
}
