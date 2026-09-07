/**
 * 桌面端页面元数据（标题 + 菜单高亮 key）单一事实源。
 * MainLayout 用它设置 document.title 与 selectedKeys，
 * 避免「企业/预案动态路径永远不高亮」的字符串精确匹配问题。
 */

interface PageRule {
  test: (pathname: string) => boolean;
  title: string;
  menuKey?: string;
}

export interface PageMeta {
  title: string;
  menuKey?: string;
}

const EXACT_SETTINGS: Array<[string, string]> = [
  ["/settings/profile", "个人资料"],
  ["/settings/ai-config", "AI 配置"],
  ["/settings/third-party-config", "第三方接口配置"],
  ["/settings/users", "用户管理"],
  ["/settings/roles", "角色管理"],
  ["/settings/system", "系统配置"],
  ["/settings/prompts", "提示词管理"],
  ["/settings/regulations", "法规库管理"],
  ["/settings/data-dicts", "数据字典管理"],
  ["/settings/chemical-library", "化学品库管理"],
];

// 顺序即优先级：具体规则在前，兜底规则在后。
const RULES: PageRule[] = [
  { test: (p) => p === "/dashboard", title: "工作台", menuKey: "/dashboard" },
  { test: (p) => p === "/chat", title: "AI 助手" },
  { test: (p) => p === "/onboarding", title: "企业数据引导" },
  { test: (p) => p === "/enterprises", title: "企业管理", menuKey: "/enterprises" },
  { test: (p) => p === "/enterprises/new", title: "新建企业", menuKey: "/enterprises" },
  { test: (p) => p === "/plans", title: "预案列表", menuKey: "/plans" },
  { test: (p) => p === "/plans/new", title: "新建预案", menuKey: "/plans" },
  // 企业级预案（先于 /enterprises/:id 驾驶舱规则）
  {
    test: (p) => /^\/enterprises\/[^/]+\/plans/.test(p),
    title: "企业预案",
    menuKey: "/enterprises",
  },
  {
    test: (p) => /^\/enterprises\/[^/]+\/risk-assessment\/preview/.test(p),
    title: "风险评估报告",
    menuKey: "/enterprises",
  },
  {
    test: (p) => /^\/enterprises\/[^/]+\/resource-investigation\/preview/.test(p),
    title: "应急资源调查报告",
    menuKey: "/enterprises",
  },
  {
    test: (p) => /^\/enterprises\/[^/]+\/risk-management/.test(p),
    title: "风险分级管控",
    menuKey: "/enterprises",
  },
  {
    test: (p) => /^\/enterprises\/[^/]+\/hazard/.test(p),
    title: "隐患排查治理",
    menuKey: "/enterprises",
  },
  {
    test: (p) => /^\/enterprises\/[^/]+\/edit$/.test(p),
    title: "编辑企业",
    menuKey: "/enterprises",
  },
  {
    test: (p) => /^\/enterprises\/[^/]+$/.test(p),
    title: "企业驾驶舱",
    menuKey: "/enterprises",
  },
  { test: (p) => p.startsWith("/enterprises/"), title: "企业管理", menuKey: "/enterprises" },
  {
    test: (p) => /^\/plans\/[^/]+\/edit$/.test(p),
    title: "预案编辑器",
    menuKey: "/plans",
  },
  {
    test: (p) => /^\/plans\/[^/]+\/versions/.test(p),
    title: "预案版本",
    menuKey: "/plans",
  },
  {
    test: (p) => /^\/plans\/[^/]+\/preview/.test(p),
    title: "导出预览",
    menuKey: "/plans",
  },
  { test: (p) => p.startsWith("/plans/"), title: "预案", menuKey: "/plans" },
  ...EXACT_SETTINGS.map(([path, title]) => ({
    test: (p: string) => p === path,
    title,
    menuKey: path,
  })),
  { test: (p) => p.startsWith("/settings/"), title: "系统设置" },
];

export function getPageMeta(pathname: string): PageMeta {
  const matched = RULES.find((r) => r.test(pathname));
  if (!matched) return { title: "" };
  return { title: matched.title, menuKey: matched.menuKey };
}
