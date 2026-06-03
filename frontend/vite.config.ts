import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
    },
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Splits de zware vendor-libs van de app-code zodat de eerste load sneller is
        // en charts pas hoeven te laden waar ze gebruikt worden.
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("recharts") || id.includes("d3")) return "charts";
            return "vendor";
          }
        },
      },
    },
  },
});
