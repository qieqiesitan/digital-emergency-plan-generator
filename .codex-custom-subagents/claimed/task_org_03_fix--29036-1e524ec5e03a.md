# Codex Custom Subagents task handoff v1

Task: task_org_03_fix

## 目标

按组织任务 3 规格审查的 2 条建议修改修复，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`7a28f35`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1：PUT /nodes 422 返回错误列表**（`backend/app/routers/enterprise_org.py`）

422 响应改为 `{"code": "ORG_TREE_INVALID", "errors": errors}`（保留 message 亦可：`{"code":..., "errors": [...], "message": "；".join(errors)}`）；同步更新测试断言。

**2：DELETE 硬删取舍注释**（`backend/app/routers/enterprise_org.py`）

在 DELETE 端点删除处补注释说明硬删取舍（如「成员绑定解除采用硬删，避免历史成员残留；如需审计留痕再改软删 enabled=false」）。

## 验证

- `python -m pytest tests/test_enterprise_org.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；`git diff --check` 干净。

## Commit

```bash
git add backend/app/routers/enterprise_org.py backend/tests/test_enterprise_org.py
git commit -m "fix(org): return error list on org tree invalid and note hard delete tradeoff"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_03_fix --claim-id <claim_id> --exit-code 0 --summary "组织任务3规格建议修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明。

## 规则

- 用 `apply_patch` 编辑；只改列出的 2 个文件；阻塞时停下汇报。
