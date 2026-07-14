/**
 * Zustand auth store — manages JWT tokens and current user state.
 * Tokens are stored in localStorage (client-side only).
 * A non-sensitive cookie `qn-authed=1` is maintained for the Edge middleware
 * route guard (the cookie contains no credentials — just a presence signal).
 * Server components never access this store.
 */
"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  id: string;
  email: string;
  role: "admin" | "trader" | "analyst" | "readonly";
  totp_enabled: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;

  // Actions
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: AuthUser) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

function setAuthCookie(value: "1" | "") {
  if (typeof document === "undefined") return;
  if (value) {
    // Strict SameSite, no Secure required (localhost dev), 7-day expiry
    const maxAge = 7 * 24 * 60 * 60;
    document.cookie = `qn-authed=1; path=/; max-age=${maxAge}; SameSite=Strict`;
  } else {
    document.cookie = "qn-authed=; path=/; max-age=0; SameSite=Strict";
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      setTokens: (access, refresh) => {
        set({ accessToken: access, refreshToken: refresh });
        setAuthCookie("1");
      },

      setUser: (user) => set({ user }),

      clearAuth: () => {
        set({ user: null, accessToken: null, refreshToken: null });
        setAuthCookie("");
      },

      isAuthenticated: () => get().accessToken !== null,
    }),
    {
      name: "quantnexus-auth",
      // Only persist tokens and user — do not persist ephemeral UI state
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
);
