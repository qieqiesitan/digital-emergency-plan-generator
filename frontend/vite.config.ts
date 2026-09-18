import { defineConfig, type PluginOption } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { configDefaults } from "vitest/config";

const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

// 部署子路径（生产如 /emergency-plan-migration，开发为空 → 根路径）
const BASE_PATH = (process.env.VITE_BASE_PATH || "").replace(/\/+$/, "");

if (process.env.VITE_BASE_PATH && !process.env.VITE_BASE_PATH.startsWith("/")) {
  throw new Error(
    `VITE_BASE_PATH 必须以 / 开头（当前: "${process.env.VITE_BASE_PATH}"），例如 /emergency-plan-migration/`,
  );
}

// Node 24 与 workbox-build 不兼容：过去这里"静默跳过 PWA"，导致不同机器产出的
// 交付物不一致（一个有 Service Worker 一个没有）。现在改为**大声失败**，
// 强制使用 Node 22（frontend/Dockerfile 与 .github/workflows/ci.yml 均为 22）。
// 仅本地调试允许显式设置 ALLOW_PWA_SKIP=1 跳过。
const majorVersion = parseInt(process.version.slice(1).split(".")[0], 10);
if (majorVersion >= 24 && process.env.ALLOW_PWA_SKIP !== "1") {
  throw new Error(
    `构建环境 Node ${majorVersion} 与 workbox 不兼容，会导致 PWA 产物缺失。` +
    "请改用 Node 22（见 frontend/Dockerfile / CI 配置）；" +
    "若只是本地调试，可设置 ALLOW_PWA_SKIP=1 跳过 PWA。",
  );
}
const skipPWA = process.env.ALLOW_PWA_SKIP === "1";

async function getPlugins() {
  const plugins: PluginOption[] = [
    react(),
    tailwindcss(),
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
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        runtimeCaching: [
          {
            // 风险工作台等接口用 updated_at 做乐观锁并发控制：
            // 一旦返回 Service Worker 缓存（NetworkFirst 超时回退/离线）的旧响应，
            // 页面就会拿着过期版本提交并被后端 409 拒绝，且刷新也无法恢复，故 API 一律不缓存。
            urlPattern: /^\/api\/v1\//,
            handler: "NetworkOnly",
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
      "/signs": { target: API_TARGET, changeOrigin: true },
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
