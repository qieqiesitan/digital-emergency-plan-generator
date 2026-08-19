# Codex Custom Subagents task handoff v1

Task: task_06_frontend

## 实现任务 6：前端类型 + service

### 任务描述（来自实现计划 2026-08-15-ai-sign-review.md 任务 6）

**文件：**

* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\types\riskNoticeCard.ts`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\services\riskNoticeCardService.ts`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\frontend\src\services\riskNoticeCardService.test.ts`

### 步骤 1：编写失败测试

在 `frontend/src/services/riskNoticeCardService.test.ts` 追加：

```typescript
it("aiReviewSigns posts and unpacks suggestion", async () => {
  vi.mock("@/services/api", () => ({ api: { post: vi.fn().mockResolvedValue({ data: { data: {
    original_signs: [],
    suggestion: { remove: [], add: ["warning-fall"], reasons: [{ sign_name: "当心滑倒", reason: "有滑倒风险" }] },
  } } }) } }));
  const result = await aiReviewSigns("e1", "o1");
  expect(result.suggestion.add).toContain("warning-fall");
});
```

（按项目现有测试模式实现，见 riskNoticeCardService.test.ts 既有用例。）

运行：`cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts`
预期：FAIL（aiReviewSigns 不存在）

### 步骤 2：实现

1. `frontend/src/types/riskNoticeCard.ts`：
* `SignSuggestion { remove: string[]; add: string[]; reasons: { sign_name: string; reason: string }[] }`
* `AiSignReviewResponse { original_signs: SignItem[]; suggestion: SignSuggestion }`
* `CardData` 加 `signs_source?: "rule" | "ai" | "manual"`（后端已回填）

2. `frontend/src/services/riskNoticeCardService.ts`：

```typescript
export async function aiReviewSigns(enterpriseId: string, objectId: string): Promise<AiSignReviewResponse> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}/ai-review-signs`, { method: "POST" });
  return res.data;
}
```

（按项目既有请求封装模式。）

### 步骤 3：运行测试验证通过

`cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts` 预期 PASS；`npx tsc -b` 0 错误。

### 步骤 4：Commit

```bash
git add frontend/src/types/riskNoticeCard.ts frontend/src/services/riskNoticeCardService.ts frontend/src/services/riskNoticeCardService.test.ts
git commit -m "feat(risk-notice-card): add frontend sign review types and service"
```

### 范围与限制

* 只改前端类型、service、测试。
* 不修改页面组件/后端。
* 提交前确认 `git status` 只含上述 3 个文件。

### 上下文

* worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=ee59902）。
* 后端 6+1 端点已就绪（含 ai-review-signs）；CardData 已回填 signs_source。
* 任务 7-8 会使用本 service 做页面交互。
