/**
 * Chart type calculation functions for non-time-axis chart types.
 * Used by PointAndFigureCanvas and KagiCanvas.
 */

// ─── Shared types ──────────────────────────────────────────────────────────

export interface OHLCBar {
  open: number;
  high: number;
  low: number;
  close: number;
}

// ─── Point & Figure ────────────────────────────────────────────────────────

export interface PnFColumn {
  /** "X" = rising column, "O" = falling column */
  type: "X" | "O";
  /** Starting price of the column (lowest box for X, highest box for O) */
  startPrice: number;
  /** Number of boxes in this column */
  boxCount: number;
  /** Index of source bar where this column started */
  startBarIndex: number;
}

export interface PnFResult {
  columns: PnFColumn[];
  boxSize: number;
  /** The price level of box index 0 — used to map box numbers to prices */
  basePrice: number;
}

/**
 * Compute Point & Figure columns from OHLC bars.
 *
 * @param bars      Array of OHLC bars (oldest first)
 * @param boxSize   Size of each box in price units (positive number)
 * @param reversal  Number of boxes required to reverse direction (typically 3)
 */
export function pointAndFigure(
  bars: OHLCBar[],
  boxSize: number,
  reversal: number = 3
): PnFResult {
  if (bars.length === 0 || boxSize <= 0) {
    return { columns: [], boxSize, basePrice: 0 };
  }

  // Helper: snap a price DOWN to the nearest box boundary
  const snapDown = (price: number): number =>
    Math.floor(price / boxSize) * boxSize;

  // Helper: snap a price UP to the nearest box boundary
  const snapUp = (price: number): number =>
    Math.ceil(price / boxSize) * boxSize;

  const columns: PnFColumn[] = [];

  // Determine initial direction from the first two bars
  let currentHigh = snapUp(bars[0].high);
  let currentLow = snapDown(bars[0].low);
  let direction: "X" | "O" | null = null;
  let columnStartPrice: number = currentLow;
  let columnStartBar: number = 0;

  // Accumulate the first column based on the initial price range
  const initialRange = currentHigh - currentLow;
  if (initialRange >= boxSize) {
    // Start with an X column (up) if the first close > first open
    direction = bars[0].close >= bars[0].open ? "X" : "O";
    columnStartPrice = direction === "X" ? currentLow : currentHigh;
  }

  for (let i = 1; i < bars.length; i++) {
    const high = bars[i].high;
    const low = bars[i].low;

    if (direction === null) {
      // Determine direction from first significant price move
      const snappedHigh = snapUp(high);
      const snappedLow = snapDown(low);
      const range = snappedHigh - snappedLow;
      if (range >= boxSize) {
        direction = bars[i].close >= bars[i].open ? "X" : "O";
        columnStartPrice = direction === "X" ? snappedLow : snappedHigh;
        columnStartBar = i;
        currentHigh = snappedHigh;
        currentLow = snappedLow;
      }
      continue;
    }

    if (direction === "X") {
      const newHigh = snapUp(high);
      if (newHigh > currentHigh) {
        // Extend the X column
        currentHigh = newHigh;
      } else {
        // Check for reversal down
        const reversalPrice = currentHigh - reversal * boxSize;
        const snappedLow = snapDown(low);
        if (snappedLow <= reversalPrice) {
          // Save the completed X column
          const boxCount = Math.round((currentHigh - columnStartPrice) / boxSize);
          if (boxCount > 0) {
            columns.push({
              type: "X",
              startPrice: columnStartPrice,
              boxCount,
              startBarIndex: columnStartBar,
            });
          }
          // Start a new O column
          direction = "O";
          columnStartPrice = currentHigh;
          columnStartBar = i;
          currentLow = snappedLow;
        }
      }
    } else {
      // direction === "O"
      const snappedLow = snapDown(low);
      if (snappedLow < currentLow) {
        currentLow = snappedLow;
      } else {
        // Check for reversal up
        const reversalPrice = currentLow + reversal * boxSize;
        const newHigh = snapUp(high);
        if (newHigh >= reversalPrice) {
          // Save the completed O column
          const boxCount = Math.round((columnStartPrice - currentLow) / boxSize);
          if (boxCount > 0) {
            columns.push({
              type: "O",
              startPrice: columnStartPrice,
              boxCount,
              startBarIndex: columnStartBar,
            });
          }
          // Start a new X column
          direction = "X";
          columnStartPrice = currentLow;
          columnStartBar = i;
          currentHigh = newHigh;
        }
      }
    }
  }

  // Flush the final column
  if (direction !== null) {
    if (direction === "X") {
      const boxCount = Math.round((currentHigh - columnStartPrice) / boxSize);
      if (boxCount > 0) {
        columns.push({
          type: "X",
          startPrice: columnStartPrice,
          boxCount,
          startBarIndex: columnStartBar,
        });
      }
    } else {
      const boxCount = Math.round((columnStartPrice - currentLow) / boxSize);
      if (boxCount > 0) {
        columns.push({
          type: "O",
          startPrice: columnStartPrice,
          boxCount,
          startBarIndex: columnStartBar,
        });
      }
    }
  }

  // Base price = lowest price seen across all columns
  const basePrice = columns.reduce((min, col) => {
    const colBottom = col.type === "X" ? col.startPrice : col.startPrice - col.boxCount * boxSize;
    return Math.min(min, colBottom);
  }, bars.reduce((m, b) => Math.min(m, b.low), Infinity));

  return { columns, boxSize, basePrice };
}

