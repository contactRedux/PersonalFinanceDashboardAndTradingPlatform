"use client";

/**
 * Sparkline — a minimal inline SVG polyline chart for WatchlistPanel rows.
 *
 * Props:
 *   data    — array of price values (max 20)
 *   width   — SVG width in px (default 60)
 *   height  — SVG height in px (default 22)
 *
 * Colour: green (#00d084) when last > first, red (#ef4444) otherwise.
 * Returns null when data has < 2 points.
 */

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ data, width = 60, height = 22 }: SparklineProps) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1; // avoid division by zero when all prices equal

  const pad = 2; // vertical padding in px
  const drawH = height - pad * 2;
  const step = (width - 1) / (data.length - 1);

  const points = data
    .map((v, i) => {
      const x = i * step;
      const y = pad + drawH - ((v - min) / range) * drawH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const isUp = data[data.length - 1] >= data[0];
  const colour = isUp ? "#00d084" : "#ef4444";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      style={{ display: "block", flexShrink: 0 }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={colour}
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
