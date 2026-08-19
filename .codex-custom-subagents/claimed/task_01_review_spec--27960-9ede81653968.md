# Codex Custom Subagents task handoff v1

Task: task_01_review_spec

## 规格合规审查：任务 1（快照 content 扩展 + build_card_data 支持 signs）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 1 规格）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\app\services\risk_notice_card_service.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\backend\tests\test_risk_notice_card_service.py`

**要求**：`build_card_data` 从快照 content 读取非空 `signs` 时优先使用（dict 列表自动转 SignItem），否则回退 `match_signs`；无快照/快照无 signs 行为不变（向后兼容）。

**实现者报告的测试加固**：原计划用例的快照标志（warning-fire）恰好等于规则 match_signs(["火灾"]) 首项，无法证明快照优先；已改用规则不可能产出的标志（notice-ventilation/注意通风）并断言 len==1。请核实该加固合理且确实验证了快照优先语义。

**范围限制**：只改 2 个文件；commit 消息 `feat(risk-notice-card): support snapshot signs in card data`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show b4dbf07` 逐行核对。
2. 核对：快照 signs 优先逻辑、无快照回退、测试加固合理性、提交范围与消息。
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`（预期全 PASS）+ 全量回归。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 2-5 将在此基础上扩展。
