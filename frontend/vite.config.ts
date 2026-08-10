import vinext from "vinext";
import { defineConfig } from "vite";

/**
 * Vite config for the executive-ai-secretary frontend.
 *
 * The frontend is a thin client that talks to the FastAPI backend exposed
 * under /api/v1. During `npm run dev` we proxy /api/* to the local backend
 * so the browser can use same-origin requests with no CORS involvement.
 *
 * `npm run build` is consumed by `Dockerfile.web`, which hard-codes
 * `NEXT_PUBLIC_APP_MODE=production` so the thin dispatcher in
 * `app/page.tsx` selects the production application.
 */
export default defineConfig(() => ({
  server: {
    // 绑定 IPv6 ::（Node 默认 dual-stack，同时接受 IPv4 请求）
    // 避免浏览器把 localhost 解析到 ::1 时连接失败
    // （会导致 "Failed to fetch dynamically imported module"）
    host: "::",
    port: 3000,
    strictPort: true,   // 3000 被占时直接报错，不再 fallback
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  plugins: [vinext()],
}));
