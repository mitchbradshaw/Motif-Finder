import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// The examiners' build (`npm run build:demo` → dist-demo/, served with run_server.py --sandbox --dist):
// the unfinished Cross-channel page loses its entry points and a typed link lands on Signal. It lives
// here, not in src/, so the normal build is byte-for-byte what it was (sourcemaps embed every source).
const demo = (): Plugin => ({
  name: 'demo-hide', transformIndexHtml: () => [
    { tag: 'style', injectTo: 'head', children: '[data-testid="mode-seg"],[data-testid="cross-channel-from"]{display:none!important}' },
    { tag: 'script', injectTo: 'head', children: `(() => { const go = e => { const m = location.hash.match(/^#\\/explore\\/cross-channel\\/(\\d+)/)
      if (m) { e && e.stopImmediatePropagation(); location.replace('#/explore/signal/' + m[1]) } }; go(); addEventListener('hashchange', go) })()` },
  ],
})

// Dev: `npm run dev` serves the client on 5173 and proxies /api to the FastAPI
// bridge on 8765 (run_server.py). Prod: `npm run build` writes dist/, which the
// bridge serves itself, so one process answers everything.
export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'demo' ? [demo()] : [])],
  server: {
    host: '127.0.0.1',   // Vite 8 otherwise binds ::1 only on this machine (builders' finding)
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } },
  },
  build: { outDir: mode === 'demo' ? 'dist-demo' : 'dist', sourcemap: true, chunkSizeWarningLimit: 1200 },
}))
