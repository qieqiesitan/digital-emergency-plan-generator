# Codex Custom Subagents task handoff v1

Task: task_05_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 5 的实现做**只读代码质量审查**（规格审查与两轮复审已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交范围：`a1446b7`、`9104d4f`、`6cd1ad4`、`26d49e8`、`6659077` → 当前 HEAD=`6659077`
- 文件：
  - 后端：`backend/app/schemas/risk_management.py`、`backend/app/routers/risk_management.py`、`backend/app/services/risk_method_engine.py`、`backend/tests/test_risk_conversion_api.py`、`backend/tests/test_risk_dual_level.py`
  - 前端：`frontend/src/types/riskManagement.ts`、`frontend/src/services/riskManagementService.ts`、`frontend/src/services/riskManagementService.test.ts`、`frontend/src/components/enterprise/RiskEventForm.tsx`、`frontend/src/components/enterprise/RiskHierarchyTree.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 可对照：项目既有路由/表单/树组件风格

## 审查要点

1. 后端：conversion-reference 端点组装与归属校验实现质量；显式 risk_level 覆盖逻辑；update_event 重算守卫可读性；COAL_LS 常量提取；schema 可选字段向后兼容；
2. 前端：表单复杂度（固有区块/管控层级/折算参考/adoptedRef/paramsUnchanged 多状态）是否可维护、命名与既有风格一致；提交层条件省略逻辑是否清晰；树 meta 扩展是否破坏既有消费者；
3. 测试：后端端点/覆盖/未改动回归用例质量；前端 service 测试有效性；缺失组件级测试的说明；
4. 已知遗留建议评估：DIRECT 固有等级显式清空被 `?? undefined` 吞掉（RiskManagementTab.tsx 约 302 行）——确认是否属实、给出修复建议；
5. 有无过度工程、重复代码、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_05_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务5代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
