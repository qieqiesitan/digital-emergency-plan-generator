# Codex Custom Subagents task handoff v1

Task: task_07_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 7 的实现做**只读代码质量审查**（规格审查已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`50010f1`（父 `9910900`）
- 文件：
  - `frontend/src/types/riskManagement.ts`、`frontend/src/types/riskMappingWorkbench.ts`
  - `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
  - `frontend/src/pages/Enterprise/RiskOverviewPage.tsx`
  - `frontend/src/components/enterprise/riskMapping/RiskDistributionStage.tsx`、`WorkbenchCanvas.tsx`、`WorkbenchLegend.tsx`
  - `frontend/src/components/enterprise/RiskOverviewMatrix.tsx`
- 可对照：项目既有页面/组件风格

## 审查要点

1. colorMode 状态管理（useState + localStorage）是否清晰、命名一致；切换逻辑是否最小；
2. `RiskDistributionStage` 的 eslint 修复（effect→useMemo）行为等价性、可读性；
3. 组件入参（mode）类型定义与回退逻辑是否一致（inherent ?? current）；`RiskOverviewMatrix` 事件标签回退；
4. 有无重复代码、过度工程；既有 eslint 债务（WorkbenchCanvas 10 error）是否确为提交前既有（git show 父版本对比）；
5. 规格审查建议评估：层级树事件标签/统计不随模式联动（是否值得本轮修复）；组件级测试缺失（jsdom 环境限制说明）。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_07_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务7代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 vitest/tsc/eslint、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
