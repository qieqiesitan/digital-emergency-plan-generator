# Codex Custom Subagents task handoff v1

Task: cockpit_06_quality_review

你正在对「企业驾驶舱」任务 6 的实现做代码质量审查（只读，不修改代码）。规格合规性审查已通过，本次只看质量。

## 审查范围
- WHAT_WAS_IMPLEMENTED：`ModuleNav.tsx`、`EnterpriseCockpitPage.tsx`、`CockpitTicker.tsx`（aria-hidden 补丁）（commit 8866d74）。
- BASE_SHA：099966f
- HEAD_SHA：8866d74
- DESCRIPTION：模块导航 + 驾驶舱主页组装

## 工作目录
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit（分支 codex/enterprise-cockpit；前端命令在 frontend 子目录）

## 审查要点
- ModuleNav：SVG 图标路径质量（是否扭曲/越界）、key 稳定性、可访问性（role/tabIndex/键盘处理）、配置数组与 JSX 分离是否合理；
- EnterpriseCockpitPage：数据流（两个 query 的加载/错误处理是否一致、refetch 是否合理）、组件职责（buildTickerItems 是否该留在页面内或抽离——结合规模判断）、错误态/加载态 UX；
- CockpitTicker aria-hidden 补丁是否破坏无缝滚动；
- 有无重复/冗余（例如 cp-grad defs 是否可能重复定义）；
- 文件规模是否合理。

## 命令参考
- diff：`git diff 099966f 8866d74`
- 检查：`npx tsc -b`、`npx eslint src/pages/Enterprise/EnterpriseCockpitPage.tsx src/components/enterprise/cockpit/ModuleNav.tsx src/components/enterprise/cockpit/CockpitTicker.tsx`（工作目录 worktree\frontend）

## 输出格式
- 优点
- 问题（分级：关键 / 重要 / 次要，附 file:line）
- 评估结论：通过 / 需修复

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 审查结论与依据
