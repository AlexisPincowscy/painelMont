import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // O front fala com a API FastAPI. Proxy no dev evita configuração de CORS
    // no navegador e mantém as URLs relativas iguais em dev e em produção.
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
