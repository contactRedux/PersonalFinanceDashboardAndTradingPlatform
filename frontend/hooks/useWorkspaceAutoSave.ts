/**
 * useWorkspaceAutoSave — debounced auto-save of layout to the active workspace.
 *
 * When `activeWorkspaceId` is non-null and `layout` changes, calls
 * `updateWorkspace` after a 2-second debounce.
 */
"use client";

import { useEffect, useRef } from "react";
import { useLayoutStore } from "@/store/layoutStore";
import { updateWorkspace } from "@/lib/api/workspaces";

const DEBOUNCE_MS = 2000;

export function useWorkspaceAutoSave(): void {
  const layout = useLayoutStore((s) => s.layout);
  const activeWorkspaceId = useLayoutStore((s) => s.activeWorkspaceId);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!activeWorkspaceId) return;

    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      updateWorkspace(activeWorkspaceId, layout).catch(() => {
        // best-effort: ignore network/auth errors during auto-save
      });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [layout, activeWorkspaceId]);
}
