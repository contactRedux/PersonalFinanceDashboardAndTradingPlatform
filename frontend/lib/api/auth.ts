/**
 * Auth API functions — login, logout, me, TOTP.
 */
import { apiRequest, clearTokens, storeTokens } from "./client";
import type { TokenResponse, LoginRequest } from "@/types/api";
import type { AuthUser } from "@/store/authStore";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error((body as { detail: string }).detail ?? "Login failed");
  }
  const data = (await res.json()) as TokenResponse;
  storeTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest("/auth/logout", { method: "POST" });
  } finally {
    clearTokens();
  }
}

export async function getMe(): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/me");
}

export interface TOTPSetupResult {
  secret: string;
  uri: string;
}

export async function totpSetup(): Promise<TOTPSetupResult> {
  return apiRequest<TOTPSetupResult>("/auth/totp/setup", { method: "POST" });
}

export async function totpVerify(secret: string, code: string): Promise<void> {
  await apiRequest("/auth/totp/verify", {
    method: "POST",
    body: JSON.stringify({ secret, totp_code: code }),
  });
}
