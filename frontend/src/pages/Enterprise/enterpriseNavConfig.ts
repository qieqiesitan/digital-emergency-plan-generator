import type { SideNavGroup } from "@/components/enterprise/cockpit/ModuleSideNav";

export function riskNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "数据编辑",
      items: [
        { key: "tree", label: "风险树编辑", to: `/enterprises/${id}/risk-management` },
        { key: "floors", label: "楼层平面图", to: `/enterprises/${id}/risk-management?floor=1`, matchSearch: "floor=1" },
        { key: "methods", label: "评估方法", to: `/enterprises/${id}/risk-management/methods` },
        { key: "dicts", label: "风险与隐患配置", to: `/enterprises/${id}/risk-management/data-dicts` },
      ],
    },
    {
      label: "成果输出",
      items: [
        { key: "overview", label: "可视化总览", to: `/enterprises/${id}/risk-management/overview` },
        { key: "workbench", label: "四色图工作台", to: `/enterprises/${id}/risk-management/workbench` },
        { key: "list", label: "管控清单", to: `/enterprises/${id}/risk-management/control-list` },
        { key: "cards", label: "风险告知卡", to: `/enterprises/${id}/risk-management/notice-cards` },
        { key: "publicity", label: "风险公示", to: `/enterprises/${id}/risk-management/publicity` },
      ],
    },
  ];
}

export function hazardNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "排查管理",
      items: [
        { key: "ledger", label: "隐患台账", to: `/enterprises/${id}/hazard` },
        { key: "plans", label: "排查计划", to: `/enterprises/${id}/hazard/plans` },
        { key: "tasks", label: "排查任务", to: `/enterprises/${id}/hazard/tasks` },
        { key: "templates", label: "排查模板", to: `/enterprises/${id}/hazard/templates` },
      ],
    },
    {
      label: "分析公示",
      items: [
        { key: "dashboard", label: "隐患看板", to: `/enterprises/${id}/hazard/dashboard` },
        { key: "publicity", label: "隐患公示", to: `/enterprises/${id}/hazard/publicity` },
      ],
    },
  ];
}
