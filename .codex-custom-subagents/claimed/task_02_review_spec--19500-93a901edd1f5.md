# Codex Custom Subagents task handoff v1

Task: task_02_review_spec

## 规格合规审查：任务 2（RiskNoticeCard 快照模型）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 2 规格）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\models\risk_notice_card.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\db_migration_risk_notice_card.sql`（末尾 COMMIT 之前追加快照表 DDL）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_service.py`（追加 test_snapshot_model_columns）

**模型要求**：RiskNoticeCard 类，表名 `risk_notice_cards`，字段：
* id UUID PK（default str(uuid4)）
* enterprise_id UUID FK enterprises ON DELETE CASCADE，NOT NULL，index
* object_id UUID FK risk_objects ON DELETE CASCADE，NOT NULL，index
* version Integer NOT NULL default 1
* content JSONB NOT NULL
* source String(20) NOT NULL default 'ai'
* created_by UUID FK users ON DELETE SET NULL，nullable
* created_at / updated_at TIMESTAMPTZ server_default now()
* 唯一约束：object_id（uq_risk_notice_cards_object）

**迁移要求**：在 BEGIN/COMMIT 之间（COMMIT 之前）追加 CREATE TABLE IF NOT EXISTS risk_notice_cards（字段与模型一致）+ CREATE INDEX IF NOT EXISTS idx_rnc_enterprise。

**范围限制**：只改这 3 个文件；不创建服务/路由/schemas；commit 消息精确 `feat(risk-notice-card): add snapshot model and migration`。

### 实现者声称构建了什么

* commit `1ef31a4`（worktree `.worktrees\risk-notice-card`），3 文件
* TDD：先追加失败测试 → 创建模型 → 迁移追加快照表 → pytest 2 passed → 提交
* 声称只含任务规定的 3 个文件

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 1ef31a4` 逐行核对。
2. 检查：
* **缺失**：模型字段/类型/约束是否齐全？迁移表结构与模型一致？测试断言是否匹配？
* **多余**：是否添加规格外内容？
* **理解偏差**：DDL 是否在 COMMIT 之前？唯一约束名、索引名是否精确？
* **提交范围**：`git show --stat 1ef31a4` 只含 3 个目标文件？提交消息精确？
* **门禁实测**：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v` 是否 2 passed？
3. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line 引用]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1 已过审（commit 80a56ed + 88d28b5），迁移文件已有 BEGIN/COMMIT。
* 后续任务（任务 5+）会扩展该模型/测试，本任务只审查任务 2 实现。
