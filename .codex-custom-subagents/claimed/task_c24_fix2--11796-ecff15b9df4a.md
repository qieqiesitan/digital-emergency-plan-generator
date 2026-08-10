# Codex Custom Subagents task handoff v1

Task: task_c24_fix2

## 任务：修复 C2-4 换风格回调回归（重生成后确认态丢失）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 c0fb2c5。启动时 `cd` 到该目录，git status 确认干净。

### 回归：换风格重生成后 sampleDone 不复位

`frontend/src/pages/Plan/PlanEditorPage.tsx` 换风格按钮（:369-372）：`setSampleDone(false)` 后调用 `startRealtimeGeneration([sections![0].section_key])` 未传完成回调，重生成成功后 `sampleDone` 永不复位，确认态横幅消失。

修复：传回调：

```tsx
<Button
  onClick={() => {
    setSampleDone(false);
    startRealtimeGeneration([sections![0].section_key], () => setSampleDone(true));
  }}
>
  换风格重新生成样章
</Button>
```

（确认 `startRealtimeGeneration` 签名支持第二个参数 `onBatchDone`；若已支持直接传。）

### 次要（顺手）：重试失败章节同样传回调

`:433` 附近「重试失败章节」的 `startRealtimeGeneration(failedSections.map(...))` 同样补 `() => setSampleDone(true)`（若处于 sample 场景；全量场景传了也无副作用，可统一补）。

### 步骤 3：验证 + Commit

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/pages/Plan/PlanEditorPage.tsx`（对比基线无新增错误）

预期：tsc 通过；无新增 ESLint 错误。

```bash
git add frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "fix(plan): restore sample confirmation after style regeneration"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 PlanEditorPage.tsx 的 startRealtimeGeneration 签名与换风格/重试调用处
2. 按步骤修复
3. tsc + eslint 验证（对比基线无新增错误）
4. 提交
5. 自审：换风格成功后再进确认态？重试成功也进？无回归？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
