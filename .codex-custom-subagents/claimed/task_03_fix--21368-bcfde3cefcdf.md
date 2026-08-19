# Codex Custom Subagents task handoff v1

Task: task_03_fix

## 修复任务：任务 3 质量审查 4 项次要建议

### 背景

任务 3（review_signs AI 服务）已通过规格审查与质量审查（✅ 通过，附 4 项次要建议）。实现提交 `101c8ae`。

### 修复 1（次要）：非 dict JSON 兜底

`backend/app/services/risk_notice_card_ai.py` 的 review_signs：`json.loads` 成功后补 `if not isinstance(data, dict): raise HTTPException(502, "AI 返回格式异常，无法解析 JSON")`（LLM 输出数组/字符串时避免 500）。

### 修复 2（次要）：提示词组装键取值防御

current_signs/catalog 组装用 `s.get('name', '')` / `s.get('svg_name', '')` 替代 `s['name']` / `s['svg_name']`（缺键不 KeyError）。

### 修复 3（次要）：accident_type 兜底

events 组装中 `e.get('accident_type', '')` 加 `or ''`，与 trigger_conditions/consequences 的 `or ''` 风格一致。

### 修复 4（次要）：测试补提示词断言

`backend/tests/test_risk_notice_card_api.py` 的 review_signs 测试：fake_completion 捕获 messages 入参，补一条断言 prompt 含关键约束字样（如「只能从这里选」「每类」）。

### 范围与限制

* 只改 `backend/app/services/risk_notice_card_ai.py`、`backend/tests/test_risk_notice_card_api.py`。
* 不修改其他文件。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend && python -m pytest tests/test_risk_notice_card_api.py -v` 全部 PASS。
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend && python -m pytest tests/ -q` 无回归（424+ passed）。
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review show --check HEAD` 干净。
* 提交新 commit（不要 amend 101c8ae），消息：`fix(risk-notice-card): harden ai sign review parsing and prompt`，只含上述 2 个文件。

### 汇报

* 状态：DONE | BLOCKED | NEEDS_CONTEXT
* 修改的文件与行
* 测试结果
* 新提交 SHA
