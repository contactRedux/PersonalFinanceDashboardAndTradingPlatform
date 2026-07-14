"use client";

/**
 * QuantNexus — Login page.
 * Two-step form:
 *   Step 1: email + password
 *   Step 2: TOTP 6-digit code (if 2FA is enabled on the account)
 *
 * On success, redirects to /dashboard.
 * Styled with the Bloomberg terminal dark aesthetic from globals.css.
 */

import { useState, useRef, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { login as apiLogin, getMe } from "@/lib/api/auth";

type Step = "credentials" | "totp";

interface FieldError {
  email?: string;
  password?: string;
  totp?: string;
  general?: string;
}

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();

  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [errors, setErrors] = useState<FieldError>({});
  const [loading, setLoading] = useState(false);

  const emailRef = useRef<HTMLInputElement>(null);
  const totpRef = useRef<HTMLInputElement>(null);

  // ─── Client-side validation ─────────────────────────────────────────────────
  function validateCredentials(): FieldError {
    const errs: FieldError = {};
    if (!email.trim()) errs.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      errs.email = "Enter a valid email address.";
    if (!password) errs.password = "Password is required.";
    else if (password.length < 8)
      errs.password = "Password must be at least 8 characters.";
    return errs;
  }

  function validateTotp(): FieldError {
    const errs: FieldError = {};
    if (!totpCode.trim()) errs.totp = "Authentication code is required.";
    else if (!/^\d{6}$/.test(totpCode.replace(/\s/g, "")))
      errs.totp = "Enter the 6-digit code from your authenticator app.";
    return errs;
  }

  // ─── Form submission ────────────────────────────────────────────────────────
  const handleCredentialsSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const errs = validateCredentials();
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setLoading(true);

      try {
        const tokens = await apiLogin({ email, password });
        setTokens(tokens.access_token, tokens.refresh_token);
        const me = await getMe();
        setUser(me);
        router.replace("/dashboard");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Login failed.";
        // "TOTP code required" → advance to TOTP step
        if (message.toLowerCase().includes("totp")) {
          setStep("totp");
          setTimeout(() => totpRef.current?.focus(), 100);
        } else {
          setErrors({ general: message });
        }
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [email, password]
  );

  const handleTotpSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const errs = validateTotp();
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setLoading(true);

      try {
        const tokens = await apiLogin({
          email,
          password,
          totp_code: totpCode.replace(/\s/g, ""),
        });
        setTokens(tokens.access_token, tokens.refresh_token);
        const me = await getMe();
        setUser(me);
        router.replace("/dashboard");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Login failed.";
        setErrors({ totp: message });
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [email, password, totpCode]
  );

  // ─── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={styles.card}>
      {/* Logo / Platform header */}
      <div style={styles.header}>
        <div style={styles.logo}>QN</div>
        <div>
          <div style={styles.platformName}>QuantNexus</div>
          <div style={styles.platformTagline}>Enterprise Trading Terminal</div>
        </div>
      </div>

      <div style={styles.divider} />

      {/* Step: Credentials */}
      {step === "credentials" && (
        <form onSubmit={handleCredentialsSubmit} noValidate>
          <div style={styles.formTitle}>Sign in to your account</div>

          {errors.general && (
            <div style={styles.errorBanner} role="alert">
              {errors.general}
            </div>
          )}

          <div style={styles.field}>
            <label htmlFor="email" style={styles.label}>
              Email address
            </label>
            <input
              ref={emailRef}
              id="email"
              type="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                ...styles.input,
                ...(errors.email ? styles.inputError : {}),
              }}
              placeholder="trader@quantnexus.io"
              aria-describedby={errors.email ? "email-error" : undefined}
              aria-invalid={!!errors.email}
            />
            {errors.email && (
              <span id="email-error" style={styles.fieldError}>
                {errors.email}
              </span>
            )}
          </div>

          <div style={styles.field}>
            <label htmlFor="password" style={styles.label}>
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                ...styles.input,
                ...(errors.password ? styles.inputError : {}),
              }}
              placeholder="••••••••••••"
              aria-describedby={errors.password ? "password-error" : undefined}
              aria-invalid={!!errors.password}
            />
            {errors.password && (
              <span id="password-error" style={styles.fieldError}>
                {errors.password}
              </span>
            )}
          </div>

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? (
              <span style={styles.spinner} aria-label="Signing in…" />
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      )}

      {/* Step: TOTP */}
      {step === "totp" && (
        <form onSubmit={handleTotpSubmit} noValidate>
          <div style={styles.formTitle}>Two-factor authentication</div>
          <div style={styles.formSubtitle}>
            Enter the 6-digit code from your authenticator app.
          </div>

          {errors.totp && (
            <div style={styles.errorBanner} role="alert">
              {errors.totp}
            </div>
          )}

          <div style={styles.field}>
            <label htmlFor="totp" style={styles.label}>
              Authentication code
            </label>
            <input
              ref={totpRef}
              id="totp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={7} /* 6 digits + optional space */
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              style={{
                ...styles.input,
                ...styles.totpInput,
                ...(errors.totp ? styles.inputError : {}),
              }}
              placeholder="000 000"
              aria-describedby={errors.totp ? "totp-error" : undefined}
              aria-invalid={!!errors.totp}
            />
            {errors.totp && (
              <span id="totp-error" style={styles.fieldError}>
                {errors.totp}
              </span>
            )}
          </div>

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? (
              <span style={styles.spinner} aria-label="Verifying…" />
            ) : (
              "Verify"
            )}
          </button>

          <button
            type="button"
            style={styles.backButton}
            onClick={() => {
              setStep("credentials");
              setTotpCode("");
              setErrors({});
            }}
          >
            ← Back to sign in
          </button>
        </form>
      )}

      {/* Security disclaimer */}
      <div style={styles.disclaimer}>
        This system is for authorised users only. All access is monitored and
        logged. Unauthorised access is strictly prohibited.
      </div>
    </div>
  );
}

