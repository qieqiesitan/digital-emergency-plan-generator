# Codex Custom Subagents task handoff v1

Task: task_org_01_review_spec

## 目标

对「企业组织与成员管理」计划任务 1 的实现做**只读规格合规审查**，对照 B 规格 §5.11 与计划任务 1，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`df1140f`（父 `929e0dd`）
- 文件：
  - `backend/db_migration_enterprise_org.sql`
  - `backend/app/models/enterprise_org.py`
  - `backend/tests/test_enterprise_org.py`
- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §5.11（enterprise_members）；计划 `docs/superpowers/plans/2026-08-15-enterprise-org-members.md` 任务 1

## 审查要点

1. 迁移：列/类型/FK CASCADE/唯一约束/索引与规格一致、幂等（IF NOT EXISTS）；
2. 模型：UUID 主键、显式 FK、role 默认 member、enabled setdefault（PlanSection 先例）、时间戳、唯一约束命名；
3. 测试：元数据/构造断言有效（注意 worker 将 `set(cols)` 改为 `set(cols.keys())` 的合理性）；无空断言；
4. 无越界改动：提交仅含上述 3 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_01_review_spec --claim-id <claim_id> --exit-code 0 --summary "组织任务1规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
