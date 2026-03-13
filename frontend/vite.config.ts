import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  // Em Docker, use o nome do container. Localmente, use localhost:8000
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://backend:8000';

  return {
    server: {
      host: "0.0.0.0",
      port: 3000,
      hmr: {
        overlay: false,
      },
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
