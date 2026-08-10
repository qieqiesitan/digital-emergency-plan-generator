# Codex Custom Subagents task handoff v1

Task: task_b3_t3_fix

## 任务：恢复 background 批量生成的取消检查

你是一个实现子智能体。规格审查发现 `backend\app\routers\generation.py` 批量重构后，`generate_batch_background` 丢失了原有的取消检查（原逻辑在每章循环前检查 `if not _active_generations.get(plan_id): break`）。请恢复该行为并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

当前 HEAD 应为 `2ce46a8`。启动时 `cd` 到该目录，`git status` 确认干净。

### 参考（git show 2ce46a8^ 中 generate_batch_background 原逻辑）

```python
                for section_key, section_title in section_ids:
                    if not _active_generations.get(plan_id):
                        break
```

### 测试命令

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\test_generation_batch_refactor.py -v
```

### 步骤 1：实现取消检查

修改 `backend\app\routers\generation.py`：

1. `_run_batch_generation` 增加可选参数 `should_stop=None`（可调用对象，返回 bool 时中断循环）：

```python
    for i, (section_key, section_title) in enumerate(section_tuples):
        if should_stop and should_stop():
            break
        ...
```

2. `generate_batch_background` 调用时传 `should_stop=lambda: not _active_generations.get(plan_id, False)`。
3. `generate_batch`（SSE）调用时 `should_stop=None`（SSE 端点原逻辑通过 `_active_generations` 检查，确认其行为已保留则传 None 即可；若 SSE 原逻辑也有取消检查，则同样传入）。

### 步骤 2：运行测试验证通过

运行 pytest 命令。
预期：PASS（1 passed）。

### 步骤 3：全量回归

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\ -q --ignore=tests\test_autofill_research.py
```

预期：全部通过。

### 步骤 4：Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement
git add backend/app/routers/generation.py backend/tests/test_generation_batch_refactor.py
git commit -m "fix(plan): restore cancel check in background batch generation (batch3)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. pytest 最终输出与全量回归结果
3. commit SHA（`git rev-parse --short HEAD`）
4. 如有疑虑，说明具体内容

不要提交其他文件；不要推送；不要动 TASKS.md。
