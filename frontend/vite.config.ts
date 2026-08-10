import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import qiankun from "vite-plugin-qiankun";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { configDefaults } from "vitest/config";

const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

// 部署子路径（生产如 /emergency-plan-migration，开发为空 → 根路径）
const BASE_PATH = (process.env.VITE_BASE_PATH || "").replace(/\/+$/, "");

// Node 24 has workbox-build compatibility issues
const majorVersion = parseInt(process.version.slice(1).split(".")[0], 10);
const skipPWA = majorVersion >= 24;

async function getPlugins() {
  const plugins: any[] = [
    react(),
    tailwindcss(),
    qiankun("emergency-plan", { useDevMode: true }),
  ];

  if (!skipPWA) {
    const { VitePWA } = await import("vite-plugin-pwa");
    plugins.push(VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/icon-192.png", "icons/icon-512.png"],
      manifest: {
        name: "数字化应急预案生成",
        short_name: "应急预案",
        description: "基于 GB/T 29639-2020 的数字化应急预案自动生成系统",
        theme_color: "#1A56DB",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: BASE_PATH ? `${BASE_PATH}/m/dashboard` : "/m/dashboard",
        scope: BASE_PATH ? `${BASE_PATH}/` : "/",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /^\/api\/v1\//,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 100, maxAgeSeconds: 3600 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /\.(?:woff2?)$/,
            handler: "CacheFirst",
            options: { cacheName: "fonts", expiration: { maxEntries: 20, maxAgeSeconds: 31536000 } },
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: "CacheFirst",
            options: { cacheName: "images", expiration: { maxEntries: 50, maxAgeSeconds: 2592000 } },
          },
        ],
      },
    }));
  } else {
    console.warn("[vite] PWA disabled: Node.js v" + majorVersion + " detected, workbox-build incompatible");
  }

  return plugins;
}

export default defineConfig(async () => ({
  base: BASE_PATH ? `${BASE_PATH}/` : "/",
  plugins: await getPlugins(),
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  cacheDir: process.env.VITE_CACHE_DIR || "node_modules/.vite",
  test: {
    // 单元测试限定 src 下 *.test.*；排除 e2e（Playwright）与仓库根遗留的 node:test 脚本
    include: ["src/**/*.test.{ts,tsx,mts,cts,js,mjs,cjs}"],
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
  server: {
    port: 5173,
    cors: true,
    origin: "http://localhost:5173",
    hmr: { protocol: "ws", host: "localhost" }, watch: { usePolling: true, interval: 500 },
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/uploads": { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "index.html"),
        mobile: path.resolve(__dirname, "m.html"),
      },
      output: {
        manualChunks: {
          "mobile-vendor": ["react", "react-dom", "react-router-dom"],
          "mobile-ui": ["framer-motion"],
          desktop: ["antd", "@ant-design/icons"],
        },
      },
    },
  },
}));
