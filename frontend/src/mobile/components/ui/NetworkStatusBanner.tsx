import { WifiOff } from "lucide-react";
import { useNetworkStatus } from "@/mobile/hooks/useNetworkStatus";

export default function NetworkStatusBanner() {
  const isOnline = useNetworkStatus();

  if (isOnline) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] bg-warning/95 text-white flex items-center justify-center gap-xs h-8 text-caption font-medium"
         style={{ paddingTop: "var(--safe-top)" }}>
      <WifiOff size={14} />
      <span>离线模式 · 编辑内容将在恢复网络后同步</span>
    </div>
  );
}
