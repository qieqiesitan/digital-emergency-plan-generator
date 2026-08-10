# Codex Custom Subagents task handoff v1

Task: task_d3_t3

## 任务：缺数据提示条 + 补图按钮（diagrams batch3 任务 3）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

这是 git 分支 `codex/plan-diagrams-enhancement` 的隔离 worktree。当前 HEAD 应为 `68470d8`（batch3 任务 1-2 完成）。启动时 `cd` 到该目录，`git status` 确认干净。

### 验证命令

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams\frontend
npx tsc -b
npx vitest run
```

### 步骤 1：提示条与按钮

修改 `frontend\src\pages\Plan\PlanEditorPage.tsx`：

1. 新增导入：`useMemo`（若未导入）、`Alert`、`Space`（antd）、`regenerateMissingDiagrams`（planService）。
2. 组件内新增：

```typescript
  const missingDiagrams = useMemo(() => {
    const keys = new Set<string>();
    (sections || []).forEach((s) => {
      Object.entries(s.diagram_svgs || {}).forEach(([k, meta]) => {
        if (meta?.placeholder) keys.add(k);
      });
    });
    return Array.from(keys);
  }, [sections]);

  const regenerateDiagramsMut = useMutation({
    mutationFn: () => regenerateMissingDiagrams(id!),
    onSuccess: (r) => {
      message.success(`已重新生成 ${r.regenerated} 张附图`);
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
    },
    onError: () => message.error("重新生成附图失败"),
  });
```

3. 渲染（PageHeader 下方、进度条上方）：

```typescript
        {missingDiagrams.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message={`该企业缺部分数据，${missingDiagrams.length} 张图未生成`}
            description={missingDiagrams.join("、")}
            action={
              <Space>
                <Button size="small" onClick={() => navigate("/enterprises")}>
                  去补数据
                </Button>
                <Button size="small" type="primary" onClick={() => regenerateDiagramsMut.mutate()}>
                  重新生成缺失附图
                </Button>
              </Space>
            }
          />
        )}
```

（`navigate` 已存在；若路由不是 `/enterprises`，按实际页面路由调整，可先读项目路由确认。）

### 步骤 2：类型检查与测试

运行 `npx tsc -b` 与 `npx vitest run`，预期通过。

### 步骤 3：Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams
git add frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "feat(plan): show missing-diagram notice and regenerate button in editor (diagrams batch3)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. tsc / vitest 结果
3. commit SHA（`git rev-parse --short HEAD`）
4. 如有疑虑，说明具体内容

不要提交其他文件；不要推送；不要动 TASKS.md；不要运行后端测试。
