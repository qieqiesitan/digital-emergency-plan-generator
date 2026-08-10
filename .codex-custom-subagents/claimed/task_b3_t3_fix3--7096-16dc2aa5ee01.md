# Codex Custom Subagents task handoff v1

Task: task_b3_t3_fix3

## 任务：修复批量重构的行为差异（代码质量审查 FAIL）

你是一个实现子智能体。代码质量审查发现 `backend\app\routers\generation.py` 批量重构（commits 2ce46a8/f414e5f/9be17f8）相对原实现存在 4 个重要行为差异，需修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

当前 HEAD 应为 `9be17f8`。启动时 `cd` 到该目录，`git status` 确认干净。

### 参考原实现

```powershell
git show 2ce46a8^:backend/app/routers/generation.py
```

对比原 `generate_batch`（SSE）与 `generate_batch_background` 的行为。

### 测试命令

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\test_generation_batch_refactor.py tests\test_plan_version_snapshot.py -v
```

### 需修复的问题（按优先级）

**1. background 编号提示行为变化（重要）**

原 `generate_batch_background` 调用 `_build_section_prompt` 时不传 `section_number`（None）；重构后公共函数固定传 `section_number=i + 1`，导致 background 生成的提示词出现「这是应急预案的第N个章节」编号提示，行为变化。

修复：`_run_batch_generation` 增加参数 `use_section_number: bool = True`；background 调用传 `use_section_number=False`（此时 `_build_section_prompt` 不传 `section_number`）；SSE 调用保持 True（与原 SSE 行为一致）。

**2. section_done 事件契约变化（重要）**

原 SSE 的 section_done 事件带 `completed`/`failed` 字段：`sse_event("section_done", section_key=..., message=..., completed=completed, failed=failed)`。重构后丢失。

修复：SSE 端点发出的 section_done 事件恢复 `completed`/`failed` 字段（维护计数器，完成一章 +1，与公共函数返回的 completed/failed 最终一致即可；每章完成时按当前计数发事件）。

**3. SSE 流后失败未上报 / done 不一致（重要）**

原实现 sse_stream 抛异常时 run_background 的 except 发 error 事件，然后该章计入 failed 但流程继续；重构后 sse_stream 内部先发 error 再重抛，公共函数捕获后记录 failed。核对最终 batch_done 的 completed/failed 与实际 outcomes 一致；若 `_GenerationCancelled` 被公共函数当作普通 Exception 捕获（导致 failed+1 而非中断），需修复：公共函数循环前检查 `_GenerationCancelled` 类型并中断（或在 on_progress 抛异常时 break，不计数失败）。

**4. 尾部重复（一般）**

两个端点「状态判定 + 自动版本快照 + batch_done/返回」尾部逻辑重复。抽取模块级辅助 `_finalize_batch_result(bg_db, plan_id, completed, failed, failed_sections, updated)` 返回快照版本号等，两个端点复用。若改动过大可保留两处但确保逻辑一致（DRY 优先，但行为正确第一）。

### 完成标准

1. 上述 1-3 行为差异修复，4 尽量 DRY
2. 全量回归通过
3. 若有合理理由保留某差异，在报告 DONE_WITH_CONCERNS 中说明

### 步骤：全量回归

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\ -q --ignore=tests\test_autofill_research.py
```

预期：全部通过。

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement
git add backend/app/routers/generation.py backend/tests/test_generation_batch_refactor.py
git commit -m "fix(plan): align batch refactor behavior with original endpoints (batch3)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 每项问题的修复方式说明
3. pytest 最终输出与全量回归结果
4. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
