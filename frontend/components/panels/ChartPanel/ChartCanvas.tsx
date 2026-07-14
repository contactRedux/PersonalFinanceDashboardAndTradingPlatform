"use client";

/**
 * ChartCanvas — mounts a TradingView Lightweight Charts v5 instance.
 *
 * Receives OHLCV bars as props and renders candlestick/line/area/bar/baseline.
 * Handles resize via autoSize.
 * Receives real-time tick updates via latestQuote prop.
 * Renders indicator overlays (SMA, EMA, WMA, BB, RSI, MACD, Stoch RSI,
 * CCI, Williams %R, Parabolic SAR, Donchian Channel, Keltner Channel,
 * Ichimoku Cloud, SuperTrend, TRIX, ROC, Ultimate Oscillator).
 */

import React, { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  BarSeries,
  BaselineSeries,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time, CandlestickData, OhlcData } from "lightweight-charts";
import type { BarData } from "@/lib/api/market";
import type { Quote } from "@/types/market";
import type { ChartType, IndicatorConfig } from "@/store/chartStore";
import {
  sma,
  ema,
  wma,
  bollingerBands,
  rsi,
  macd,
  heikinAshi,
  stochasticRsi,
  cci,
  williamsR,
  parabolicSar,
  donchianChannel,
  keltnerChannel,
  ichimokuCloud,
  superTrend,
  trix,
  roc,
  ultimateOscillator,
  accumulationDistribution,
  cmf,
  mfi,
  forceIndex,
  rvol,
  pivotPoints,
} from "@/lib/indicators";

// Colour palette for overlay series
const OVERLAY_COLOURS = [
  "#f59e0b", // amber
  "#3b82f6", // blue
  "#a855f7", // purple
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f97316", // orange
];

let _colourIdx = 0;
function nextColour(): string {
  return OVERLAY_COLOURS[_colourIdx++ % OVERLAY_COLOURS.length];
}

export interface VPVRLevel {
  price: number;
  volume: number;
  is_poc: boolean;
  pct_of_max: number;
}

interface ChartCanvasProps {
  bars: BarData[];
  chartType: ChartType;
  latestQuote?: Quote;
  height?: number;
  indicators?: IndicatorConfig[];
  /** Optional VPVR data rendered as a canvas overlay on the right side. */
  vpvr?: VPVRLevel[];
  /**
   * If provided, ChartCanvas will populate these refs so the parent (ChartPanel)
   * can share them with drawing-tool hooks.
   */
  chartRef?: React.RefObject<IChartApi | null>;
  seriesRef?: React.RefObject<ISeriesApi<
    "Candlestick" | "Line" | "Area" | "Bar" | "Baseline"
  > | null>;
}

