# Codex Custom Subagents task handoff v1

Task: task_org_03_review_quality2

## 目标

对组织任务 3 的**质量修复提交做只读复审**（2 条建议：null role/enabled 拒绝 + extra=allow 透传扩展字段）。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`4aa59d5`（父 `d4bdd58`）
- 文件：`backend/app/schemas/enterprise_org.py`、`backend/app/routers/enterprise_org.py`、`backend/tests/test_enterprise_org.py`

## 复审要点

1. PUT /members 显式 `role`/`enabled` null → 422（`key in updates and updates[key] is None` 判定正确，未传字段不误判）；`position`/`org_node_id` null 清空保留；
2. `OrgNode`/`OrgMember` `extra="allow"`：model_dump 保留扩展字段（description/role/phone），validate/normalize 路径不受影响；
3. 测试：6 条新增用例有效（schema 透传 ×2、路由扩展字段落库、null 422 ×2、position 清空）；
4. 无越界改动：提交仅含上述 3 个文件。

## 验证

- `python -m pytest tests/test_enterprise_org.py -v` 预期 32 passed；`git show --check 4aa59d5` 干净。

## 输出格式

- 结论：✅ 通过（建议已解决）/ ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_03_review_quality2 --claim-id <claim_id> --exit-code 0 --summary "组织任务3质量复审2完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
