# Codex Custom Subagents task handoff v1

Task: task_05_review_spec

## 规格合规审查：任务 5（快照端点透传 signs）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 5 规格 + 设计规格 §7.2/§6）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\schemas\risk_notice_card.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\services\risk_notice_card_service.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_api.py`（+ service 测试）

**要求：**

* RightColumn 支持可选 signs/signs_source（CardData 已声明 signs，继承不冲突）
* save_snapshot：content.signs 为 list 时 normalize_signs 规范化；signs_source 不在 rule/ai/manual 回退 rule；无 signs 时原样保存（AI 优化路径不受影响）
* 测试：API 级 PUT snapshot 带 signs 端到端；service 级规范化/source 回退/原样保持

**实现者偏差：** 提交含 4 文件（含 service 测试，任务文件清单含 service 测试所以合理）；红灯形态是 KeyError 而非 422（pydantic extra=ignore）。请核实合理性。

**范围限制：** commit 消息 `feat(risk-notice-card): persist signs in snapshot with normalization`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show 8d6fe18` 逐行核对。
2. 核对：RightColumn 字段与 CardData 继承、save_snapshot 规范化逻辑、无 signs 原样保持、测试覆盖、提交范围与消息。
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -v`（预期全 PASS）+ 全量回归。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 6 起进入前端。
