# Codex Custom Subagents task handoff v1

Task: task_03_review_quality

## 代码质量审查：任务 3（review_signs AI 服务）

你正在审查一个已通过规格合规审查的实现的质量。独立阅读实际代码，不信任报告。

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review）的 commit `101c8ae`：

* `backend/app/services/risk_notice_card_ai.py`
* `backend/tests/test_risk_notice_card_api.py`

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show 101c8ae` 通读。
2. 对照项目既有 AI 服务模式（optimize_right_column）检查：提示词组装质量（可读性、长度、重复）、解析容错（仅捕获 JSONDecodeError 是否够）、类型兜底、测试质量（mock 是否真实）、命名/风格、`git show --check` 干净度。
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 4 会新增 ai-review-signs 端点调用本服务。
* 规格审查已确认实现符合规格（含 3 项参考：非 str 返回、None 输入、mock 噪音）。
