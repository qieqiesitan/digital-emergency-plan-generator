# Codex Custom Subagents task handoff v1

Task: task_ai_generate_review_spec

## 任务：规格合规审查——task_ai_generate_experience

你是代码审查子智能体。请核验 AI 生成体验修复是否符合需求。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 视当前最新提交，含 2d1a8ff）。

审查命令：`git show 2d1a8ff`（AI 生成体验修复提交），逐文件阅读实际代码。

### 需求核验

1. **前端超时**：api.ts axios timeout 600000 → 180000（对齐后端 120s）。
2. **错误透出**：引导页各步骤（StepRiskChemical/StepResources/StepSurrounding/StepOrg/ImportDrawer/SurroundingAIGenerateModal）生成/保存 catch 解析 `axios error.response?.data?.detail`，用户能看到后端 504「AI 响应超时」等真实信息。
3. **loading 文案**：各步骤 AI 生成按钮提示「AI 生成中，通常需要 1-2 分钟，请耐心等待」。
4. **登录过期提示**：AuthContext auth:logout handler 提示「登录已过期，请重新登录」，一次性。
5. **后端**：确认 llm_client.py 120s 超时 + 504 提示已存在（只读）。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error
- `git diff --check` 干净；diff 无 any

### 汇报格式

```
结论：PASS / FAIL（✅ 符合需求 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

