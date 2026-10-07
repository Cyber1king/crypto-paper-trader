import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

import runtimeErrorOverlay from '@replit/vite-plugin-runtime-error-modal';

const rawPort = process.env.PORT;

if (!rawPort) {
  throw new Error(
    'PORT environment variable is required but was not provided.',
  );
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const basePath = process.env.BASE_PATH;

if (!basePath) {
  throw new Error(
    'BASE_PATH environment variable is required but was not provided.',
  );
}

/**
 * Origin of the Python paper-trading API.
 *
 * Read by the *dev server* only, to configure the proxy below. It is deliberately
 * not read by `src/lib/api.ts`, which keeps sending same-origin relative URLs, and
 * it never reaches the built bundle: `vite build` does not run a server, so a
 * production deployment is unaffected by this value and needs no API URL baked in.
 * A production deployment puts both under one origin, or a reverse proxy routes
 * `/api` the same way.
 */
const apiOrigin = process.env.PAPER_API_ORIGIN ?? 'http://127.0.0.1:8000';

/**
 * Same-origin proxy for the Python API (Phase 18L).
 *
 * The browser loads the dashboard from the Vite dev server and the API listens on a
 * different port. Two origins means the browser enforces CORS, and the API
 * deliberately registers no CORS middleware: it answers with no
 * `Access-Control-Allow-Origin` header, so a cross-origin `fetch` from the
 * dashboard is refused by the browser no matter how many times it is retried.
 * That is a deliberate backend design choice, not a missing feature, so the fix
 * belongs here rather than in the API.
 *
 * Proxying keeps the request same-origin: the dashboard sends `/api/modes`, the
 * dev server forwards it to the API, and the browser sees one origin throughout.
 *
 * `/api` is matched by prefix, which covers `/api/...` only. `/healthz` sits at the
 * root and needs its own entry. Both are listed explicitly rather than using a bare
 * catch-all, so a genuine frontend 404 still returns 404 instead of being forwarded
 * and reported as a confusing backend error.
 */
const proxy = {
  '/api': { target: apiOrigin, changeOrigin: false },
  '/healthz': { target: apiOrigin, changeOrigin: false },
};

export default defineConfig({
  base: basePath,
  plugins: [
    react(),
    tailwindcss(),
    runtimeErrorOverlay(),
    ...(process.env.NODE_ENV !== 'production' &&
    process.env.REPL_ID !== undefined
      ? [
          await import('@replit/vite-plugin-cartographer').then((m) =>
            m.cartographer({
              root: path.resolve(import.meta.dirname, '..'),
            }),
          ),
          await import('@replit/vite-plugin-dev-banner').then((m) =>
            m.devBanner(),
          ),
        ]
      : []),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      '@assets': path.resolve(
        import.meta.dirname,
        '..',
        '..',
        'attached_assets',
      ),
    },
    dedupe: ['react', 'react-dom'],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist/public'),
    emptyOutDir: true,
  },
  server: {
    port,
    strictPort: true,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy,
    fs: {
      strict: true,
    },
  },
  preview: {
    port,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy,
  },
});