// ─── ATR-based box size helper ──────────────────────────────────────────────

/**
 * Compute a reasonable P&F box size as ~1% of the average close price.
 * Rounds to a clean decimal number.
 */
export function computeAutoBoxSize(bars: OHLCBar[]): number {
  if (bars.length === 0) return 1;
  const avgClose = bars.reduce((s, b) => s + b.close, 0) / bars.length;
  const raw = avgClose * 0.01;
  // Round to 1 significant figure
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  return Math.max(0.01, Math.round(raw / mag) * mag);
}

// ─── Kagi ──────────────────────────────────────────────────────────────────

export interface KagiLine {
  /** "up" = Yang (rising thick line), "down" = Yin (falling thin line) */
  direction: "up" | "down";
  /** Starting close price of this segment */
  startPrice: number;
  /** Ending close price of this segment */
  endPrice: number;
  /** Index of source bar where the segment started */
  startBarIndex: number;
  /** Index of source bar where the segment ended */
  endBarIndex: number;
}

export interface KagiResult {
  lines: KagiLine[];
}

/**
 * Compute Kagi chart lines from close prices.
 *
 * @param bars              Array of bars (oldest first)
 * @param reversalThreshold Minimum price change (absolute) to trigger a reversal.
 *                          Pass 0 to use 1% of the first close price (auto).
 */
export function kagi(bars: OHLCBar[], reversalThreshold: number = 0): KagiResult {
  if (bars.length < 2) return { lines: [] };

  const closes = bars.map((b) => b.close);
  const threshold =
    reversalThreshold > 0
      ? reversalThreshold
      : closes[0] * 0.01; // default 1%

  const lines: KagiLine[] = [];

  let direction: "up" | "down" = closes[1] >= closes[0] ? "up" : "down";
  let segStart = closes[0];
  let segStartBar = 0;

  for (let i = 1; i < closes.length; i++) {
    const price = closes[i];

    if (direction === "up") {
      if (price >= segStart) {
        // Continue up — extend
        segStart = price;
      } else if (segStart - price >= threshold) {
        // Reversal down
        lines.push({
          direction: "up",
          startPrice: closes[segStartBar],
          endPrice: segStart,
          startBarIndex: segStartBar,
          endBarIndex: i - 1,
        });
        direction = "down";
        segStart = price;
        segStartBar = i;
      }
    } else {
      if (price <= segStart) {
        // Continue down — extend
        segStart = price;
      } else if (price - segStart >= threshold) {
        // Reversal up
        lines.push({
          direction: "down",
          startPrice: closes[segStartBar],
          endPrice: segStart,
          startBarIndex: segStartBar,
          endBarIndex: i - 1,
        });
        direction = "up";
        segStart = price;
        segStartBar = i;
      }
    }
  }

  // Flush final segment
  lines.push({
    direction,
    startPrice: closes[segStartBar],
    endPrice: closes[closes.length - 1],
    startBarIndex: segStartBar,
    endBarIndex: closes.length - 1,
  });

  return { lines };
}
