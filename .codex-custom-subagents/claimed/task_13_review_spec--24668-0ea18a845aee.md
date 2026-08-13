# Codex Custom Subagents task handoff v1

Task: task_13_review_spec

## 规格合规审查：任务 13（公开只读页）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 13 规格 + 设计规格 §10.3）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\frontend\src\pages\PublicRiskNoticePage.tsx`

**功能要求**（设计规格 §10.3）：

* 路由 /r/:token（登录守卫外，已注册）；useParams 取 token
* useQuery fetchPublicCard，retry: false
* 加载中：居中 Spin
* 错误：居中「卡片不存在或链接已失效」（与后端 404 文案一致）
* 成功：RiskNoticeCard 渲染，max-width 480px 居中
* 底部提示条：「公开只读页面 · 数据来自系统快照 · 无需登录」

**范围限制**：只改该文件；commit 消息 `feat(risk-notice-card): add public read-only page`。

### 实现者声称构建了什么

* commit `10803c4`（1 文件），tsc/eslint 0、vitest 61 通过
* 公开页完整实现（Spin/Result 404/RiskNoticeCard/提示条）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 10803c4` 逐行核对。
2. 核对功能要素、提交范围与消息。
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）+ `cd frontend && npx eslint src/pages/PublicRiskNoticePage.tsx`（0 问题）。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-12 已过审；任务 14 表单字段。
