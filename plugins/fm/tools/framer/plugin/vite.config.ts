import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import mkcert from "vite-plugin-mkcert"
import framer from "vite-plugin-framer"

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), mkcert(), framer()],
  server: { proxy: { "/bridge": { target: "http://127.0.0.1:3056", rewrite: p => p.replace(/^\/bridge/, ""), timeout: 60000, proxyTimeout: 60000 } } },
})
