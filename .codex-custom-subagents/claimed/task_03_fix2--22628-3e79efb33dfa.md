# Codex Custom Subagents task handoff v1

Task: task_03_fix2

## 修复任务：任务 3 质量审查 2 项重要 + 3 项次要建议

### 背景

任务 3（常量数据）已通过规格审查，质量审查 ❌ 需修复（2 项重要 + 若干次要）。实现提交 `94960e9` + 路径修复 `d8714e3`。

### 修复 1（重要）：LEVEL_COLORS 复用 risk_mapping_service

`backend/app/services/risk_notice_card_data.py` 中删除本模块的 `LEVEL_COLORS` 定义，改为从既有服务导入（`risk_mapping_service.py` 已定义完全一致的映射，含「未评估」#d9d9d9）：

```python
from app.services.risk_mapping_service import LEVEL_COLORS
```

`LEVEL_ORDER` 列表（["重大","较大","一般","低"]，用于取最高等级）**保留**，加注释说明它与 risk_mapping_service 的 LEVEL_ORDER（权重字典）用途不同。

注意检查循环导入：确认 risk_mapping_service 不会 import risk_notice_card_data（目前不会）。

### 修复 2（重要）：测试补 EMERGENCY_TEMPLATES 全覆盖断言

`backend/tests/test_risk_notice_card_data.py` 追加：

```python
def test_emergency_templates_cover_all_types():
    assert set(EMERGENCY_TEMPLATES) == set(GB6441_ACCIDENT_TYPES)
    for accident_type, steps in EMERGENCY_TEMPLATES.items():
        assert len(steps) >= 2, accident_type
```

### 修复 3（次要）：DEFAULT_SIGN_GROUP 拷贝

`DEFAULT_SIGN_GROUP = list(SIGN_GROUPS["其他伤害"])`（避免与常量表同一可变对象别名）。

### 修复 4（次要）：注释修正

「每类最多 2 个」改为「每个类别（警告/禁止/指令/提示）最多 2 个」。

### 修复 5（次要）：超长行折行

`risk_notice_card_data.py` 中超过 120 字符的行（触电/容器爆炸/其他爆炸等）折行到 120 字符以内。

### 范围与限制

* 只改 `backend/app/services/risk_notice_card_data.py`、`backend/tests/test_risk_notice_card_data.py` 两个文件。
* 计划文档 `docs/superpowers/plans/2026-08-11-risk-notice-card.md` 任务 3 代码块中 LEVEL_COLORS 的定义同步改为「从 risk_mapping_service 导入复用」（含未评估 #d9d9d9），保持文档与实现一致（如任务 5 有引用 LEVEL_COLORS 的地方无需改）。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_risk_notice_card_data.py -v` 预期 4 passed 1 failed（failed 仍为 SVG 引用测试，任务 4 转绿）。
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_risk_notice_card_service.py -v` 预期 2 passed 无回归。
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净。
* 提交新 commit（不要 amend），消息：`fix(risk-notice-card): reuse level colors and strengthen template tests`，只含上述文件。

### 汇报

* 状态：DONE | BLOCKED | NEEDS_CONTEXT
* 修改的文件与行
* 测试结果
* 新提交 SHA
