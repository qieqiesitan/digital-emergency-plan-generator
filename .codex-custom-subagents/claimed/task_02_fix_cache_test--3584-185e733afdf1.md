# Codex Custom Subagents task handoff v1

Task: task_02_fix_cache_test

## 目标

修复任务 2 测试中的一个假通过问题：`test_disabled_entry_excluded` 与前一用例共享模块级 `_cache` key `("ent-1","measure_factors")`，全量运行时命中缓存、`db.execute` 未被调用，断言未真正验证 enabled 过滤。按既有先例（反序用例）在测试开头清理缓存。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`15b63e5`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 文件

- 修改：`backend/tests/test_data_dict.py`

## 步骤

- [ ] **步骤 1：在 `test_disabled_entry_excluded` 开头加缓存清理**

在 `async def test_disabled_entry_excluded():` 第一行加入：

```python
    invalidate_dict_cache("ent-1", "measure_factors")
```

（`invalidate_dict_cache` 从 `app.services.data_dict_service` 导入；若文件顶部未导入，补上。）

- [ ] **步骤 2：验证测试真实生效**

在 `backend` 目录 `python -m pytest tests/test_data_dict.py -v`，预期 5 passed。
可加只读探针确认 `db.execute` 被调用（不强制）。

- [ ] **步骤 3：Commit**

在 `.worktrees\dual-prevention` 内：

```bash
git add backend/tests/test_data_dict.py
git commit -m "test(data-dict): invalidate cache in disabled-entry test to avoid false pass"
```

不要提交 TASKS.md；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_02_fix_cache_test --claim-id <claim_id> --exit-code 0 --summary "禁用条目测试缓存清理修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果。

## 规则

- 用 `apply_patch` 编辑；只改列出的 1 个文件；阻塞时停下汇报。
