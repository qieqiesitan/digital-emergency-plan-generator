import React from "react";
import ReactDOM from "react-dom/client";
import { isMobile } from "@/mobile/utils/platform";

// URL 路径检测：/m 或 /m/xxx 一律视为移动端
function isMobilePath(): boolean {
  const p = window.location.pathname;
  return p === "/m" || p.startsWith("/m/");
}

async function bootstrap() {
  if (isMobilePath() || isMobile()) {
    const { default: MobileApp } = await import("@/mobile/MobileApp");
    ReactDOM.createRoot(document.getElementById("root")!).render(
      <React.StrictMode>
        <MobileApp />
      </React.StrictMode>
    );
  } else {
    const { default: App } = await import("@/App");
    ReactDOM.createRoot(document.getElementById("root")!).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  }
}

bootstrap();