// ─── Inline styles — terminal aesthetic ────────────────────────────────────────
// Inline styles are intentional for the login page to work without Tailwind
// class compilation issues in the auth route group (no layout.tsx imports globals.css).
const styles: Record<string, React.CSSProperties> = {
  card: {
    width: "100%",
    maxWidth: 400,
    background: "#0a0a0a",
    border: "1px solid #222222",
    borderRadius: 4,
    padding: "32px 28px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    marginBottom: 20,
  },
  logo: {
    width: 40,
    height: 40,
    background: "#00d084",
    borderRadius: 3,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: 800,
    fontSize: 14,
    color: "#000",
    flexShrink: 0,
    letterSpacing: "0.04em",
  },
  platformName: {
    fontFamily: "'Inter', sans-serif",
    fontSize: 18,
    fontWeight: 700,
    color: "#e8e8e8",
    letterSpacing: "-0.02em",
  },
  platformTagline: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10,
    color: "#555555",
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    marginTop: 2,
  },
  divider: {
    height: 1,
    background: "#222222",
    marginBottom: 24,
  },
  formTitle: {
    fontFamily: "'Inter', sans-serif",
    fontSize: 14,
    fontWeight: 600,
    color: "#e8e8e8",
    marginBottom: 4,
  },
  formSubtitle: {
    fontFamily: "'Inter', sans-serif",
    fontSize: 12,
    color: "#8a8a8a",
    marginBottom: 20,
  },
  errorBanner: {
    background: "rgba(239, 68, 68, 0.08)",
    border: "1px solid rgba(239, 68, 68, 0.25)",
    borderRadius: 3,
    padding: "8px 12px",
    fontSize: 12,
    color: "#ef4444",
    marginBottom: 16,
    fontFamily: "'Inter', sans-serif",
  },
  field: {
    marginBottom: 16,
  },
  label: {
    display: "block",
    fontSize: 11,
    fontWeight: 500,
    color: "#8a8a8a",
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
    marginBottom: 6,
    fontFamily: "'Inter', sans-serif",
  },
  input: {
    width: "100%",
    background: "#111111",
    border: "1px solid #333333",
    borderRadius: 3,
    padding: "9px 12px",
    fontSize: 13,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e8e8e8",
    outline: "none",
    boxSizing: "border-box" as const,
    transition: "border-color 0.15s ease",
  },
  inputError: {
    borderColor: "#ef4444",
  },
  totpInput: {
    fontSize: 20,
    letterSpacing: "0.3em",
    textAlign: "center" as const,
  },
  fieldError: {
    display: "block",
    fontSize: 11,
    color: "#ef4444",
    marginTop: 4,
    fontFamily: "'Inter', sans-serif",
  },
  button: {
    width: "100%",
    padding: "10px 16px",
    background: "#00d084",
    border: "none",
    borderRadius: 3,
    fontSize: 13,
    fontWeight: 600,
    fontFamily: "'Inter', sans-serif",
    color: "#000000",
    cursor: "pointer",
    marginTop: 8,
    letterSpacing: "0.02em",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    transition: "background 0.15s ease",
  },
  backButton: {
    width: "100%",
    padding: "8px 16px",
    background: "transparent",
    border: "1px solid #333333",
    borderRadius: 3,
    fontSize: 12,
    fontFamily: "'Inter', sans-serif",
    color: "#8a8a8a",
    cursor: "pointer",
    marginTop: 8,
    letterSpacing: "0.02em",
  },
  spinner: {
    display: "inline-block",
    width: 14,
    height: 14,
    border: "2px solid rgba(0,0,0,0.3)",
    borderTopColor: "#000",
    borderRadius: "50%",
    animation: "spin 0.6s linear infinite",
  },
  disclaimer: {
    marginTop: 24,
    fontSize: 10,
    color: "#555555",
    fontFamily: "'Inter', sans-serif",
    lineHeight: 1.5,
    textAlign: "center" as const,
    borderTop: "1px solid #1a1a1a",
    paddingTop: 16,
  },
};
