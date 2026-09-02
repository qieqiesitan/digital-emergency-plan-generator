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
};
