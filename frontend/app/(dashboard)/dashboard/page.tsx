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
import { MarketDataProvider } from "@/components/providers/MarketDataProvider";

/**
 * Main dashboard page — the core panel grid.
 * MarketDataProvider mounts the single WebSocket connection for the session.
 * All 8 primary panels are rendered — layout is controlled by PanelGrid.
 */
export default function DashboardPage() {
  return (
    <MarketDataProvider>
      <PanelGrid>
        {/* ── Row 1 ── */}
        <div key="chart">
          <ChartPanel panelId="chart" />
        </div>

        <div key="watchlist">
          <WatchlistPanel panelId="watchlist" />
        </div>

        {/* ── Row 2 ── */}
        <div key="portfolio">
          <PortfolioPanel panelId="portfolio" />
        </div>

        <div key="risk">
          <RiskPanel panelId="risk" />
        </div>

        {/* ── Row 3 ── */}
        <div key="orderbook">
          <OrderBookPanel panelId="orderbook" defaultSymbol="AAPL" />
        </div>

        <div key="tape">
          <TimeAndSalesPanel panelId="tape" defaultSymbol="AAPL" />
        </div>

        {/* ── Row 4 ── */}
        <div key="options">
          <OptionsChainPanel panelId="options" defaultSymbol="AAPL" />
        </div>

        {/* ── News & AI Sentiment ── */}
        <div key="news">
          <NewsFeedPanel panelId="news" />
        </div>
      </PanelGrid>
    </MarketDataProvider>
  );
}
