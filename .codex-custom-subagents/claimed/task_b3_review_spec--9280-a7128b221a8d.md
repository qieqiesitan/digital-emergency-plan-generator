# Codex Custom Subagents task handoff v1

Task: task_b3_review_spec

## 任务：规格合规审查——task_b3_completion（含修复 a25f3c8）

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `28accd4` 与 `a25f3c8`：

git show 28accd4 --stat、git show a25f3c8 --stat，并阅读实际代码。

### 要求的内容（任务 B3 原文摘要 + 规格 6.6）

1. onboarding_service.compute_completion：6 模块加权（企业信息 10 / 组织架构 15 / 风险与危化品 30 / 应急资源 15 / 周边环境 10 / 报告 20），返回 {percent, modules[]}。
2. 完成标准（规格 6.6）：企业信息=名称+地址+行业；组织架构=总指挥姓名已填；风险与危化品=风险点≥1 或危化品≥1 且已关联；应急资源=资源≥1；周边=周边单位或敏感目标≥1；报告=两份报告均已生成。
3. GET /enterprises/{id}/completion 接口（企业不存在 404）；onboarding router 注册到 main.py。
4. 企业列表 list_enterprises 每项加 completion 字段；EnterpriseResponse.completion。
5. 新测试 test_onboarding_completion.py（100% 全完成 + 0% 空企业 + 修复后追加的总指挥/关联判定测试）。
6. Commit：feat(onboarding): enterprise data completion aggregation endpoint（+ 修复 commit）。

### 实现者声称构建了什么

- 28accd4：服务/接口/列表字段/路由注册/测试（RiskEvent 无 enterprise_id，用 JOIN RiskObject 归属）
- a25f3c8：组织架构判定改总指挥姓名、风险与危化品改已关联判定 + 追加测试
- 全量 258 passed / 0 failed
- 自审说明：测试 mock 适配（AsyncMock → Mock，SQLAlchemy Result 同步方法）

### 你的工作

阅读实际代码并验证：

缺失的需求：所有要求是否实现？完成标准与规格 6.6 逐项一致？
多余的工作：是否构建了未被要求的内容？
理解偏差：权重/模块 key/标签是否与规格一致？列表 completion 字段是否可用？报告模块"可跳过"语义（规格 6.6）当前如何处理（未生成时 done=False）——评估是否可接受（引导页 UI 层处理可选语义）。

通过阅读代码来验证，而非信任报告。

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
