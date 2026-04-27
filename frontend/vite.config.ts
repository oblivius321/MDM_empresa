import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  // No proxy do Vite em Docker, o backend continua no nome do servico e porta interna 8000.
  // A exposicao no host segue em 8200.
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://backend:8000';
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || '')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean);

  return {
    server: {
      host: "0.0.0.0",
      port: 3000,
      allowedHosts,
      headers: {
        "Cache-Control": "no-store",
      },
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
    optimizeDeps: {
      include: ["@radix-ui/react-dialog"],
    },
  };
});
