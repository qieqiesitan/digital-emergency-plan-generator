# Codex Custom Subagents task handoff v1

Task: cockpit_07_spec_review

你正在审查「企业驾驶舱」任务 7 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 7 规格）

1. 新建 `ModuleSideNav.tsx`：SideNavItem/SideNavGroup 接口；pathname 精确匹配高亮，matchSearch 时用 location.search.includes 匹配；role=button + tabIndex + Enter。
2. 新建 `ModulePageShell.tsx`：props {title, en?, groups?: (id: string) => SideNavGroup[]}；顶栏「← 返回企业驾驶舱」（antd Button type=link）+ 标题 + EN；内容区 = 可选 ModuleSideNav + Outlet。
3. 新建 `enterpriseNavConfig.ts`：riskNavGroups（数据编辑：风险树编辑/楼层平面图 ?floor=1/评估方法/风险与隐患配置；成果输出：可视化总览/四色图工作台/管控清单/风险告知卡/风险公示）与 hazardNavGroups（排查管理：隐患台账/排查计划/排查任务/排查模板；分析公示：隐患看板/隐患公示）。
4. 新建 `EnterpriseModulePage.tsx`：MODULE_MAP（info/surrounding/chemicals/resources/assessment/investigation 6 模块），useQuery 取 enterprise，PageHeader 返回驾驶舱，模块不存在显示「模块不存在」。
5. 修改 `RiskManagementTab.tsx`：Props 加 embedded；useSearchParams + useEffect（?floor=1 时打开楼层抽屉）；8 个导航按钮包进 !embedded，保留添加分区/智能导引/楼层管理。
6. 修改 `HazardInspectionTab.tsx`：Props 加 embedded；5 个导航按钮包进 !embedded，保留新增记录/导出（文案按文件实际）。
7. Commit：`feat(cockpit): module page shell, side nav and embedded tab components`；只改这 6 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit 35ea909（父 8866d74）；6 文件 259+/33-；tsc/eslint exit 0；因 react-hooks/set-state-in-effect 新规则对 useEffect 内 setState 报错（基线文件同样报错），加了一条 eslint-disable-next-line 注释。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；`git show 35ea909 --stat` / 直接读文件核验；
- 逐项核验上面 7 点；特别确认：embedded 条件渲染确实包住了全部导航按钮且保留了主操作按钮；useEffect 只在 floor=1 时开抽屉；ModuleSideNav 高亮逻辑（pathname === to 与 matchSearch）；EnterpriseModulePage 各 render 的 props 与现有组件签名一致（对照 src/components/enterprise/* 与 src/pages/Enterprise/*Tab.tsx）；
- 检查 eslint-disable 注释是否合理、是否影响了行为；
- 实际运行（工作目录 worktree\frontend）：
  - `npx tsc -b`
  - `npx eslint src/components/enterprise/cockpit/ModulePageShell.tsx src/components/enterprise/cockpit/ModuleSideNav.tsx src/pages/Enterprise/enterpriseNavConfig.ts src/pages/Enterprise/EnterpriseModulePage.tsx src/pages/Enterprise/RiskManagementTab.tsx src/pages/Hazard/HazardInspectionTab.tsx`
- 检查提交只含 6 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（检查输出、git show 核验、发现的任何问题）
