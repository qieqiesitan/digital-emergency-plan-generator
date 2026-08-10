# Codex Custom Subagents task handoff v1

Task: task_final_fix

## 任务：修复最终审查发现的 2 个重要问题

你是一个实现子智能体。最终审查发现 2 个重要问题，请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

当前 HEAD 应为 `6360dcb`。启动时 `cd` 到该目录，`git status` 确认干净。

### 问题 1：export_trace.log 调试残留

`backend\app\routers\export.py::export_plan_docx` 中存在调试日志：

```python
    with open("export_trace.log", "a", encoding="utf-8") as _t:
        import datetime as _dt
        _t.write(f"EXPORT START {_dt.datetime.now()}\n")
```

以及后面 `EXPORT DOCX DONE` 的写入。这些是遗留调试代码，会污染工作目录。

修复：删除 `export.py` 中所有 `export_trace.log` 写入代码（包括函数内 import datetime 的调试块与对应变量）。全量搜索确认无残留。

### 问题 2：duplicate 副本无编号导致导出 400

`backend\app\routers\plans.py::duplicate_plan` 创建副本时未复制 `plan_number`/`version_number`，而导出接口要求两者非空（否则 400「请先设置预案编号与版本号」），且当前前端无编辑编号的入口，用户无法补全。

修复方案（选择其一，推荐 A）：

- **方案 A（推荐）**：`duplicate_plan` 创建副本时复制原预案的 `plan_number`/`version_number`，并自动生成新编号避免重复：
  - `plan_number`：复制原值并追加后缀，如 `原编号-C`（长度限制 100 字符内，超出截断）；或调用 `_generate_plan_number` 重新生成（同企业同类型数量+1，与 create_plan 逻辑一致）。
  - `version_number`：复制原值或默认 `A-{year}-{month}`。
  - 推荐：`plan_number = _generate_plan_number(enterprise_name, plan_type, seq)` 重新生成（与 create_plan 一致，保证唯一），`version_number = f"A-{year}-{month:02d}"` 或复制原值。
- **方案 B**：在 PlanUpdate schema/update_plan 端点支持修改 plan_number/version_number，前端编辑页/创建页提供编辑入口。改动面较大。

选 A 时确认 `duplicate_plan` 内可拿到 enterprise name（可查询 enterprise 或复用 p.enterprise 关系）。

### 验证

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\ -q --ignore=tests\test_autofill_research.py
```

预期：全部通过（若新增测试则一并加入）。

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement
git add backend/app/routers/export.py backend/app/routers/plans.py
git commit -m "fix(plan): remove export trace logging and assign numbers on duplicate (batch3)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 两个问题的修复方式
3. pytest 结果
4. commit SHA（`git rev-parse --short HEAD`）

不要提交其他文件；不要推送；不要动 TASKS.md。
