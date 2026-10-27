import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In dev (and the compose stack) /api is proxied to the Flask service.
const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": apiTarget } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    css: false,
  },
});
