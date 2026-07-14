import React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TickerTape } from "@/components/layout/TickerTape";

/**
 * Dashboard route group layout.
 * Renders: Sidebar | [TickerTape + Content area]
 * This is a SERVER component — no client state here.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* Left sidebar */}
      <Sidebar />

      {/* Main content column */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Real-time ticker tape */}
        <TickerTape />

        {/* Page content (panel grid or full-page view) */}
        <main style={{ flex: 1, overflow: "auto" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
