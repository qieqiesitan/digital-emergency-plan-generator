import DOMPurify from "dompurify";

/**
 * 统一 HTML 消毒入口（W2 存储型 XSS 修复）。
 *
 * 所有 `dangerouslySetInnerHTML` 的内容——预案章节、报告正文、AI 流式输出、
 * 后端渲染的预览 HTML——都可能包含用户输入或模型输出，必须先过这里。
 * Chat 页此前已单独使用 DOMPurify，此处收敛为全站共用实现，避免各处写法漂移。
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html || "");
}

/**
 * Mermaid 渲染出的 SVG：保留 foreignObject（图表标签需要），
 * 仍会过滤脚本、事件属性与 javascript: 链接。
 */
export function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg || "", {
    ADD_TAGS: ["foreignObject"],
    ADD_ATTR: ["dominant-baseline", "text-anchor"],
  });
}
