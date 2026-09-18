import type { SideNavGroup } from "@/components/enterprise/cockpit/ModuleSideNav";

export function riskNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "数据编辑",
      items: [
        { key: "tree", label: "风险树编辑", to: `/enterprises/${id}/risk-management`, inactiveWhenSearch: "floor=1" },
        { key: "methods", label: "评估方法", to: `/enterprises/${id}/risk-management/methods` },
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

/**
 * 重大危险源模块侧导航。
 *
 * 三页对应一条线：建单元 → 录品种并算 R 值 → 建档备案。
 * 与作业票模块不同，这里不做"单入口 + 类型筛选"，因为重大危险源没有类型分叉，
 * 只有流程阶段，所以按阶段分页更直观。
 */
export function majorHazardNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "台账",
      items: [
        { key: "list", label: "单元台账", to: `/enterprises/${id}/major-hazard` },
      ],
    },
    {
      label: "分析与备案",
      items: [
        {
          key: "compute",
          label: "计算与分级",
          to: `/enterprises/${id}/major-hazard/compute`,
        },
        {
          key: "record",
          label: "档案与备案",
          to: `/enterprises/${id}/major-hazard/record`,
        },
      ],
    },
  ];
}

/**
 * 作业票模块侧导航。
 *
 * 视觉走查第 1 条：侧边栏**只有一个入口**，8 类票在页面内用类型筛选切换，
 * 不在这里开 8 个菜单——菜单一多，用户找不到东西，将来加类型还要改导航。
 * 故这里只有两项：作业票（含开票向导）与审批工作台。
 */
export function workTicketNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "特殊作业",
      items: [
        { key: "tickets", label: "作业票", to: `/enterprises/${id}/work-ticket` },
      ],
    },
    {
      label: "基础设置",
      items: [
        {
          key: "approval",
          label: "审批工作台",
          to: `/enterprises/${id}/work-ticket/approval`,
        },
      ],
    },
  ];
}
