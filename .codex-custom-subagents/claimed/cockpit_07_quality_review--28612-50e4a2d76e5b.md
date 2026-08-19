# Codex Custom Subagents task handoff v1

Task: cockpit_07_quality_review

你正在对「企业驾驶舱」任务 7 的实现做代码质量审查（只读，不修改代码）。规格合规性审查已通过，本次只看质量。

## 审查范围
- WHAT_WAS_IMPLEMENTED：ModuleSideNav/ModulePageShell/enterpriseNavConfig/EnterpriseModulePage（新）+ RiskManagementTab/HazardInspectionTab（embedded 改造）（commit 35ea909）。
- BASE_SHA：8866d74
- HEAD_SHA：35ea909
- DESCRIPTION：模块页外壳 + 左竖导航 + embedded 改造

## 工作目录
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit（分支 codex/enterprise-cockpit；前端命令在 frontend 子目录）

## 审查要点
- ModuleSideNav：高亮逻辑边界（pathname 精确匹配 vs 子路径场景——如 /risk-management/overview 时「风险树编辑」不应高亮、楼层项 matchSearch 是否可能误匹配）、可访问性（Enter 键、焦点样式缺失是否可接受）；
- ModulePageShell：groups 作为函数注入是否合理、与 SideNav 的耦合；
- enterpriseNavConfig：路径与任务 8 路由表一致性、重复路径风险；
- EnterpriseModulePage：MODULE_MAP 结构是否清晰、render 闭包是否可能造成不必要的重渲染、模块不存在时的体验；
- 两个 Tab 的 embedded 改造：条件渲染是否引入了行为回归（如按钮位置微调）、useEffect 依赖数组是否稳定、eslint-disable 注释是否精确；
- 文件规模与职责。

## 命令参考
- diff：`git diff 8866d74 35ea909`
- 检查：`npx tsc -b`、`npx eslint src/components/enterprise/cockpit/ModulePageShell.tsx src/components/enterprise/cockpit/ModuleSideNav.tsx src/pages/Enterprise/enterpriseNavConfig.ts src/pages/Enterprise/EnterpriseModulePage.tsx src/pages/Enterprise/RiskManagementTab.tsx src/pages/Hazard/HazardInspectionTab.tsx`（工作目录 worktree\frontend）

## 输出格式
- 优点
- 问题（分级：关键 / 重要 / 次要，附 file:line）
- 评估结论：通过 / 需修复

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 审查结论与依据
