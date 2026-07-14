"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/dashboard",   label: "Dashboard",   icon: "⬛" },
  { href: "/charts",      label: "Charts",      icon: "📈" },
  { href: "/screener",    label: "Screener",    icon: "🔍" },
  { href: "/settings",    label: "Settings",    icon: "⚙️" },
] as const;

/**
 * Sidebar — collapsible navigation panel.
 */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <div
      style={{
        width: 48,
        height: "100vh",
        background: "var(--color-bg-elevated)",
        borderRight: "1px solid var(--color-bg-border)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: 8,
        gap: 4,
        flexShrink: 0,
        zIndex: "var(--z-sidebar)",
        position: "sticky",
        top: 0,
      }}
    >
      {/* Logo */}
      <div
        style={{
          width: 32,
          height: 32,
          background: "var(--color-accent-green)",
          borderRadius: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 12,
          fontSize: 14,
          fontWeight: 700,
          color: "#000",
          fontFamily: "var(--font-mono)",
          flexShrink: 0,
        }}
      >
        QN
      </div>

      {/* Nav items */}
      {NAV_ITEMS.map(({ href, label, icon }) => {
        const active = pathname === href || (href !== "/dashboard" && pathname?.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            title={label}
            style={{
              width: 36,
              height: 36,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 3,
              background: active ? "var(--color-accent-green-bg)" : "transparent",
              border: active ? "1px solid rgba(0,208,132,0.25)" : "1px solid transparent",
              fontSize: 16,
              textDecoration: "none",
              flexShrink: 0,
              cursor: "pointer",
              transition: "background 0.15s",
            }}
          >
            {icon}
          </Link>
        );
      })}
    </div>
  );
}
