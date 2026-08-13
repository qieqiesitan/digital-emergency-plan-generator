# Codex Custom Subagents task handoff v1

Task: task_07_review_quality

## 代码质量审查：任务 7（AI 优化 + 快照端点）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `0901c75`：

* `backend/app/services/risk_notice_card_ai.py`（新建）
* `backend/app/routers/risk_notice_card.py`（追加 2 端点）
* `backend/tests/test_risk_notice_card_api.py`、`test_risk_notice_card_service.py`（追加）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 0901c75` 通读。
2. 对照项目既有 AI 服务模式（`risk_ai_service.py` 的 suggest_measures 等）检查：
* AI prompt 质量与 JSON 解析健壮性（非法 JSON、字段类型错误）
* 异常处理粒度（统一 502 是否合理、日志记录）
* 端点代码风格（与既有端点一致、docstring）
* 测试质量（mock 是否真实、覆盖是否充分）
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 8-9 会追加导出与公开端点。
