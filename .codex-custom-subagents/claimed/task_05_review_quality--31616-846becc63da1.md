# Codex Custom Subagents task handoff v1

Task: task_05_review_quality

## 代码质量审查：任务 5（schemas + CardData 组装服务）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `3b4709a`：

* `backend/app/schemas/risk_notice_card.py`（新建）
* `backend/app/services/risk_notice_card_service.py`（新建）
* `backend/tests/test_risk_notice_card_service.py`（追加 5 个测试）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 3b4709a` 通读。
2. 对照项目既有服务模式（`risk_mapping_service.py`、`risk_stats_service.py`、`risk_ai_service.py`）检查：
* 命名与可读性
* 类型注解与 docstring
* 魔法值/重复（如 source="ai" 字符串、通用模板兜底文案）
* 函数职责边界（load_events_and_measures 的查询效率——selectinload 字符串路径、N+1）
* 时间比较（is_stale 的时区处理）
* 测试质量（是否验证真实行为）
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 6 路由将使用本服务；任务 7 AI 优化 + 快照端点复用 save_snapshot/build_right_column。
* 已知：规格审查已确认 2 处计划修正合理（compute_code 身份兜底、match_signs 返回 dict 列表），无需重判。
