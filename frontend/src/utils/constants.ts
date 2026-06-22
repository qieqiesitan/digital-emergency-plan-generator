export const PRESET_RISK_CATEGORIES = [
  "火灾", "爆炸", "触电", "中毒窒息", "机械伤害",
  "高处坠落", "物体打击", "车辆伤害", "淹溺", "坍塌",
  "锅炉爆炸", "容器爆炸",
] as const;

export const PRESET_EMERGENCY_GROUPS: Record<string, string> = {
  headquarters: "应急指挥部",
  rescue: "抢险救灾组",
  evacuation: "疏散引导组",
  medical: "医疗救护组",
  communication: "通讯联络组",
  logistics: "后勤保障组",
};

export const PRESET_INTERNAL_RESOURCE_CATEGORIES = [
  "消防设施", "急救物资", "防护装备", "通讯设备",
  "照明设备", "破拆工具", "侦检设备", "堵漏器材",
] as const;

export const PRESET_EXTERNAL_RESOURCE_CATEGORIES = [
  "消防队", "医院", "公安机关", "安监部门", "环保部门",
] as const;

export const PRESET_INDUSTRIES = [
  "危险化学品", "工贸", "建筑施工", "矿山",
  "交通运输", "商贸服务",
] as const;

export const PLAN_TYPE_LABELS: Record<string, string> = {
  comprehensive: "综合应急预案",
  special: "专项应急预案",
  onsite: "现场处置方案",
};

export const PLAN_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  generating: "生成中",
  completed: "已完成",
};

// ⚠️ 以下常量已迁移到中台字典管理，仅保留 fallback
// 前端组件应优先使用 useDict() hook 从 /api/v1/system/dicts/{type} 获取
