# Codex Custom Subagents task handoff v1

Task: task_03_review_spec

## 规格合规审查：任务 3（review_signs AI 服务）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 3 规格 + 设计规格 §8）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\services\risk_notice_card_ai.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_api.py`

**要求（设计规格 §8）：**

* `review_signs(db, user_id, enterprise_name, object_name, category, location, events, current_signs, catalog)` → 返回 `{remove, add, reasons}`
* 提示词：system=安全生产专家；user=风险点上下文 + 事件 + 当前标志 + 候选库（只能从这里选）+ 严格 JSON 约束（remove 必须来自当前标志、add 来自候选库且不重复、每类≤2 总数≤8、理由具体、中文）
* 解析失败 → logger.warning + HTTPException(502, "AI 返回格式异常，无法解析 JSON")
* remove/add 非 list、reasons 非 list → 回落空列表

**实现者补充**：按规格 §11 追加非法 JSON→502、非 list 回落 2 个服务级测试。

**范围限制**：只改 2 文件；commit 消息 `feat(risk-notice-card): add ai sign review service`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show 101c8ae` 逐行核对。
2. 核对：提示词结构与约束、解析与容错、返回结构、测试覆盖（含实现者补充的兜底测试）、提交范围与消息。
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v`（预期全 PASS）+ 全量回归。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 4 会新增 ai-review-signs 端点调用本服务。
