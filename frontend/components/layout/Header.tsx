"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { logout as apiLogout } from "@/lib/api/auth";
import { clearTokens } from "@/lib/api/client";

/**
 * Header — top bar of the dashboard.
 * Contains: symbol search input (left), platform time clock (center), user menu (right).
 * All state is client-side.
 */
export function Header() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  const [searchQuery, setSearchQuery] = useState("");
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [clock, setClock] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  // Live clock (UTC)
  useEffect(() => {
    function tick() {
      const now = new Date();
      const time = now.toISOString().slice(11, 19); // HH:MM:SS
      setClock(`UTC ${time}`);
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    if (userMenuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [userMenuOpen]);

  const handleLogout = useCallback(async () => {
    setUserMenuOpen(false);
    await apiLogout().catch(() => {/* best-effort */});
    clearAuth();
    clearTokens();
    router.replace("/login");
  }, [clearAuth, router]);

  const handleSearchSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      // Symbol search will be wired to /market/search in ST-5
      if (searchQuery.trim()) {
        // Navigate to charts page with symbol pre-selected
        router.push(`/charts?symbol=${encodeURIComponent(searchQuery.trim().toUpperCase())}`);
        setSearchQuery("");
      }
    },
    [searchQuery, router]
  );

  const roleBadgeColor: Record<string, string> = {
    admin: "#00d084",
    trader: "#0ea5e9",
    analyst: "#f59e0b",
    readonly: "#6b7280",
  };

  return (
    <div style={styles.header}>
      {/* Left: Symbol search */}
      <form onSubmit={handleSearchSubmit} style={styles.searchForm}>
        <span style={styles.searchIcon}>⌕</span>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search symbol or company…"
          style={styles.searchInput}
          aria-label="Search for a symbol"
          autoComplete="off"
          spellCheck={false}
        />
        {searchQuery && (
          <button
            type="button"
            style={styles.clearBtn}
            onClick={() => setSearchQuery("")}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </form>

      {/* Center: Clock */}
      <div style={styles.clock} aria-label="Current UTC time">
        {clock}
      </div>

      {/* Right: User menu */}
      <div ref={menuRef} style={styles.userSection}>
        <button
          style={styles.userButton}
          onClick={() => setUserMenuOpen((v) => !v)}
          aria-haspopup="true"
          aria-expanded={userMenuOpen}
          aria-label="User menu"
        >
          <span style={styles.userAvatar}>
            {user?.email?.[0]?.toUpperCase() ?? "?"}
          </span>
          <div style={styles.userInfo}>
            <span style={styles.userEmail}>{user?.email ?? "—"}</span>
            {user?.role && (
              <span
                style={{
                  ...styles.roleBadge,
                  color: roleBadgeColor[user.role] ?? "#6b7280",
                }}
              >
                {user.role.toUpperCase()}
              </span>
            )}
          </div>
          <span style={styles.chevron}>{userMenuOpen ? "▲" : "▼"}</span>
        </button>

        {userMenuOpen && (
          <div style={styles.dropdown} role="menu">
            <div style={styles.dropdownDivider} />
            <button
              style={styles.dropdownItem}
              onClick={() => { setUserMenuOpen(false); router.push("/settings"); }}
              role="menuitem"
            >
              Settings
            </button>
            <button
              style={{ ...styles.dropdownItem, color: "#ef4444" }}
              onClick={handleLogout}
              role="menuitem"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  header: {
    height: 36,
    background: "var(--color-bg-elevated)",
    borderBottom: "1px solid var(--color-bg-border)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 12px",
    gap: 12,
    flexShrink: 0,
    zIndex: "var(--z-header)" as unknown as number,
  },
  searchForm: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    flex: 1,
    maxWidth: 320,
    position: "relative",
  },
  searchIcon: {
    color: "var(--color-text-muted)",
    fontSize: 16,
    flexShrink: 0,
    lineHeight: 1,
  },
  searchInput: {
    flex: 1,
    background: "var(--color-bg-surface)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "3px 28px 3px 8px",
    fontSize: 12,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    outline: "none",
  },
  clearBtn: {
    position: "absolute",
    right: 6,
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "var(--color-text-muted)",
    fontSize: 16,
    lineHeight: 1,
    padding: 0,
  },
  clock: {
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    color: "var(--color-text-muted)",
    letterSpacing: "0.06em",
    userSelect: "none",
  },
  userSection: {
    position: "relative",
    flexShrink: 0,
  },
  userButton: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "4px 6px",
    borderRadius: 3,
    color: "var(--color-text-primary)",
  },
  userAvatar: {
    width: 22,
    height: 22,
    borderRadius: "50%",
    background: "var(--color-bg-separator)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: 700,
    color: "var(--color-text-primary)",
    fontFamily: "var(--font-mono)",
    flexShrink: 0,
  },
  userInfo: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: 1,
  },
  userEmail: {
    fontSize: 11,
    color: "var(--color-text-primary)",
    fontFamily: "var(--font-sans)",
    maxWidth: 140,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  roleBadge: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.06em",
  },
  chevron: {
    fontSize: 8,
    color: "var(--color-text-muted)",
  },
  dropdown: {
    position: "absolute",
    right: 0,
    top: "calc(100% + 4px)",
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 4,
    minWidth: 180,
    boxShadow: "0 8px 24px rgba(0,0,0,0.8)",
    zIndex: 100,
  },
  dropdownDivider: {
    height: 1,
    background: "var(--color-bg-border)",
    margin: "4px 0",
  },
  dropdownItem: {
    width: "100%",
    padding: "8px 12px",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 12,
    fontFamily: "var(--font-sans)",
    color: "var(--color-text-primary)",
    textAlign: "left" as const,
  },
};
