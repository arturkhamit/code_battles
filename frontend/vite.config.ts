import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig(({ mode }) => {
  // dev proxy targets (see .env.example); the production entry point routes the same paths
  const env = loadEnv(mode, process.cwd(), "VITE_PROXY_")
  const django = env.VITE_PROXY_DJANGO || "http://localhost:8000"
  const fastapi = env.VITE_PROXY_FASTAPI || "http://localhost:8001"

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 3000,
      proxy: {
        "/api/accounts": { target: django, changeOrigin: true },
        "/api/battles": { target: django, changeOrigin: true },
        "/api/tasks": { target: fastapi, changeOrigin: true },
        "/ws": { target: fastapi, ws: true, changeOrigin: true },
      },
    },
  }
})
