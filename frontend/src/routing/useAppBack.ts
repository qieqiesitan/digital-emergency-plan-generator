import { useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * 返回按钮统一规则：
 * 站内有应用内历史（react-router location.key 非 default）→ 浏览器后退；
 * 深层直达/刷新后 → 跳页面声明的逻辑上级，避免跳到站外或登录页。
 */
export function resolveBackTarget(inAppHistory: boolean, fallback: string): string | number {
  return inAppHistory ? -1 : fallback;
}

export function useAppBack(fallback: string): () => void {
  const navigate = useNavigate();
  const location = useLocation();
  return useCallback(() => {
    const target = resolveBackTarget(location.key !== "default", fallback);
    if (typeof target === "number") {
      navigate(target);
    } else {
      navigate(target, { replace: true });
    }
  }, [fallback, location.key, navigate]);
}
