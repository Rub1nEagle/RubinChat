import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// During `npm run dev` we proxy /api and /ws to the FastAPI backend,
// so the Vite dev server can run independently with HMR while still
// hitting real endpoints.
export default defineConfig({
    plugins: [svelte()],
    server: {
        port: 5173,
        proxy: {
            "/api": "http://localhost:8000",
            "/ws": { target: "ws://localhost:8000", ws: true },
        },
    },
    build: {
        outDir: "dist",
        emptyOutDir: true,
        sourcemap: false,
    },
});
