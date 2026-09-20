import type { FieldSource } from "@/types/workTicket";

/**
 * 字段来源的中文名。
 *
 * 单独成文件：组件的 Fast Refresh 只支持"纯组件导出"，
 * 常量与纯函数混在组件文件里会触发 react-refresh/only-export-components。
 */
export const SOURCE_LABEL: Record<FieldSource, string> = {
  manual: "手工填写",
  history: "上次同类票",
  member: "成员台账",
  risk_object: "作业对象",
  template_link: "向导联动",
  system_default: "系统默认",
  batch: "作业包",
  ai: "AI 生成",
};
