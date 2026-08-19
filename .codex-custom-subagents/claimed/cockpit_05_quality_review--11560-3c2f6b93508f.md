# Codex Custom Subagents task handoff v1

Task: cockpit_05_quality_review

你正在对「企业驾驶舱」任务 5 的实现做代码质量审查（只读，不修改代码）。规格合规性审查已通过，本次只看质量。

## 审查范围
- WHAT_WAS_IMPLEMENTED：`frontend/src/types/cockpit.ts`（+常量）、5 个面板组件（RiskDonutPanel/RiskRadarPanel/CockpitTodoPanel/CockpitCompletionPanel/CockpitActivityPanel）（commit ba95be2）。
- BASE_SHA：eea489d
- HEAD_SHA：ba95be2
- DESCRIPTION：驾驶舱数据面板组件

## 工作目录
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit（分支 codex/enterprise-cockpit；前端命令在 frontend 子目录）

## 审查要点
- 组件职责单一、props 接口清晰；有无重复逻辑可抽取（如面板 corner 四连 <i> 重复 5 次——评估是否值得抽小组件，结合项目「页面自包含」惯例判断，不强求重构）；
- 渲染分支是否完整（有数据/空数据/异常值如 score null）；key 选择是否稳定（r.name / t.title / m.key 是否可能重复导致渲染问题）；
- 类型使用是否严谨（无 any；RISK_LEVEL_COLORS 用 Record<string,string> 是否合适）；
- 可访问性/性能（动画元素数量、aria）；
- 文件规模是否合理。

## 命令参考
- diff：`git diff eea489d ba95be2`
- 检查：`npx tsc -b`、`npx eslint src/components/enterprise/cockpit src/types/cockpit.ts`（工作目录 worktree\frontend）

## 输出格式
- 优点
- 问题（分级：关键 / 重要 / 次要，附 file:line）
- 评估结论：通过 / 需修复

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 审查结论与依据
