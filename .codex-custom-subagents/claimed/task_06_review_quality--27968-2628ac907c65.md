# Codex Custom Subagents task handoff v1

Task: task_06_review_quality

## 代码质量审查：任务 6（列表/详情 API 路由）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `661476d`：

* `backend/app/routers/risk_notice_card.py`（新建）
* `backend/app/routers/public_risk_notice.py`（占位）
* `backend/app/main.py`（注册）
* `backend/tests/test_risk_notice_card_api.py`（新建）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 661476d` 通读。
2. 对照项目既有路由模式（`risk_management.py` 路由）检查：
* 命名与可读性、docstring
* 路由内查询效率（列表循环里是否有 N+1 查询——resolve_responsible 传企业对象复用、build_card_data 是否重复查快照）
* 筛选参数校验（非法 level 值处理）
* 异常路径（企业不存在、风险点不存在、对象无数据时的兜底）
* 测试质量（mock 是否真实反映行为、覆盖是否充分）
* `git show --check` 干净度
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 7-9 会追加 AI/快照/导出/token 端点到本路由文件；列表的 snapshot/stale 字段会在快照端点后完善（规格审查已记录，无需重判）。
