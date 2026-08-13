# Codex Custom Subagents task handoff v1

Task: task_03_review_quality

## 代码质量审查：任务 3（常量数据：标志映射 + 应急处置模板）

你正在审查一个已通过规格合规审查（含修复复审）的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）：

* commit `94960e9`：`backend/app/services/risk_notice_card_data.py`（新建）+ `backend/tests/test_risk_notice_card_data.py`（新建）
* commit `d8714e3`：修复测试路径 parents[2]→parents[1]（含计划文档同步）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 94960e9` + `git show d8714e3` 通读。
2. 检查：
* 命名与可读性（W/P/I/N helper 命名、SIGN_GROUPS 字典结构）
* 是否遵循项目代码库模式（对比 `backend/app/services/risk_ai_service.py` 等既有常量/服务文件的风格）
* 魔法值、重复、可维护性（如 source="ai" 之类是否出现在本模块）
* 测试质量：断言是否验证真实行为、是否有弱化
* `git show --check` 是否干净
* 代码行是否有超长等可读性问题（项目无 linter，纯可读性评估）
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 4 将创建 SVG 资产使引用测试转绿；任务 5 组装服务会使用本模块常量。
* 已知说明：断言修正（索引单调不减）已由规格审查确认合理，无需重判；请关注实现质量本身。
