import { useEffect } from "react";

/** 按页面设置浏览器标签标题（空标题时回退系统名）。 */
export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} - 数字化预案系统` : "数字化预案系统";
  }, [title]);
}
