# Codex Custom Subagents task handoff v1

Task: task_org_02_review_spec

## 目标

对「企业组织与成员管理」计划任务 2 的实现做**只读规格合规审查**（对照计划任务 2），输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`25b822e`（父 `df1140f`）
- 文件：
  - `backend/app/services/enterprise_org_service.py`
  - `backend/tests/test_enterprise_org.py`
- 计划：`docs/superpowers/plans/2026-08-15-enterprise-org-members.md` 任务 2

## 审查要点

1. `validate_org_tree`：id 唯一、parent 存在（根 None）、type ∈ {dept,team,position}、members 数组且 name 非空——与计划一致；
2. `sync_org_structure`/`normalize_org_nodes`：向后兼容（name/members[].name）、缺 id 生成短 id；
3. 测试：3 用例覆盖合法/重复+坏 parent/镜像写入，断言有效；
4. 无越界改动：提交仅含上述 2 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_02_review_spec --claim-id <claim_id> --exit-code 0 --summary "组织任务2规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
