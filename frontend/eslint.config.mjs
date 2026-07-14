import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

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
    rules: {
      // Data-fetching effects that set loading/error state are valid patterns.
      // The rule "no setState synchronously in effects" applies to external state
      // sync patterns, not async data-fetch lifecycle management.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
