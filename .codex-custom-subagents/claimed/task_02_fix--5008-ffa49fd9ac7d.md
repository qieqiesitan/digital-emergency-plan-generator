# Codex Custom Subagents task handoff v1

Task: task_02_fix

## 修复任务：任务 2 质量审查建议（测试强度 + DRY）

### 背景

任务 2（normalize_signs）已通过规格审查与质量审查（✅ 通过，附 1 项重要 + 3 项次要建议）。实现提交 `5157f5e`。

### 修复 1（重要）：去重断言补真实重复项

`backend/tests/test_risk_notice_card_service.py` 的 `test_normalize_signs_filters_and_limits`：输入补一条真实重复项（如第二个 `warning-fire`），使 `len(out) == len({svg...})` 成为有效判别。

### 修复 2（次要）：max_total 截断路径测试

测试补：`normalize_signs(signs, max_total=4)` 断言只取前 4 项（真实覆盖截断路径，默认 2×4=8 下 `[:8]` 恒真不可达）。

### 修复 3（次要）：docstring 说明 category 约束

`normalize_signs` docstring 注明「调用方须保证每个标志的 category 合法（缺失/错配会被静默丢弃）」。

### 修复 4（次要）：提取共享排序限量函数（DRY）

`match_signs` 与 `normalize_signs` 的「按 SIGN_CATEGORY_ORDER 排序 + 每类限量」循环重复。提取共享 helper（如 `_order_by_category(items, max_per_category)`）供两者复用；`match_signs` 传 2、`normalize_signs` 传参数。注意保持两者行为不变（match_signs 现有测试全绿）。

### 范围与限制

* 只改 `backend/app/services/risk_notice_card_service.py`、`backend/tests/test_risk_notice_card_service.py`。
* 不修改其他文件。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend && python -m pytest tests/test_risk_notice_card_service.py -v` 全部 PASS。
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend && python -m pytest tests/ -q` 无回归（420+ passed）。
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review show --check HEAD` 干净。
* 提交新 commit（不要 amend 5157f5e），消息：`fix(risk-notice-card): strengthen normalize tests and dedupe ordering helper`，只含上述 2 个文件。

### 汇报

* 状态：DONE | BLOCKED | NEEDS_CONTEXT
* 修改的文件与行
* 测试结果
* 新提交 SHA
