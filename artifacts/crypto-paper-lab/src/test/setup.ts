/**
 * Test environment setup (Phase 18K).
 *
 * One job: make a missing stub an obvious failure rather than an opaque one.
 *
 * jsdom has no `fetch`, and every test that touches the client installs a stub. If
 * one were missing the test would fail with a confusing network error instead of
 * "this test forgot its stub", so the base client throws a named error instead.
 *
 * Deliberately **not** installed here: `@testing-library/jest-dom`. Phase 18's
 * approved dependency set was vitest, jsdom, `@testing-library/react` and
 * `@testing-library/dom`, and adding a fifth package for matchers would exceed it.
 * Assertions therefore use plain DOM properties — `textContent`, `getAttribute`,
 * `disabled` — which are sufficient and one fewer thing to keep in step.
 */

import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

/**
 * `ResizeObserver` stub.
 *
 * jsdom does not implement it, and `recharts`' `ResponsiveContainer` calls it to
 * size the chart. Without this, rendering the dashboard throws before any assertion
 * runs — a failure that reads as a component bug when it is an environment gap.
 *
 * The stub is inert: it never fires. Chart geometry is not what these tests check,
 * and a stub that emitted sizes would make assertions depend on a layout engine that
 * does not exist here.
 */
class StubResizeObserver implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

globalThis.ResizeObserver ??= StubResizeObserver;

/**
 * `matchMedia` stub.
 *
 * Present for the same reason: several shadcn primitives read it to pick a theme,
 * and jsdom leaves it undefined.
 */
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

const REAL_FETCH_MISSING =
  "A test called fetch without installing a stub. Use makeApi() from test/fixtures.";

beforeEach(() => {
  if (!globalThis.fetch) {
    globalThis.fetch = (() => {
      throw new Error(REAL_FETCH_MISSING);
    }) as unknown as typeof fetch;
  }
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});