# Codex Custom Subagents task handoff v1

Task: task_02_review_quality

## 代码质量审查：任务 2（RiskNoticeCard 快照模型）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `1ef31a4`：

* `backend/app/models/risk_notice_card.py`（新建）
* `backend/db_migration_risk_notice_card.sql`（追加快照表 DDL）
* `backend/tests/test_risk_notice_card_service.py`（追加 test_snapshot_model_columns）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 1ef31a4` 通读 diff。
2. 对照项目既有模型模式（参考 `backend/app/models/risk_management.py` 的 RiskZone/RiskObject 写法）检查：
* 命名是否清晰准确
* 是否遵循项目代码库模式（mapped_column 风格、relationship 是否必要）
* 是否有魔法值、重复、可读性问题
* 测试是否验证真实行为
* `git show --check` 是否干净
* 迁移 DDL 与模型的 server_default/onupdate 是否一致（如 updated_at 的 onupdate 在 DDL 中缺失是否有影响——SQLAlchemy onupdate 是 ORM 层行为，DDL 无对应项是正常还是需要处理）
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 后续任务（任务 5+）会扩展该模型与测试，本任务只审查任务 2 范围。
