# Codex Custom Subagents task handoff v1

Task: task_b3_review_spec2

## 任务：规格复审——task_b3_fix2（unit 级风险事件缺口修复）

你是一个规格合规审查子智能体。目的：验证前次审查发现的功能性缺口（unit 级事件漏计）是否已修复且无回归。不要信任实现者报告，独立阅读代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `ed1accb`：

git show ed1accb --stat 与 git show ed1accb，并阅读 onboarding_service.py 全文。

### 前次审查发现的问题

compute_completion 的 risk_chemical 事件查询仅用 `INNER JOIN RiskObject ON RiskEvent.object_id == RiskObject.id`，而 `/units/{unit_id}/events` 创建的事件只写 unit_id、object_id 为空，导致只有 unit 级事件的企业被误判为风险模块未完成。

### 实现者声称修复了什么

- 事件查询拆为 object 级 + unit 级（RiskEvent.unit_id → RiskUnit → RiskObject.object_id），均按 enterprise_id 过滤
- `list(dict.fromkeys([...]))` 去重
- 追加 unit 级事件测试（按 SQL 文本区分 object/unit 查询）
- 提交 ed1accb，全量 259 passed 无新增失败

### 你的工作

阅读实际代码验证：unit 级事件现在能计入？查询归属逻辑正确（enterprise_id 过滤）？去重合理？新增测试是否真实覆盖 unit 路径？规格 6.6「风险点 ≥1 即完成」语义满足？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
