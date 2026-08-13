# Codex Custom Subagents task handoff v1

Task: task_05_fix

## 修复任务：任务 5 质量审查 1 项重要 + 5 项次要建议

### 背景

任务 5（schemas + 组装服务）已通过规格审查与质量审查（✅ 通过，附 1 项重要 + 6 项次要建议）。实现提交 `3b4709a`。

### 修复 1（重要）：load_events_and_measures 按事件 id 去重

`backend/app/services/risk_notice_card_service.py` 的 `load_events_and_measures`：RiskEvent 同时有 object_id 与 unit_id 双外键，同一事件可能同时出现在 obj.events 和 unit.events，导致重复加入。请按事件 id 去重后再收集措施（例如用 dict 保序去重）。注意内存构造对象 id 可能为 None，用 id 或对象身份混合去重。

### 修复 2（次要）：is_stale 时区处理健壮化 + 补单测

`is_stale` 改为：

```python
def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
```

比较用 `_as_utc(snapshot.updated_at) < _as_utc(source_updated_at)`。在测试文件补一条 `test_is_stale_timezone`：naive 与 +08:00 aware 时间都能正确比较。

### 修复 3（次要）：兜底应急文案移入常量模块

`backend/app/services/risk_notice_card_data.py` 新增：

```python
DEFAULT_EMERGENCY_TEMPLATE = ["立即停止作业，保护现场", "拨打 119/120 报警", "组织人员疏散，报告企业应急管理部门"]
```

`build_right_column` 引用 `DEFAULT_EMERGENCY_TEMPLATE` 替代硬编码。

### 修复 4（次要）：source="ai" 提取常量

`risk_notice_card_data.py` 新增 `SOURCE_AI = "ai"`；`save_snapshot` 中 `source="ai"` 与 `existing.source = "ai"` 改用 `SOURCE_AI`。

### 修复 5（次要）：selectinload 字符串路径改对象引用

`load_events_and_measures` 的 `selectinload("events")` / `selectinload("measures")` 改为 `selectinload(RiskUnit.events).selectinload(RiskEvent.measures)` 与 `selectinload(RiskObject.events).selectinload(RiskEvent.measures)`（相关模型已导入）。

### 修复 6（次要）：清理未使用 import + 补测试

* `backend/tests/test_risk_notice_card_service.py` 清理未使用 import（asyncio、datetime、timezone、RiskZone、RiskUnit、LEVEL_ORDER 等，按实际使用保留）。
* 补 `test_build_right_column_uses_snapshot`：传入 snapshot dict 时右栏直接取快照内容。

### 范围与限制

* 只改 `backend/app/services/risk_notice_card_service.py`、`backend/app/services/risk_notice_card_data.py`、`backend/tests/test_risk_notice_card_service.py`。
* 不修改其他文件。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_risk_notice_card_service.py tests/test_risk_notice_card_data.py -v` 全部 PASS。
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净。
* 提交新 commit（不要 amend 3b4709a），消息：`fix(risk-notice-card): dedupe events and harden timezone handling`，只含上述 3 个文件。

### 汇报

* 状态：DONE | BLOCKED | NEEDS_CONTEXT
* 修改的文件与行
* 测试结果
* 新提交 SHA
