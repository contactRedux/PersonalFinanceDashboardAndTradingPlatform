"use client";

import React from "react";
import { motion } from "framer-motion";

interface PanelProps {
  id: string;
  title: string;
  children: React.ReactNode;
  toolbar?: React.ReactNode;
  className?: string;
}

/**
 * Panel — the base container for every dashboard widget.
 * Title bar is the drag handle.
 * Content area scrolls independently.
 */
export function Panel({ id, title, children, toolbar, className = "" }: PanelProps) {
  return (
    <div className={`panel ${className}`} style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Drag handle — the panel-header css class enables cursor:move */}
      <div className="panel-header">
        <span style={{ color: "var(--color-text-secondary)", fontSize: "11px" }}>
          {title.toUpperCase()}
        </span>
        {toolbar && <div style={{ display: "flex", gap: 4, alignItems: "center" }}>{toolbar}</div>}
      </div>

      {/* Panel content — scrollable */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          position: "relative",
        }}
      >
        <motion.div
          key={id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.15 }}
          style={{ height: "100%" }}
        >
          {children}
        </motion.div>
      </div>
    </div>
  );
}
