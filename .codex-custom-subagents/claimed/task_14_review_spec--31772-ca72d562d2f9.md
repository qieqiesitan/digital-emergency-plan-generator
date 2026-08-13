# Codex Custom Subagents task handoff v1

Task: task_14_review_spec

## 规格合规审查：任务 14（风险对象表单责任信息字段）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 14 规格 + 设计规格 §6.1/§10.4）

**文件：**

* 修改：`frontend/src/components/enterprise/RiskObjectForm.tsx`（责任信息分组三字段 + 兜底提示）
* 修改：`frontend/src/types/riskManagement.ts`（表单 values 与 RiskObject 类型加 3 字段）
* 修改：`backend/app/schemas/risk_management.py`（RiskObjectCreate/Update/Response 加 3 可选字段）
* 测试：schema 字段断言（可选）

**要求**：表单三字段（责任单位/责任人/联系电话）+ 兜底说明文案与规格 §10.4 一致；后端 schema 三字段与模型对应；创建/更新透传正常（exclude_unset）。

**实现者计划外偏离**（请核实合理性）：1) RiskManagementTab.tsx 的 object 提交处理器重构为透传 3 字段（否则前端丢弃）；2) WorkbenchCanvas.tsx 与 riskMappingWorkbenchStore.test.ts 字面量补 3 个 null 字段（类型加字段后 tsc 要求）。

**范围限制**：commit 消息 `feat(risk-notice-card): add responsibility fields to risk object form`。

### 实现者声称构建了什么

* commit `66b69ca`（7 文件 77+/4-），tsc/vitest/eslint 0、pytest 408 passed
* 表单分组 + 前端类型 + 后端 schema + 提交透传 + 字面量补齐

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 66b69ca` 逐行核对。
2. 核对：表单三字段位置/文案/类型；前端类型字段（与后端契约一致，public_token 未恢复）；后端 schema 三字段与模型对应；创建/更新透传；两处计划外偏离合理性；提交范围与消息。
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）+ `cd backend && python -m pytest tests/ -q`（408+ passed）。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-13 已过审；任务 15 回归。
