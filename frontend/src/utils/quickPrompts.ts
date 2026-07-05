export interface QuickPrompt {
  id: string;
  label: string;
  text: string;
}

const STORAGE_KEY = "plan_quick_prompts";

const DEFAULTS: QuickPrompt[] = [
  { id: "more_detail", label: "更详细", text: "请补充更多细节，增加具体的操作步骤和数据" },
  { id: "more_concise", label: "更简洁", text: "请精简表达，保留核心要点，删除冗余描述" },
  { id: "gbt_compliant", label: "按GB/T规范", text: "按GB/T 29639-2020规范格式调整，确保术语和结构合规" },
  { id: "add_steps", label: "补充操作步骤", text: "增加具体的操作步骤、责任人和时间节点" },
  { id: "add_data", label: "增加定量数据", text: "补充具体的数量、距离、时间等定量数据" },
  { id: "formal_tone", label: "公文语体", text: "使用正式公文语体，语言严谨、客观、简洁" },
];

export function getQuickPrompts(): QuickPrompt[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {}
  return [...DEFAULTS];
}

export function saveQuickPrompts(prompts: QuickPrompt[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prompts));
}

export function resetQuickPrompts(): QuickPrompt[] {
  localStorage.removeItem(STORAGE_KEY);
  return [...DEFAULTS];
}
