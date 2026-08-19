# Codex Custom Subagents task handoff v1

Task: task_05_fix

## 修复任务：任务 5 质量审查建议（signs_source 回填 + 测试加固）

### 背景

任务 5（快照端点透传 signs）已通过规格审查与质量审查（✅ 通过，附 7 项次要/观察建议，其中 1 项为功能性缺口）。实现提交 `8d6fe18`。

### 修复 1（功能缺口）：build_card_data 回填 signs_source

`backend/app/services/risk_notice_card_service.py` 的 `build_card_data`：构造 CardData 时从快照 content 回填 `signs_source`（如 `snapshot_content(snapshot).get("signs_source") or "rule"`），否则前端来源 Tag（任务 8 依赖）恒拿不到 manual/ai。有快照 signs 时 source 取快照值；无快照/无 signs 时保持 "rule" 或 None（前端按缺省处理）。

### 修复 2（次要）：测试消除 RuntimeWarning

`backend/tests/test_risk_notice_card_service.py` 两个新测试（service:301/336）加 `db.add = MagicMock()`，与 `_risk_card_db` 模式对齐，消除 coroutine never awaited 警告。

### 修复 3（次要）：CardData.signs 冗余清理

`backend/app/schemas/risk_notice_card.py` 删除 CardData 中与父类重复的 `signs: list[SignItem] = []` 重定义（保持继承即可）；确认无测试/调用受影响。

### 修复 4（次要）：非法 category 边界明确

`normalize_signs` docstring 明确：写端点（PUT /snapshot）经 pydantic SignItem 严格校验（非法 category/缺字段 → 422）；`normalize_signs` 的静默丢弃主要用于读旧快照脏数据路径。补一条 API 层非法 category → 422 的用例。

### 修复 5（次要）：补测试覆盖

补：a) 已存在快照 + signs 分支（版本递增且 content 替换为规范化结果）；b) API 层非法 signs_source 回退 rule 端到端；c) 有 signs 缺 signs_source 默认 rule。

### 范围与限制

* 只改 `backend/app/schemas/risk_notice_card.py`、`backend/app/services/risk_notice_card_service.py`、`backend/tests/test_risk_notice_card_api.py`、`backend/tests/test_risk_notice_card_service.py`。
* 不修改前端/路由。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -v` 全部 PASS（无 RuntimeWarning）。
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend && python -m pytest tests/ -q` 无回归（435+ passed）。
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review show --check HEAD` 干净。
* 提交新 commit（不要 amend 8d6fe18），消息：`fix(risk-notice-card): populate signs source and harden snapshot tests`，只含上述文件。

### 汇报

* 状态：DONE | BLOCKED | NEEDS_CONTEXT
* 修改的文件与行
* 测试结果
* 新提交 SHA
