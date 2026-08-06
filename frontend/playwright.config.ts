import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  retries: 1,
  // 自动拉起当前源码的 Vite dev server，保证默认路径可复现；
  // 若已有 5174 在跑则复用（CI 中总是新建）。
  webServer: {
    command: "npm run dev -- --port 5174 --strictPort",
    url: "http://localhost:5174",
    reuseExistingServer: false,
    timeout: 60000,
  },
  use: {
    // 默认走 webServer 自动启动的 5174；可用 E2E_BASE_URL 覆盖（如指向已部署环境）。
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5174",
    headless: true,
    viewport: { width: 1280, height: 800 },
    actionTimeout: 10000,
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
