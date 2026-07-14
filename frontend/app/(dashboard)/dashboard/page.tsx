"use client";

import React from "react";
import { PanelGrid } from "@/components/layout/PanelGrid";
import { ChartPanel } from "@/components/panels/ChartPanel";
import { WatchlistPanel } from "@/components/panels/WatchlistPanel";
import { NewsFeedPanel } from "@/components/panels/NewsFeedPanel";
import { PortfolioPanel } from "@/components/panels/PortfolioPanel";
import { OptionsChainPanel } from "@/components/panels/OptionsChainPanel";
import { OrderBookPanel } from "@/components/panels/OrderBookPanel";
import { TimeAndSalesPanel } from "@/components/panels/TimeAndSalesPanel";
import { RiskPanel } from "@/components/panels/RiskPanel";
import { ScreenerPanel } from "@/components/panels/ScreenerPanel";
import { AlertsPanel } from "@/components/panels/AlertsPanel";
import { MacroPanel } from "@/components/panels/MacroPanel";
import { HeatMapPanel } from "@/components/panels/HeatMapPanel";
import { CorrelationMatrixPanel } from "@/components/panels/CorrelationMatrixPanel";
import { EconomicCalendarPanel } from "@/components/panels/EconomicCalendarPanel";
import { DarkPoolPanel } from "@/components/panels/DarkPoolPanel";
import { CryptoPanel } from "@/components/panels/CryptoPanel";
import { PerformancePanel } from "@/components/panels/PerformancePanel";
import { MultiTimeframePanel } from "@/components/panels/MultiTimeframePanel";
import { OrderEntryPanel } from "@/components/panels/OrderEntryPanel";
import { MarketDataProvider } from "@/components/providers/MarketDataProvider";

/**
 * Main dashboard page — the full panel grid.
 *
 * MarketDataProvider mounts the single WebSocket connection for the session.
 * All 16 panels (ST-9 + ST-10) are rendered; layout is controlled by PanelGrid.
 *
 * Panel groups:
 *  Row 1 — Chart + Watchlist
 *  Row 2 — Portfolio + Risk
 *  Row 3 — Order Book + Time & Sales
 *  Row 4 — Options Chain + News & AI Sentiment
 *  Row 5 — Screener + Alerts
 *  Row 6 — Macro + Economic Calendar
 *  Row 7 — Heat Map + Correlation Matrix
 *  Row 8 — Dark Pool / Unusual Options + Crypto
 */
export default function DashboardPage() {
  return (
    <MarketDataProvider>
      <PanelGrid>
        {/* ── Row 1 — Primary charting + watchlist ── */}
        <div key="chart">
          <ChartPanel panelId="chart" />
        </div>

        <div key="watchlist">
          <WatchlistPanel panelId="watchlist" />
        </div>

        {/* ── Row 2 — Portfolio overview + risk analytics ── */}
        <div key="portfolio">
          <PortfolioPanel panelId="portfolio" />
        </div>

        <div key="risk">
          <RiskPanel panelId="risk" />
        </div>

        {/* ── Row 3 — Level 2 / Order book + Time & Sales tape ── */}
        <div key="orderbook">
          <OrderBookPanel panelId="orderbook" defaultSymbol="AAPL" />
        </div>

        <div key="tape">
          <TimeAndSalesPanel panelId="tape" defaultSymbol="AAPL" />
        </div>

        {/* ── Row 4 — Options chain + News & AI sentiment ── */}
        <div key="options">
          <OptionsChainPanel panelId="options" defaultSymbol="AAPL" />
        </div>

        <div key="news">
          <NewsFeedPanel panelId="news" />
        </div>

        {/* ── Row 5 — Screener + Alert manager ── */}
        <div key="screener">
          <ScreenerPanel panelId="screener" />
        </div>

        <div key="alerts">
          <AlertsPanel panelId="alerts" />
        </div>

        {/* ── Row 6 — Macro overview + Economic calendar ── */}
        <div key="macro">
          <MacroPanel panelId="macro" />
        </div>

        <div key="calendar">
          <EconomicCalendarPanel panelId="calendar" />
        </div>

        {/* ── Row 7 — Sector heat map + Correlation matrix ── */}
        <div key="heatmap">
          <HeatMapPanel panelId="heatmap" />
        </div>

        <div key="correlation">
          <CorrelationMatrixPanel panelId="correlation" />
        </div>

        {/* ── Row 8 — Unusual options activity / dark pool + Crypto ── */}
        <div key="darkpool">
          <DarkPoolPanel panelId="darkpool" />
        </div>

        <div key="crypto">
          <CryptoPanel panelId="crypto" />
        </div>

        {/* ── Row 9 — Performance analytics + Multi-timeframe ── */}
        <div key="performance">
          <PerformancePanel panelId="performance" />
        </div>

        <div key="mtf">
          <MultiTimeframePanel panelId="mtf" defaultSymbol="AAPL" />
        </div>

        {/* ── Row 10 — Order entry (paper trading) ── */}
        <div key="order-entry">
          <OrderEntryPanel panelId="order-entry" defaultSymbol="AAPL" />
        </div>
      </PanelGrid>
    </MarketDataProvider>
  );
}
