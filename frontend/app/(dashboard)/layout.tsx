import React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { TickerTape } from "@/components/layout/TickerTape";

/**
 * Dashboard route group layout.
 * Renders: [Sidebar] | [Header + TickerTape + Content area]
 * This is a SERVER component shell — client components are inside.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* Left sidebar — navigation */}
      <Sidebar />

      {/* Main content column */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
        {/* Top header: symbol search + clock + user menu */}
        <Header />

        {/* Real-time ticker tape */}
        <TickerTape />

        {/* Page content (panel grid or full-page view) */}
        <main style={{ flex: 1, overflow: "auto", position: "relative" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
