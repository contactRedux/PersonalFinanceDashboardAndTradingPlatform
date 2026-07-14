"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  listWorkspaces,
  createWorkspace,
  inviteMember,
  type Workspace,
} from "@/lib/api/workspaces";
import { updateWorkspace } from "@/lib/api/workspaces";
import { useLayoutStore } from "@/store/layoutStore";

/**
 * WorkspaceSwitcher — compact toolbar component for the navbar.
 *
 * Features:
 *  - Dropdown listing all workspaces (owner + member)
 *  - "＋ New" inline name input + create
 *  - "Share" per-workspace opens invite popover
 *  - Selecting a workspace saves current layout then loads the new one
 */
export function WorkspaceSwitcher() {
  const layout = useLayoutStore((s) => s.layout);
  const activeWorkspaceId = useLayoutStore((s) => s.activeWorkspaceId);
  const setActiveWorkspaceId = useLayoutStore((s) => s.setActiveWorkspaceId);
  const setLayout = useLayoutStore((s) => s.setLayout);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [showNewInput, setShowNewInput] = useState(false);
  const [creating, setCreating] = useState(false);
  const [shareWorkspaceId, setShareWorkspaceId] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [inviting, setInviting] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load workspaces on mount
  useEffect(() => {
    listWorkspaces()
      .then((r) => setWorkspaces(r.workspaces))
      .catch(() => {/* no-op: unauthenticated or network error */});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setShareWorkspaceId(null);
      }
    }
    if (open) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const activeName = workspaces.find((w) => w.id === activeWorkspaceId)?.name ?? "Default";

  const handleSelect = useCallback(
    async (ws: Workspace) => {
      // Save current layout to the currently active workspace before switching
      if (activeWorkspaceId) {
        await updateWorkspace(activeWorkspaceId, layout).catch(() => {/* best-effort */});
      }
      setActiveWorkspaceId(ws.id);
      // Load the new workspace's layout — for now the API returns the stored layout
      // in the workspace object itself; extend when backend returns layout in GET /workspaces
      setOpen(false);
    },
    [activeWorkspaceId, layout, setActiveWorkspaceId]
  );

  const handleCreate = useCallback(async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      const created = await createWorkspace(name);
      setWorkspaces((prev) => [created, ...prev]);
      setActiveWorkspaceId(created.id);
      setNewName("");
      setShowNewInput(false);
      setOpen(false);
    } catch {
      /* best-effort */
    } finally {
      setCreating(false);
    }
  }, [newName, setActiveWorkspaceId]);

  const handleInvite = useCallback(async () => {
    if (!shareWorkspaceId || !inviteEmail.trim()) return;
    setInviting(true);
    try {
      await inviteMember(shareWorkspaceId, inviteEmail.trim(), inviteRole);
      setInviteEmail("");
      setShareWorkspaceId(null);
    } catch {
      /* best-effort */
    } finally {
      setInviting(false);
    }
  }, [shareWorkspaceId, inviteEmail, inviteRole]);

  return (
    <div ref={dropdownRef} style={styles.container}>
      {/* Trigger button */}
      <button
        style={styles.trigger}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Workspace switcher"
      >
        <span style={styles.triggerIcon}>⬡</span>
        <span style={styles.triggerLabel}>{activeName}</span>
        <span style={styles.chevron}>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div style={styles.dropdown} role="listbox" aria-label="Workspaces list">
          {/* Workspace list */}
          {workspaces.length === 0 && (
            <div style={styles.empty}>No workspaces yet</div>
          )}
          {workspaces.map((ws) => (
            <div key={ws.id} style={styles.wsRow}>
              <button
                style={{
                  ...styles.wsItem,
                  ...(ws.id === activeWorkspaceId ? styles.wsItemActive : {}),
                }}
                onClick={() => handleSelect(ws)}
                role="option"
                aria-selected={ws.id === activeWorkspaceId}
                aria-label={`Switch to workspace ${ws.name}`}
              >
                {ws.name}
              </button>
              <button
                style={styles.shareBtn}
                onClick={(e) => {
                  e.stopPropagation();
                  setShareWorkspaceId(ws.id === shareWorkspaceId ? null : ws.id);
                }}
                aria-label={`Share workspace ${ws.name}`}
              >
                Share
              </button>
            </div>
          ))}

          <div style={styles.divider} />

          {/* New workspace */}
          {!showNewInput ? (
            <button
              style={styles.newBtn}
              onClick={() => setShowNewInput(true)}
              aria-label="Create new workspace"
            >
              ＋ New
            </button>
          ) : (
            <div style={styles.newRow}>
              <input
                autoFocus
                style={styles.newInput}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Workspace name…"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") { setShowNewInput(false); setNewName(""); }
                }}
                aria-label="New workspace name"
              />
              <button
                style={styles.createBtn}
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                aria-label="Confirm create workspace"
              >
                {creating ? "…" : "Create"}
              </button>
            </div>
          )}

          {/* Share / invite popover */}
          {shareWorkspaceId && (
            <div style={styles.sharePanel} aria-label="Invite member">
              <div style={styles.shareTitle}>Invite to workspace</div>
              <input
                style={styles.shareInput}
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="User ID or email…"
                aria-label="Invite user ID"
              />
              <select
                style={styles.roleSelect}
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                aria-label="Invite role"
              >
                <option value="viewer">Viewer</option>
                <option value="editor">Editor</option>
                <option value="owner">Owner</option>
              </select>
              <button
                style={styles.inviteBtn}
                onClick={handleInvite}
                disabled={inviting || !inviteEmail.trim()}
                aria-label="Send invite"
              >
                {inviting ? "…" : "Invite"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "relative",
    flexShrink: 0,
  },
  trigger: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    background: "#1a1a1a",
    border: "1px solid #2a2a2a",
    borderRadius: 3,
    padding: "3px 8px",
    cursor: "pointer",
    color: "#e8e8e8",
    fontSize: 11,
    fontFamily: "var(--font-mono, monospace)",
    whiteSpace: "nowrap",
  },
  triggerIcon: {
    fontSize: 12,
    color: "#888",
  },
  triggerLabel: {
    maxWidth: 120,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  chevron: {
    fontSize: 7,
    color: "#888",
  },
  dropdown: {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: 0,
    background: "#0d0d0d",
    border: "1px solid #2a2a2a",
    borderRadius: 4,
    minWidth: 200,
    boxShadow: "0 8px 24px rgba(0,0,0,0.8)",
    zIndex: 200,
    padding: "4px 0",
  },
  empty: {
    padding: "8px 12px",
    fontSize: 11,
    color: "#666",
    fontFamily: "var(--font-mono, monospace)",
  },
  wsRow: {
    display: "flex",
    alignItems: "center",
  },
  wsItem: {
    flex: 1,
    padding: "7px 12px",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 12,
    color: "#e8e8e8",
    textAlign: "left",
    fontFamily: "var(--font-sans, sans-serif)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  wsItemActive: {
    color: "#00d084",
    fontWeight: 600,
  },
  shareBtn: {
    padding: "4px 8px",
    background: "none",
    border: "1px solid #333",
    borderRadius: 3,
    cursor: "pointer",
    fontSize: 10,
    color: "#888",
    marginRight: 6,
    flexShrink: 0,
  },
  divider: {
    height: 1,
    background: "#1e1e1e",
    margin: "4px 0",
  },
  newBtn: {
    width: "100%",
    padding: "7px 12px",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 12,
    color: "#0ea5e9",
    textAlign: "left",
    fontFamily: "var(--font-sans, sans-serif)",
  },
  newRow: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "4px 8px",
  },
  newInput: {
    flex: 1,
    background: "#1a1a1a",
    border: "1px solid #333",
    borderRadius: 3,
    padding: "4px 8px",
    fontSize: 11,
    color: "#e8e8e8",
    fontFamily: "var(--font-mono, monospace)",
    outline: "none",
  },
  createBtn: {
    padding: "4px 8px",
    background: "#0ea5e9",
    border: "none",
    borderRadius: 3,
    cursor: "pointer",
    fontSize: 11,
    color: "#000",
    fontWeight: 600,
    flexShrink: 0,
  },
  sharePanel: {
    padding: "8px 10px",
    borderTop: "1px solid #1e1e1e",
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  shareTitle: {
    fontSize: 10,
    color: "#888",
    fontFamily: "var(--font-mono, monospace)",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
  },
  shareInput: {
    background: "#1a1a1a",
    border: "1px solid #333",
    borderRadius: 3,
    padding: "4px 8px",
    fontSize: 11,
    color: "#e8e8e8",
    fontFamily: "var(--font-mono, monospace)",
    outline: "none",
  },
  roleSelect: {
    background: "#1a1a1a",
    border: "1px solid #333",
    borderRadius: 3,
    padding: "4px 8px",
    fontSize: 11,
    color: "#e8e8e8",
    fontFamily: "var(--font-mono, monospace)",
    cursor: "pointer",
    outline: "none",
  },
  inviteBtn: {
    padding: "5px 10px",
    background: "#0ea5e9",
    border: "none",
    borderRadius: 3,
    cursor: "pointer",
    fontSize: 11,
    color: "#000",
    fontWeight: 600,
  },
};
