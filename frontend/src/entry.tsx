import React from "react";
import ReactDOM from "react-dom/client";
import { isMobile } from "@/mobile/utils/platform";

function isMobilePath(): boolean {
  const p = window.location.pathname;
  return p === "/m" || p.startsWith("/m/");
}

(async () => {
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
})();
