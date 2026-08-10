# Codex Custom Subagents task handoff v1

Task: task_d3_t3_fix

## 任务：修复缺图计数语义不匹配

你是一个实现子智能体。代码质量审查发现 `frontend\src\pages\Plan\PlanEditorPage.tsx` 的 `missingDiagrams` 统计的是**唯一 key 数**（Set），而提示语「N 张图未生成」与补图接口 `regenerateMissingDiagrams` 返回的 `regenerated`（占位实例数，同 key 多章节计多次）语义不一致。请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

当前 HEAD 应为 `7d256c5`。启动时 `cd` 到该目录，`git status` 确认干净。

### 验证命令

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams\frontend
npx tsc -b
npx vitest run
```

### 修复方案

`missingDiagrams` 改为统计**占位实例**（每章节每个占位 key 计 1），描述列出「章节：key」列表：

```typescript
  const missingDiagrams = useMemo(() => {
    const items: string[] = [];
    (sections || []).forEach((s) => {
      Object.entries(s.diagram_svgs || {}).forEach(([k, meta]) => {
        if (meta?.placeholder) items.push(`${s.title}：${k}`);
      });
    });
    return items;
  }, [sections]);
```

渲染处同步调整：

```typescript
        {missingDiagrams.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message={`该企业缺部分数据，${missingDiagrams.length} 张图未生成`}
            description={missingDiagrams.join("、")}
            ...
```

（`description` 现在是「章节：key」列表，数量与补图接口计数一致。）

### 完成标准

1. missingDiagrams 为占位实例数组（含章节名）
2. 提示数量与 regenerateMissingDiagrams 返回的 regenerated 语义一致
3. tsc / vitest 通过

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams
git add frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "fix(plan): count placeholder instances not unique keys in missing-diagram banner (diagrams batch3)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. tsc / vitest 结果
3. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
