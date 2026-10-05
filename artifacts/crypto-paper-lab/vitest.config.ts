import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

/**
 * Vitest configuration (Phase 18K).
 *
 * Added alongside the existing `vite.config.ts` rather than replacing it. The
 * production build's `PORT`/`BASE_PATH` requirement is a deployment contract and
 * has no business governing a test run, so the test config is standalone and
 * deliberately does not require those variables.
 *
 * `jsdom` provides the DOM. `@testing-library/react` needs a DOM and React's act
 * environment, and this is the smallest combination that supports the rendering
 * assertions Phase 18K requires. No second test framework was added.
 */
export default defineConfig({
  // Required, not optional. `vite.config.ts` uses `jsx: "preserve"` for esbuild,
  // but Vitest transforms JSX itself and the automatic runtime needs the plugin to
  // supply it — without this every `.tsx` test fails with "React is not defined".
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
    },
    dedupe: ["react", "react-dom"],
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});