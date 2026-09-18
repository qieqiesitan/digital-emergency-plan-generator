/**
 * 路径 → 菜单权限码 映射（侧边菜单与路由守卫共用，避免两处维护漂移）。
 * 未收录的路径（公开页、企业业务子页等）不受菜单权限守卫约束。
 */
export const MENU_MAP: Record<string, string> = {
  "/dashboard": "menu:dashboard",
  "/enterprises": "menu:enterprises",
  "/plans": "menu:plans",
  "/settings/users": "menu:users",
  "/settings/roles": "menu:roles",
  "/settings/system": "menu:system_config",
  "/settings/prompts": "menu:prompts",
  "/settings/profile": "menu:profile",
  "/settings/ai-config": "menu:ai_config",
  "/settings/third-party-config": "menu:third_party_config",
  "/settings/regulations": "menu:regulations",
  "/settings/data-dicts": "menu:data_dicts",
  "/settings/chemical-library": "menu:chemical_library",
  "/settings/data-hub": "menu:data_hub",
  "/settings/data-hub/import": "menu:data_hub",
  // W0 安全修复：平台总览与 AI 能力管理收口为管理员（与后端 require_admin 对齐）
  "/platform/overview": "menu:system_config",
  "/settings/ai-capabilities": "menu:system_config",
};