export function ChartCanvas({
  bars,
  chartType,
  latestQuote,
  height = 420,
  indicators = [],
  vpvr,
  chartRef: externalChartRef,
  seriesRef: externalSeriesRef,
}: ChartCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const internalChartRef = useRef<IChartApi | null>(null);
  const internalSeriesRef = useRef<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>(
    null
  );

  // Resolve to external refs if provided, otherwise use internal refs
  const chartRef = externalChartRef ?? internalChartRef;
  const seriesRef = externalSeriesRef ?? internalSeriesRef;
  // Map: indicator id (or id+"_upper" etc.) → LineSeries
  const overlayRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const vpvrCanvasRef = useRef<HTMLCanvasElement>(null);

  // Initialize chart on mount
  useEffect(() => {
    if (!containerRef.current) return;

    _colourIdx = 0; // reset colour rotation on remount
    // Capture overlay map at effect-start so the cleanup closure holds a stable ref
    const overlays = overlayRef.current;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "#0a0a0a" },
        textColor: "#8a8a8a",
        fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1a1a1a", style: 1 },
        horzLines: { color: "#1a1a1a", style: 1 },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "#555555", width: 1, style: 3, labelBackgroundColor: "#222" },
        horzLine: { color: "#555555", width: 1, style: 3, labelBackgroundColor: "#222" },
      },
      rightPriceScale: {
        borderColor: "#222222",
        textColor: "#8a8a8a",
      },
      timeScale: {
        borderColor: "#222222",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });

    chartRef.current = chart;

    return () => {
      overlays.clear();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Add/swap primary series when chartType or bars change
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove all overlay series before recreating primary (chart.remove() resets everything)
    overlayRef.current.forEach((s) => chart.removeSeries(s));
    overlayRef.current.clear();

    // Remove existing primary series
    if (seriesRef.current) {
      chart.removeSeries(seriesRef.current);
      seriesRef.current = null;
    }

    if (!bars.length) return;

    const commonOptions = {
      priceLineVisible: true,
      lastValueVisible: true,
    };

    if (chartType === "candlestick" || chartType === "heikin_ashi" || chartType === "renko" || chartType === "line_break") {
      const series = chart.addSeries(CandlestickSeries, {
        ...commonOptions,
        upColor: "#00d084",
        downColor: "#ef4444",
        borderUpColor: "#00d084",
        borderDownColor: "#ef4444",
        wickUpColor: "#00a868",
        wickDownColor: "#dc2626",
      });

      let ohlcBars = bars.map((b) => ({
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));

      if (chartType === "heikin_ashi") {
        ohlcBars = heikinAshi(ohlcBars);
      }

      const data: CandlestickData<Time>[] = bars.map((b, i) => ({
        time: (new Date(b.time).getTime() / 1000) as Time,
        open: ohlcBars[i].open,
        high: ohlcBars[i].high,
        low: ohlcBars[i].low,
        close: ohlcBars[i].close,
      }));
      series.setData(data);
      seriesRef.current = series;
    } else if (chartType === "bar") {
      const series = chart.addSeries(BarSeries, {
        ...commonOptions,
        upColor: "#00d084",
        downColor: "#ef4444",
      });
      const data: OhlcData<Time>[] = bars.map((b) => ({
        time: (new Date(b.time).getTime() / 1000) as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));
      series.setData(data);
      seriesRef.current = series;
    } else if (chartType === "area") {
      const series = chart.addSeries(AreaSeries, {
        ...commonOptions,
        lineColor: "#0ea5e9",
        topColor: "rgba(14,165,233,0.3)",
        bottomColor: "rgba(14,165,233,0.01)",
      });
      series.setData(
        bars.map((b) => ({
          time: (new Date(b.time).getTime() / 1000) as Time,
          value: b.close,
        }))
      );
      seriesRef.current = series;
    } else if (chartType === "baseline") {
      const series = chart.addSeries(BaselineSeries, {
        ...commonOptions,
        baseValue: { type: "price", price: bars[0]?.close ?? 0 },
        topLineColor: "#00d084",
        topFillColor1: "rgba(0,208,132,0.2)",
        topFillColor2: "rgba(0,208,132,0.02)",
        bottomLineColor: "#ef4444",
        bottomFillColor1: "rgba(239,68,68,0.02)",
        bottomFillColor2: "rgba(239,68,68,0.2)",
      });
      series.setData(
        bars.map((b) => ({
          time: (new Date(b.time).getTime() / 1000) as Time,
          value: b.close,
        }))
      );
      seriesRef.current = series;
    } else {
      // line (default)
      const series = chart.addSeries(LineSeries, {
        ...commonOptions,
        color: "#0ea5e9",
        lineWidth: 2,
      });
      series.setData(
        bars.map((b) => ({
          time: (new Date(b.time).getTime() / 1000) as Time,
          value: b.close,
        }))
      );
      seriesRef.current = series;
    }
    // Renko & line_break are also handled above (candlestick branch) since
    // the backend transforms them to OHLCV before sending.

    chart.timeScale().fitContent();
  }, [bars, chartType]);

  // Indicator overlays — diff and update when indicators or bars change
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !bars.length) return;

    const times = bars.map((b) => (new Date(b.time).getTime() / 1000) as Time);
    const closes = bars.map((b) => b.close);

    const currentIds = new Set<string>();

    for (const ind of indicators) {
      if (ind.type === "bb") {
        // Bollinger Bands — three sub-series per indicator id
        const period = (ind.params.period as number) ?? 20;
        const stdDev = (ind.params.std_dev as number) ?? 2;
        const bb = bollingerBands(closes, period, stdDev);
        const colour = nextColour();

        for (const band of ["upper", "mid", "lower"] as const) {
          const key = `${ind.id}_${band}`;
          currentIds.add(key);
          if (!overlayRef.current.has(key)) {
            const s = chart.addSeries(LineSeries, {
              color: colour,
              lineWidth: 1,
              lineStyle: band === "mid" ? 0 : 2,
              visible: ind.visible,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(key, s);
          }
          const series = overlayRef.current.get(key)!;
          series.applyOptions({ visible: ind.visible });
          const values = band === "upper" ? bb.upper : band === "mid" ? bb.middle : bb.lower;
          series.setData(
            times
              .map((t, i) => ({ time: t, value: values[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        continue;
      }

      if (ind.type === "macd") {
        // MACD — three sub-series: macd line, signal, histogram
        const fast = (ind.params.fast as number) ?? 12;
        const slow = (ind.params.slow as number) ?? 26;
        const signal = (ind.params.signal as number) ?? 9;
        const result = macd(closes, fast, slow, signal);
        const colour = nextColour();

        for (const part of ["line", "signal", "hist"] as const) {
          const key = `${ind.id}_${part}`;
          currentIds.add(key);
          if (!overlayRef.current.has(key)) {
            const s = chart.addSeries(LineSeries, {
              color: part === "hist" ? "rgba(255,255,255,0.35)" : colour,
              lineWidth: part === "hist" ? 1 : 1,
              lineStyle: part === "signal" ? 2 : 0,
              visible: ind.visible,
              priceScaleId: "macd",
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(key, s);
          }
          const series = overlayRef.current.get(key)!;
          series.applyOptions({ visible: ind.visible });
          const vals =
            part === "line" ? result.macd : part === "signal" ? result.signal : result.histogram;
          series.setData(
            times
              .map((t, i) => ({ time: t, value: vals[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        // Apply scale margins so MACD renders below price
        chart.priceScale("macd").applyOptions({
          scaleMargins: { top: 0.7, bottom: 0 },
        });
        continue;
      }

      if (ind.type === "rsi") {
        const period = (ind.params.period as number) ?? 14;
        const values = rsi(closes, period);
        const key = ind.id;
        currentIds.add(key);
        if (!overlayRef.current.has(key)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "rsi",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(key, s);
        }
        const series = overlayRef.current.get(key)!;
        series.applyOptions({ visible: ind.visible });
        series.setData(
          times
            .map((t, i) => ({ time: t, value: values[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("rsi").applyOptions({
          scaleMargins: { top: 0.75, bottom: 0 },
        });
        continue;
      }

      if (ind.type === "stochrsi") {
        const period = (ind.params.period as number) ?? 14;
        const smoothK = (ind.params.smooth_k as number) ?? 3;
        const smoothD = (ind.params.smooth_d as number) ?? 3;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const { k, d } = stochasticRsi(closes, highs, lows, period, smoothK, smoothD);
        const colour = nextColour();

        for (const part of ["k", "d"] as const) {
          const srKey = `${ind.id}_${part}`;
          currentIds.add(srKey);
          if (!overlayRef.current.has(srKey)) {
            const s = chart.addSeries(LineSeries, {
              color: part === "k" ? colour : "rgba(255,255,255,0.5)",
              lineWidth: 1,
              lineStyle: part === "d" ? 2 : 0,
              visible: ind.visible,
              priceScaleId: "stochrsi",
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(srKey, s);
          }
          const srSeries = overlayRef.current.get(srKey)!;
          srSeries.applyOptions({ visible: ind.visible });
          const vals = part === "k" ? k : d;
          srSeries.setData(
            times
              .map((t, i) => ({ time: t, value: vals[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        chart.priceScale("stochrsi").applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
        continue;
      }

      if (ind.type === "cci") {
        const period = (ind.params.period as number) ?? 20;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const cciValues = cci(highs, lows, closes, period);
        const cciKey = ind.id;
        currentIds.add(cciKey);
        if (!overlayRef.current.has(cciKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "cci",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(cciKey, s);
        }
        const cciSeries = overlayRef.current.get(cciKey)!;
        cciSeries.applyOptions({ visible: ind.visible });
        cciSeries.setData(
          times
            .map((t, i) => ({ time: t, value: cciValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("cci").applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
        continue;
      }

      if (ind.type === "willr") {
        const period = (ind.params.period as number) ?? 14;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const wrValues = williamsR(highs, lows, closes, period);
        const wrKey = ind.id;
        currentIds.add(wrKey);
        if (!overlayRef.current.has(wrKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "willr",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(wrKey, s);
        }
        const wrSeries = overlayRef.current.get(wrKey)!;
        wrSeries.applyOptions({ visible: ind.visible });
        wrSeries.setData(
          times
            .map((t, i) => ({ time: t, value: wrValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("willr").applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
        continue;
      }

      if (ind.type === "psar") {
        const psarStep = ((ind.params.step as number) ?? 2) / 100;
        const psarMax = ((ind.params.max as number) ?? 20) / 100;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const psarValues = parabolicSar(highs, lows, psarStep, psarMax);
        const psarKey = ind.id;
        currentIds.add(psarKey);
        if (!overlayRef.current.has(psarKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            lineStyle: 3,
            visible: ind.visible,
            priceScaleId: "psar",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(psarKey, s);
        }
        const psarSeries = overlayRef.current.get(psarKey)!;
        psarSeries.applyOptions({ visible: ind.visible });
        psarSeries.setData(
          times
            .map((t, i) => ({ time: t, value: psarValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("psar").applyOptions({ scaleMargins: { top: 0.0, bottom: 0.0 } });
        continue;
      }

      if (ind.type === "donchian") {
        const period = (ind.params.period as number) ?? 20;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const dc = donchianChannel(highs, lows, period);
        const dcColour = nextColour();

        for (const band of ["upper", "mid", "lower"] as const) {
          const dcKey = `${ind.id}_${band}`;
          currentIds.add(dcKey);
          if (!overlayRef.current.has(dcKey)) {
            const s = chart.addSeries(LineSeries, {
              color: dcColour,
              lineWidth: 1,
              lineStyle: band === "mid" ? 2 : 0,
              visible: ind.visible,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(dcKey, s);
          }
          const dcSeries = overlayRef.current.get(dcKey)!;
          dcSeries.applyOptions({ visible: ind.visible });
          const dcVals = band === "upper" ? dc.upper : band === "lower" ? dc.lower : dc.mid;
          dcSeries.setData(
            times
              .map((t, i) => ({ time: t, value: dcVals[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        continue;
      }

      if (ind.type === "keltner") {
        const period = (ind.params.period as number) ?? 20;
        const multiplier = (ind.params.multiplier as number) ?? 2;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const kc = keltnerChannel(highs, lows, closes, period, multiplier);
        const kcColour = nextColour();

        for (const band of ["upper", "mid", "lower"] as const) {
          const kcKey = `${ind.id}_${band}`;
          currentIds.add(kcKey);
          if (!overlayRef.current.has(kcKey)) {
            const s = chart.addSeries(LineSeries, {
              color: kcColour,
              lineWidth: 1,
              lineStyle: band === "mid" ? 0 : 2,
              visible: ind.visible,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(kcKey, s);
          }
          const kcSeries = overlayRef.current.get(kcKey)!;
          kcSeries.applyOptions({ visible: ind.visible });
          const kcVals = band === "upper" ? kc.upper : band === "lower" ? kc.lower : kc.mid;
          kcSeries.setData(
            times
              .map((t, i) => ({ time: t, value: kcVals[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        continue;
      }

      if (ind.type === "ichimoku") {
        const tenkanP = (ind.params.tenkan as number) ?? 9;
        const kijunP = (ind.params.kijun as number) ?? 26;
        const senkouBP = (ind.params.senkouB as number) ?? 52;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const cloud = ichimokuCloud(highs, lows, closes, tenkanP, kijunP, senkouBP);

        const ichimokuLines: [string, number[], string][] = [
          ["tenkan", cloud.tenkan, "#3b82f6"],      // blue
          ["kijun", cloud.kijun, "#ef4444"],         // red
          ["chikou", cloud.chikou, "#22c55e"],        // green
          ["senkouA", cloud.senkouA, "rgba(0,208,132,0.3)"],
          ["senkouB", cloud.senkouB, "rgba(239,68,68,0.3)"],
        ];
        for (const [suffix, vals, colour] of ichimokuLines) {
          const ichKey = `${ind.id}_${suffix}`;
          currentIds.add(ichKey);
          if (!overlayRef.current.has(ichKey)) {
            const s = chart.addSeries(LineSeries, {
              color: colour,
              lineWidth: 1,
              visible: ind.visible,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(ichKey, s);
          }
          const ichSeries = overlayRef.current.get(ichKey)!;
          ichSeries.applyOptions({ visible: ind.visible });
          ichSeries.setData(
            times
              .map((t, i) => ({ time: t, value: vals[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        continue;
      }

      if (ind.type === "supertrend") {
        const period = (ind.params.period as number) ?? 10;
        const multiplier = (ind.params.multiplier as number) ?? 3;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const st = superTrend(highs, lows, closes, period, multiplier);
        const stKey = ind.id;
        currentIds.add(stKey);
        // Determine colour from last direction
        const lastDir = [...st.direction].reverse().find((v) => !isNaN(v)) ?? 1;
        const stColour = lastDir > 0 ? "#22c55e" : "#ef4444";
        if (!overlayRef.current.has(stKey)) {
          const s = chart.addSeries(LineSeries, {
            color: stColour,
            lineWidth: 2,
            visible: ind.visible,
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(stKey, s);
        }
        const stSeries = overlayRef.current.get(stKey)!;
        stSeries.applyOptions({ visible: ind.visible, color: stColour });
        stSeries.setData(
          times
            .map((t, i) => ({ time: t, value: st.values[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        continue;
      }

      if (ind.type === "trix") {
        const period = (ind.params.period as number) ?? 14;
        const trixValues = trix(closes, period);
        const trixKey = ind.id;
        currentIds.add(trixKey);
        if (!overlayRef.current.has(trixKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "trix",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(trixKey, s);
        }
        const trixSeries = overlayRef.current.get(trixKey)!;
        trixSeries.applyOptions({ visible: ind.visible });
        trixSeries.setData(
          times
            .map((t, i) => ({ time: t, value: trixValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("trix").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "roc") {
        const period = (ind.params.period as number) ?? 12;
        const rocValues = roc(closes, period);
        const rocKey = ind.id;
        currentIds.add(rocKey);
        if (!overlayRef.current.has(rocKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "roc",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(rocKey, s);
        }
        const rocSeries = overlayRef.current.get(rocKey)!;
        rocSeries.applyOptions({ visible: ind.visible });
        rocSeries.setData(
          times
            .map((t, i) => ({ time: t, value: rocValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("roc").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "ultosc") {
        const period1 = (ind.params.period1 as number) ?? 7;
        const period2 = (ind.params.period2 as number) ?? 14;
        const period3 = (ind.params.period3 as number) ?? 28;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const ultValues = ultimateOscillator(highs, lows, closes, period1, period2, period3);
        const ultKey = ind.id;
        currentIds.add(ultKey);
        if (!overlayRef.current.has(ultKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "ultosc",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(ultKey, s);
        }
        const ultSeries = overlayRef.current.get(ultKey)!;
        ultSeries.applyOptions({ visible: ind.visible });
        ultSeries.setData(
          times
            .map((t, i) => ({ time: t, value: ultValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("ultosc").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "ad") {
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const vols = bars.map((b) => b.volume);
        const adValues = accumulationDistribution(highs, lows, closes, vols);
        const adKey = ind.id;
        currentIds.add(adKey);
        if (!overlayRef.current.has(adKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "ad",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(adKey, s);
        }
        const adSeries = overlayRef.current.get(adKey)!;
        adSeries.applyOptions({ visible: ind.visible });
        adSeries.setData(
          times
            .map((t, i) => ({ time: t, value: adValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("ad").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "cmf") {
        const period = (ind.params.period as number) ?? 20;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const vols = bars.map((b) => b.volume);
        const cmfValues = cmf(highs, lows, closes, vols, period);
        const cmfKey = ind.id;
        currentIds.add(cmfKey);
        if (!overlayRef.current.has(cmfKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "cmf",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(cmfKey, s);
        }
        const cmfSeries = overlayRef.current.get(cmfKey)!;
        cmfSeries.applyOptions({ visible: ind.visible });
        cmfSeries.setData(
          times
            .map((t, i) => ({ time: t, value: cmfValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("cmf").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "mfi") {
        const period = (ind.params.period as number) ?? 14;
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const vols = bars.map((b) => b.volume);
        const mfiValues = mfi(highs, lows, closes, vols, period);
        const mfiKey = ind.id;
        currentIds.add(mfiKey);
        if (!overlayRef.current.has(mfiKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "mfi",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(mfiKey, s);
        }
        const mfiSeries = overlayRef.current.get(mfiKey)!;
        mfiSeries.applyOptions({ visible: ind.visible });
        mfiSeries.setData(
          times
            .map((t, i) => ({ time: t, value: mfiValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("mfi").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "force") {
        const period = (ind.params.period as number) ?? 13;
        const vols = bars.map((b) => b.volume);
        const fiValues = forceIndex(closes, vols, period);
        const fiKey = ind.id;
        currentIds.add(fiKey);
        if (!overlayRef.current.has(fiKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "force",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(fiKey, s);
        }
        const fiSeries = overlayRef.current.get(fiKey)!;
        fiSeries.applyOptions({ visible: ind.visible });
        fiSeries.setData(
          times
            .map((t, i) => ({ time: t, value: fiValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("force").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "rvol") {
        const period = (ind.params.period as number) ?? 20;
        const vols = bars.map((b) => b.volume);
        const rvolValues = rvol(vols, period);
        const rvolKey = ind.id;
        currentIds.add(rvolKey);
        if (!overlayRef.current.has(rvolKey)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "rvol",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(rvolKey, s);
        }
        const rvolSeries = overlayRef.current.get(rvolKey)!;
        rvolSeries.applyOptions({ visible: ind.visible });
        rvolSeries.setData(
          times
            .map((t, i) => ({ time: t, value: rvolValues[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("rvol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        continue;
      }

      if (ind.type === "pivots") {
        const highs = bars.map((b) => b.high);
        const lows = bars.map((b) => b.low);
        const piv = pivotPoints(highs, lows, closes);
        const pivotSeries = seriesRef.current;
        const pivotKey = ind.id;
        currentIds.add(pivotKey);
        // We store a sentinel LineSeries in overlayRef to track existence,
        // but render using price lines on the primary series.
        // On re-render we recreate all price lines for this indicator id.
        const existingPivotSeries = overlayRef.current.get(pivotKey);
        if (existingPivotSeries) {
          // Remove old sentinel so price lines get re-created
          try { chart.removeSeries(existingPivotSeries); } catch { /* ignore */ }
          overlayRef.current.delete(pivotKey);
        }
        // Create a hidden sentinel series to track this indicator
        const sentinel = chart.addSeries(LineSeries, {
          visible: false,
          priceLineVisible: false,
          lastValueVisible: false,
          lineWidth: 1,
          color: "transparent",
        });
        overlayRef.current.set(pivotKey, sentinel);

        if (pivotSeries && ind.visible) {
          const lastIdx = times.length - 1;
          const pivotDefs: { key: keyof typeof piv; color: string; title: string }[] = [
            { key: "P",  color: "#ffffff", title: "P" },
            { key: "R1", color: "#22c55e", title: "R1" },
            { key: "R2", color: "#16a34a", title: "R2" },
            { key: "R3", color: "#15803d", title: "R3" },
            { key: "S1", color: "#ef4444", title: "S1" },
            { key: "S2", color: "#dc2626", title: "S2" },
            { key: "S3", color: "#b91c1c", title: "S3" },
          ];
          for (const { key, color, title } of pivotDefs) {
            const priceVal = piv[key][lastIdx];
            if (!isNaN(priceVal)) {
              pivotSeries.createPriceLine({
                price: priceVal,
                color,
                lineWidth: 1,
                lineStyle: 1,
                axisLabelVisible: true,
                title,
              });
            }
          }
        }
        continue;
      }

      // SMA, EMA, WMA — single line overlaid on price pane
      const key = ind.id;
      currentIds.add(key);
      if (!overlayRef.current.has(key)) {
        const s = chart.addSeries(LineSeries, {
          color: nextColour(),
          lineWidth: 1,
          visible: ind.visible,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        overlayRef.current.set(key, s);
      }
      const series = overlayRef.current.get(key)!;
      series.applyOptions({ visible: ind.visible });

      const period = (ind.params.period as number) ?? 20;
      const fn = ind.type === "ema" ? ema : ind.type === "wma" ? wma : sma;
      const values = fn(closes, period);
      series.setData(
        times
          .map((t, i) => ({ time: t, value: values[i] }))
          .filter((pt) => !isNaN(pt.value))
      );
    }

    // Remove series for indicators that were deleted
    for (const key of overlayRef.current.keys()) {
      const baseId = key.replace(/_(upper|mid|lower|line|signal|hist|k|d|tenkan|kijun|chikou|senkouA|senkouB)$/, "");
      if (!currentIds.has(key) && !currentIds.has(baseId)) {
        chart.removeSeries(overlayRef.current.get(key)!);
        overlayRef.current.delete(key);
      }
    }
  }, [indicators, bars]);

  // Imperatively update the last bar with the latest quote (bypasses React state)
  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !latestQuote?.price || !bars.length) return;
    const lastBar = bars[bars.length - 1];
    const lastTime = (new Date(lastBar.time).getTime() / 1000) as Time;

    if (chartType === "candlestick" || chartType === "heikin_ashi" || chartType === "bar" || chartType === "renko" || chartType === "line_break") {
      (series as ISeriesApi<"Candlestick">).update({
        time: lastTime,
        open: lastBar.open,
        high: Math.max(lastBar.high, latestQuote.price),
        low: Math.min(lastBar.low, latestQuote.price),
        close: latestQuote.price,
      } as CandlestickData<Time>);
    } else {
      (series as ISeriesApi<"Line">).update({
        time: lastTime,
        value: latestQuote.price,
      } as { time: Time; value: number });
    }
  }, [latestQuote, bars, chartType]);

  // VPVR canvas overlay — drawn right-side histogram
  useEffect(() => {
    const canvas = vpvrCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!vpvr || vpvr.length === 0 || !bars.length) return;

    const barPrices = bars.map((b) => b.close);
    const priceMin = Math.min(...barPrices);
    const priceMax = Math.max(...barPrices);
    const priceRange = priceMax - priceMin || 1;

    const maxBarWidth = 60; // px
    const h = canvas.height;
    const w = canvas.width;

    vpvr.forEach((level) => {
      const barW = Math.round(level.pct_of_max * maxBarWidth);
      const y = Math.round(((priceMax - level.price) / priceRange) * h);
      const barH = Math.max(2, Math.round((h / (vpvr.length || 1)) * 0.8));

      ctx.fillStyle = level.is_poc
        ? "rgba(245,158,11,0.7)"  // amber — point of control
        : "rgba(59,130,246,0.35)"; // blue — normal
      ctx.fillRect(w - barW - 2, y - barH / 2, barW, barH);
    });
  }, [vpvr, bars]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: height,
        background: "#0a0a0a",
        borderRadius: 0,
      }}
    >
      {/* VPVR overlay canvas — transparent, pointer-events: none */}
      <canvas
        ref={vpvrCanvasRef}
        width={80}
        height={height}
        style={{
          position: "absolute",
          right: 50, // leave room for price scale
          top: 0,
          pointerEvents: "none",
        }}
        aria-hidden="true"
        data-testid="vpvr-canvas"
      />
    </div>
  );
}
