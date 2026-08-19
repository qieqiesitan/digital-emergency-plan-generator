# Codex Custom Subagents task handoff v1

Task: task_06_review_spec

## 规格合规审查：任务 6（前端类型 + service）

你正在审查一个实现是否与其规格匹配。不要信任实现者的报告，必须独立阅读实际代码验证。

### 要求的内容（任务 6 规格）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\types\riskNoticeCard.ts`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\services\riskNoticeCardService.ts`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\services\riskNoticeCardService.test.ts`

**要求：**

* 类型：SignSuggestion（remove/add: string[]、reasons）、AiSignReviewResponse（original_signs: SignItem[]、suggestion）、CardData 加 signs_source?: "rule"|"ai"|"manual"
* service：aiReviewSigns POST /enterprises/{eid}/risk-notice-cards/{oid}/ai-review-signs，返回解包
* 测试：aiReviewSigns 用例

**实现者适配：** 测试用文件级 apiMock（vi.hoisted）替代模块内 vi.mock（与既有用例一致）；service 用项目既有 api 封装；worktree 复制 node_modules。请核实合理性。

**范围限制：** 只改 3 文件；commit 消息 `feat(risk-notice-card): add frontend sign review types and service`。

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`，`git show e7f0ac3` 逐行核对。
2. 核对：类型与后端 schemas 一致（SignItem/signs_source）、service URL/方法/解包、测试断言、适配合理性、提交范围与消息。
3. 门禁实测：`cd frontend && npx tsc -b`（0 错误）+ `cd frontend && npx vitest run`（全通过）。
4. 报告：✅ 符合规格 或 ❌ 发现问题（file:line）。

### 上下文

* worktree 独立分支 codex/ai-sign-review，审查只读，不修改文件、不提交。
* 任务 7-8 使用 aiReviewSigns 做页面交互。
