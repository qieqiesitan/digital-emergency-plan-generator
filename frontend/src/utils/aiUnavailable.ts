/**
 * AI 未配置（审查报告 I7）统一识别与引导文案。
 *
 * 设计约束：不靠前端猜测 AI 是否可用——先按后端响应 detail 中的
 * "未配置 AI" 类文案识别；识别不出时由调用方回退到通用错误提示
 * （不得再显示 "（无回复）" 这类误导性兜底）。
 */

/** 设置 → AI 配置 页面路由（菜单权限点 menu:ai_config） */
export const AI_CONFIG_ROUTE = "/settings/ai-config";

/** AI 未配置时的统一引导文案（Chat / 一键生成 / 悬浮球三入口共用） */
export const AI_NOT_CONFIGURED_HINT =
  "系统尚未配置 AI 模型，请前往 设置→AI 配置 完成配置后使用";

/** 后端/上游 detail 中可判定为 "AI 未配置" 的常见表述 */
const AI_NOT_CONFIGURED_PATTERNS: RegExp[] = [
  /未配置\s*AI/i,
  /尚未配置\s*AI/i,
  /AI\s*未配置/i,
  /AI\s*尚未配置/i,
  /请(?:先|到).{0,12}配置\s*AI/i,
];

/** 判断错误消息是否表示 "AI 未配置" */
export function isAiNotConfiguredError(message: string | null | undefined): boolean {
  if (!message) return false;
  return AI_NOT_CONFIGURED_PATTERNS.some((re) => re.test(message));
}

export interface AiErrorDisplay {
  /** 是否命中 "AI 未配置"，命中时调用方应展示统一引导（含跳转配置页按钮） */
  notConfigured: boolean;
  /** 实际展示给用户的文案 */
  text: string;
}

/** 把原始错误 message 归一化为可展示文案：未配置 → 统一引导；其余 → 原文或 fallback */
export function aiErrorDisplay(
  message: string | null | undefined,
  fallback: string,
): AiErrorDisplay {
  const raw = (message || "").trim();
  if (isAiNotConfiguredError(raw)) {
    return { notConfigured: true, text: AI_NOT_CONFIGURED_HINT };
  }
  return { notConfigured: false, text: raw || fallback };
}
