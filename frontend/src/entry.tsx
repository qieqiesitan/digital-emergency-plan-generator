import React from "react";
import ReactDOM from "react-dom/client";
import { isMobile } from "@/mobile/utils/platform";

function isMobilePath(): boolean {
  const p = window.location.pathname;
  return p === "/m" || p.startsWith("/m/");
}

let root: ReactDOM.Root | null = null;

// ---- qiankun 生命周期 ----

/** 子应用首次加载时调用，通常为空 */
export async function bootstrap(): Promise<void> {
  // no-op
}

/** 子应用挂载 */
export async function mount(props: Record<string, unknown>): Promise<void> {
  // 将中台注入的 props 写入全局，供 platform.ts 读取
  (window as any).__YWT_PROPS__ = props;

  const { container } = props as { container?: HTMLElement };
  const rootEl = container
    ? container.querySelector("#root") as HTMLElement | null
    : document.getElementById("root");

  if (!rootEl) {
    console.error("[emergency-plan] mount: #root not found");
    return;
  }

  // qiankun 模式下始终渲染桌面端 App（移动端由中台主应用处理）
  const { default: App } = await import("@/App");
  root = ReactDOM.createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

/** 子应用卸载 */
export async function unmount(props: Record<string, unknown>): Promise<void> {
  if (root) {
    root.unmount();
    root = null;
  }
  delete (window as any).__YWT_PROPS__;
}

// ---- 独立模式：非 qiankun 环境直接渲染 ----
if (!(window as any).__POWERED_BY_QIANKUN__) {
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
}
