# Codex Custom Subagents task handoff v1

Task: task_org_06_review_spec2

## 目标

对组织任务 6 的**规格修复提交做只读复审**（1 必须修复 + 3 建议）。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`1419272`（父 `963dab2`）
- 文件：`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`、`backend/app/routers/enterprise_org.py`、`backend/tests/test_enterprise_org.py`

## 复审要点

1. treeData 只映射根节点（含孤儿挂根处理），buildChildren 嵌套正确，不再重复渲染；
2. validateNodes 补 members[].name 校验；
3. delete_member 返回 ApiResponse(data=None)，前端解包 null，测试断言同步；
4. buildChildren 环防护（seen）；
5. 无越界改动：提交仅含上述 3 个文件。

## 验证

- `python -m pytest tests/test_enterprise_org.py -v` 预期 64 passed；`npx vitest run` 97 passed；`npx tsc -b` 通过；`git show --check 1419272` 干净。

## 输出格式

- 结论：✅ 通过 / ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_06_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "组织任务6规格复审完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest/tsc、git log/show/diff）；任务池命令在任务池目录执行。
