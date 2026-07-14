/**
 * Financial number formatting utilities.
 */

const currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const compactFmt = new Intl.NumberFormat("en-US", {
  notation: "compact",
  compactDisplay: "short",
  maximumFractionDigits: 2,
});

const pctFmt = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

/**
 * Format a price number for display.
 * Automatically adjusts decimal places based on magnitude.
 */
export function formatPrice(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format as USD currency. */
export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  return currencyFmt.format(value);
}

/** Format as compact notation (e.g. 1.23B, 456M). */
export function formatCompact(value: number | null | undefined): string {
  if (value == null) return "—";
  return compactFmt.format(value);
}

/** Format as signed percentage (e.g. +1.23%, -0.45%). */
export function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return pctFmt.format(value / 100);
}

/** Format a percentage already in decimal form (0.0123 → +1.23%). */
export function formatPctDecimal(value: number | null | undefined): string {
  if (value == null) return "—";
  return pctFmt.format(value);
}

/** Format a large volume number. */
export function formatVolume(value: number | null | undefined): string {
  if (value == null) return "—";
  return compactFmt.format(value);
}

/** CSS class for a price change value. */
export function priceChangeClass(change: number | null | undefined): string {
  if (change == null) return "price-flat";
  if (change > 0) return "price-up";
  if (change < 0) return "price-down";
  return "price-flat";
}
