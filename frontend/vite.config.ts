import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      "/api/internal": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/api/tasks": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8001",
        ws: true,
      },
    },
  },
})
