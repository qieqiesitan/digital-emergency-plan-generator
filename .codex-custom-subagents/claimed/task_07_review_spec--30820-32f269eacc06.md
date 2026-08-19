# Codex Custom Subagents task handoff v1

Task: task_07_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 7 的实现做**只读规格合规审查**，对照 A 规格 §6/§10 与任务 7 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`50010f1`（父 `9910900`）
- 文件：
  - `frontend/src/types/riskManagement.ts`、`frontend/src/types/riskMappingWorkbench.ts`
  - `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
  - `frontend/src/pages/Enterprise/RiskOverviewPage.tsx`
  - `frontend/src/components/enterprise/riskMapping/RiskDistributionStage.tsx`
  - `frontend/src/components/enterprise/RiskOverviewMatrix.tsx`
  - `frontend/src/components/enterprise/riskMapping/WorkbenchCanvas.tsx`、`WorkbenchLegend.tsx`（实现者超范围但必要）
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §6（四色图双模式）、§10（工作台/总览切换）

## 审查要点

1. 工作台：Segmented「现有/固有」切换、`colorMode` 默认 current、区域填充色回退（inherent ?? current）、图例文案随模式、切换不破坏已绘制内容；
2. 总览：第二组 Segmented、切换清高亮、`RiskDistributionStage`/`RiskOverviewMatrix` 的 mode 入参取对应等级与颜色（inherent 回退 current）；
3. 类型：HierarchyZone/WorkbenchZone 双字段与后端契约一致；
4. 超范围评估：WorkbenchCanvas/WorkbenchLegend 改动是否必要、RiskDistributionStage 的 eslint 修复是否行为等价（stash 对比结论可信否）；
5. 门禁：tsc/eslint/vitest 全过；
6. 无其他越界改动。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_07_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务7规格审查完成"
```

## 规则

- 全程只读（可运行只读 vitest/tsc/eslint、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
