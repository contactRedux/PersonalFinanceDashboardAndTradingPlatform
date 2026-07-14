/**
 * Vitest global setup — patches browser APIs that jsdom doesn't implement.
 */

// ─── window.matchMedia (required by lightweight-charts / fancy-canvas) ────────
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ─── ResizeObserver (react-grid-layout) ──────────────────────────────────────
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// ─── IntersectionObserver ─────────────────────────────────────────────────────
if (!window.IntersectionObserver) {
  (window as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
