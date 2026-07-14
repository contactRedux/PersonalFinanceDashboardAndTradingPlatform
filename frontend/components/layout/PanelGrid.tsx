"use client";

import React from "react";
import {
  useContainerWidth,
  ReactGridLayout as GridLayout,
} from "react-grid-layout";
import type { Layout, LayoutItem as RGLLayoutItem } from "react-grid-layout";
import { useLayoutStore } from "@/store/layoutStore";
import type { LayoutItem } from "@/store/layoutStore";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

/**
 * PanelGrid — wraps react-grid-layout (v2.2) with the QuantNexus terminal layout.
 * Uses useContainerWidth hook + ReactGridLayout component.
 * Panels are dragged by their .panel-header handle.
 * Layout is persisted to localStorage via useLayoutStore.
 */
interface PanelGridProps {
  children: React.ReactNode;
}

export function PanelGrid({ children }: PanelGridProps) {
  const { containerRef, width } = useContainerWidth({ initialWidth: 1280 });
  const { layout, setLayout } = useLayoutStore();

  const handleLayoutChange = (newLayout: Layout) => {
    // Cast to our local LayoutItem[] type (structurally compatible)
    setLayout(newLayout as unknown as LayoutItem[]);
  };

  return (
    <div ref={containerRef} style={{ width: "100%" }}>
      <GridLayout
        width={width}
        layout={layout as unknown as RGLLayoutItem[]}
        gridConfig={{
          cols: 12,
          rowHeight: 30,
          margin: [4, 4],
          containerPadding: [4, 4],
          maxRows: Infinity,
        }}
        dragConfig={{
          handle: ".panel-header",
        }}
        resizeConfig={{
          handles: ["se"],
        }}
        onLayoutChange={handleLayoutChange}
        className="layout"
        style={{
          background: "var(--color-bg-base)",
          minHeight: "calc(100vh - 28px - 36px)",
        }}
      >
        {children}
      </GridLayout>
    </div>
  );
}
