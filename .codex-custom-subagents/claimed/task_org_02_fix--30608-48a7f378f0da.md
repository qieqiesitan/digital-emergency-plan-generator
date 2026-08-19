# Codex Custom Subagents task handoff v1

Task: task_org_02_fix

## 目标

按组织任务 2 质量审查的 2 条建议修改修复，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`25b822e`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1：畸形输入防御**（`backend/app/services/enterprise_org_service.py`）

- 节点循环前先判 `isinstance(n, dict)`，非 dict 报「节点必须是对象」并跳过；
- 成员循环：`isinstance(m, dict)` 后才取 name，非 dict 报「节点 {nid} 存在非法成员」；
- 行为不变（合法输入结果一致）。

**2：补测试**（`backend/tests/test_enterprise_org.py`）

- `normalize_org_nodes`：缺 id 生成 `node-<n>`、缺 members 默认 `[]`、浅拷贝不修改输入顶层（修改输出 dict 不影响输入）；
- `validate_org_tree` 补：非 dict 节点不崩溃返回错误、非法 type、members 非列表、空 name、字符串成员不崩溃。

## 验证

- `python -m pytest tests/test_enterprise_org.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；`git diff --check` 干净。

## Commit

```bash
git add backend/app/services/enterprise_org_service.py backend/tests/test_enterprise_org.py
git commit -m "fix(org): guard malformed nodes in org tree validation and cover normalize"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_02_fix --claim-id <claim_id> --exit-code 0 --summary "组织任务2防御+测试修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明。

## 规则

- 用 `apply_patch` 编辑；只改列出的 2 个文件；阻塞时停下汇报。
