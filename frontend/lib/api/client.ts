/**
 * API client — wraps fetch with auth headers, base URL, and 401 refresh logic.
 *
 * All requests go through apiRequest(). Tokens are managed via the auth store.
 * On 401, an automatic refresh attempt is made before failing.
 * On refresh failure, auth is cleared and the user is redirected to /login.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

// ─── Token accessors (store-independent, safe for SSR guards) ────────────────
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("quantnexus-auth");
    if (!raw) return null;
    return (JSON.parse(raw) as { state?: { accessToken?: string } }).state
      ?.accessToken ?? null;
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("quantnexus-auth");
    if (!raw) return null;
    return (JSON.parse(raw) as { state?: { refreshToken?: string } }).state
      ?.refreshToken ?? null;
  } catch {
    return null;
  }
}

export function storeTokens(access: string, refresh: string): void {
  // Delegate to authStore — this function is called from non-React contexts.
  // We manipulate localStorage directly to stay out of React's render cycle.
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem("quantnexus-auth");
    const stored = raw
      ? (JSON.parse(raw) as { state?: Record<string, unknown> })
      : { state: {} };
    stored.state = {
      ...(stored.state ?? {}),
      accessToken: access,
      refreshToken: refresh,
    };
    localStorage.setItem("quantnexus-auth", JSON.stringify(stored));
  } catch {
    // Silently fail — caller will get 401 on next request and be redirected
  }
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("quantnexus-auth");
}

// ─── Token refresh ────────────────────────────────────────────────────────────
let _refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  // Deduplicate concurrent refresh calls
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return null;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) {
        clearTokens();
        return null;
      }
      const data = (await res.json()) as {
        access_token: string;
        refresh_token: string;
      };
      storeTokens(data.access_token, data.refresh_token);
      return data.access_token;
    } catch {
      clearTokens();
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

// ─── Core request function ───────────────────────────────────────────────────
export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } else {
      // Redirect to login on auth failure (client-side only)
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please log in again.");
    }
  }

  if (!res.ok) {
    const errorBody = await res
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(
      (errorBody as { detail: string }).detail ?? "Request failed"
    );
  }

  return res.json() as Promise<T>;
}
