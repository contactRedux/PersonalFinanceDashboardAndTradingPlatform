/**
 * useAuth hook — login/logout actions wired to authStore + API.
 */
"use client";

import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { login as apiLogin, logout as apiLogout, getMe } from "@/lib/api/auth";
import type { LoginRequest } from "@/types/api";

export function useAuth() {
  const { user, accessToken, setTokens, setUser, clearAuth, isAuthenticated } =
    useAuthStore();
  const router = useRouter();

  // Hydrate user profile on mount if we have a token but no user object
  useEffect(() => {
    if (accessToken && !user) {
      getMe()
        .then(setUser)
        .catch(() => {
          // Token is invalid — clear and redirect
          clearAuth();
          router.replace("/login");
        });
    }
  }, [accessToken, user, setUser, clearAuth, router]);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      const tokens = await apiLogin(credentials);
      setTokens(tokens.access_token, tokens.refresh_token);
      // Fetch and store user profile
      const me = await getMe();
      setUser(me);
      return me;
    },
    [setTokens, setUser]
  );

  const logout = useCallback(async () => {
    await apiLogout().catch(() => {/* ignore network errors on logout */});
    clearAuth();
    router.replace("/login");
  }, [clearAuth, router]);

  return {
    user,
    isAuthenticated: isAuthenticated(),
    login,
    logout,
  };
}
