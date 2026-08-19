# Codex Custom Subagents task handoff v1

Task: task_02_review_quality

## 代码质量审查：任务 2（normalize_signs 规范化函数）

你正在审查一个已通过规格合规审查的实现的质量。独立阅读实际代码，不信任报告。

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review）的 commit `5157f5e`：

* `backend/app/services/risk_notice_card_service.py`
* `backend/tests/test_risk_notice_card_service.py`

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show 5157f5e` 通读。
2. 对照项目既有服务模式（match_signs）检查：VALID_SVG_NAMES 定义位置与可维护性、normalize_signs 实现质量（类型标注、边界处理、与 match_signs 的 DRY 程度）、测试质量（规格审查已提示去重断言空转、category 缺失静默丢弃）、`git show --check` 干净度。
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 5（快照透传）会调用 normalize_signs；规格审查已确认实现符合规格（含 2 项参考）。
