# Codex Custom Subagents task handoff v1

Task: cockpit_06_spec_review

你正在审查「企业驾驶舱」任务 6 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 6 规格）

1. 新建 `frontend/src/components/enterprise/cockpit/ModuleNav.tsx`：10 模块内联 SVG 图标导航（基本信息 ARCHIVE/组织架构 ORG/周边环境 GEO/危险化学品 CHEM/风险管控 RISK(hot)/隐患治理 HAZARD(hot)/应急资源 RESCUE/风险评估 REPORT/资源调查 SURVEY/预案管理 PLAN），路径映射到 /enterprises/:id/modules/info、/org、/modules/surrounding、/modules/chemicals、/risk-management、/hazard、/modules/resources、/modules/assessment、/modules/investigation、/plans；role=button + tabIndex + Enter 键；stroke 引用 url(#cp-grad)。
2. 新建 `frontend/src/pages/Enterprise/EnterpriseCockpitPage.tsx`：useQuery 并行取 getEnterprise + getCockpitSummary；加载态 Spin；失败态重试；组装 Background/Header/Ticker/三栏（Donut|Radar|Todo+Completion+Activity）/ModuleNav；buildTickerItems(summary, resources, plans) 用 resources_count/plans_count ?? 0；页面内隐藏 svg defs 提供 cp-grad。
3. 修改 `CockpitTicker.tsx`：第二份重复内容包 `<span aria-hidden="true">`。
4. Commit：`feat(cockpit): module nav and cockpit page assembly`；只改这 3 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit 8866d74（父 099966f）；3 文件 +175/-1；tsc/eslint exit 0。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；`git show 8866d74 --stat` / 直接读文件核验；
- 按上面「要求的内容」逐项核验：10 模块路径映射（与任务 8 将注册的路由一致）、hot 徽标、键盘可达、buildTickerItems 兜底、加载/错误/成功三态、cp-grad defs、Ticker aria-hidden；
- 检查是否有多余内容或范围外改动；
- 实际运行（工作目录 worktree\frontend）：
  - `npx tsc -b`
  - `npx eslint src/pages/Enterprise/EnterpriseCockpitPage.tsx src/components/enterprise/cockpit/ModuleNav.tsx src/components/enterprise/cockpit/CockpitTicker.tsx`
- 检查提交只含 3 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（检查输出、git show 核验、发现的任何问题）
