import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import securityPlugin from "eslint-plugin-security";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // ─── Security plugin ────────────────────────────────────────────────────
    plugins: { security: securityPlugin },
    rules: {
      // Enforce most security rules as errors; audit these periodically.
      // detect-object-injection is disabled: extremely noisy on TypeScript
      // where array[i] and typed dict lookups are fully type-safe.
      "security/detect-object-injection":          "off",
      "security/detect-non-literal-regexp":        "warn",
      "security/detect-unsafe-regex":              "error",
      "security/detect-buffer-noassert":           "error",
      "security/detect-child-process":             "error",
      "security/detect-disable-mustache-escape":   "error",
      "security/detect-eval-with-expression":      "error",
      "security/detect-new-buffer":                "error",
      "security/detect-no-csrf-before-method-override": "error",
      "security/detect-possible-timing-attacks":   "warn",
      "security/detect-pseudoRandomBytes":         "error",
      "security/detect-non-literal-fs-filename":   "warn",
      "security/detect-non-literal-require":       "warn",

      // Data-fetching effects that set loading/error state are valid patterns.
      // The rule "no setState synchronously in effects" applies to external state
      // sync patterns, not async data-fetch lifecycle management.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
