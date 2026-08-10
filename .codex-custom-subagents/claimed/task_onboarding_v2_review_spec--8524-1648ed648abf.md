# Codex Custom Subagents task handoff v1

Task: task_onboarding_v2_review_spec

## 任务：规格合规审查——task_onboarding_v2_features

你是代码审查子智能体。请核验引导页 4 项功能增强是否符合需求。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 390726c）。

审查命令：`git log 69f97da..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 需求核验

1. **StepOrg 内联补姓名/电话**：候选组成员姓名/电话可编辑（受控 Input），采纳（单组/全部）时用编辑后 members 保存到 org_structure；已采纳区只读展示姓名电话。
2. **步骤回显**：StepRiskChemical/StepResources 挂载时从后端加载已保存数据到 accepted（loading 态、失败降级）；StepSurrounding 从既有查询派生；不破坏采纳/删除逻辑。
3. **全部采纳/全部取消采纳**：CandidatesReview 两个批量按钮（loading/防重复/失败保留状态）；取消采纳=删除已保存数据+移回候选区；risk/resources 批量接口与 id 重建、surrounding 整体语义、StepOrg 复用。
4. **跳过生成预案完成引导**：StepGenerate 加按钮接通 onDone；OnboardingPage generate 步骤 onDone 标记完成 + 跳 /dashboard（不越界）；「现在生成预案」保持。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint src/pages/Onboarding` 不得新增 error
- `git diff --check` 干净；diff 无 any

### 汇报格式

```
结论：PASS / FAIL（✅ 符合需求 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

