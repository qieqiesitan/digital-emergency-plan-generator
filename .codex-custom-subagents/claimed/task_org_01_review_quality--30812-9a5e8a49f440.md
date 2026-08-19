# Codex Custom Subagents task handoff v1

Task: task_org_01_review_quality

## 目标

对「企业组织与成员管理」计划任务 1 的实现做**只读代码质量审查**（规格审查已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`df1140f`（父 `929e0dd`）
- 文件：
  - `backend/db_migration_enterprise_org.sql`
  - `backend/app/models/enterprise_org.py`
  - `backend/tests/test_enterprise_org.py`
- 可对照：`backend/app/models/data_dict.py`、`backend/app/models/risk_management.py`、`backend/db_migration_data_dicts.sql`

## 审查要点

1. 模型与项目风格一致性（Mapped/mapped_column、UUID 字符串主键、FK、__init__ setdefault、时间戳）；
2. 迁移可读性与幂等；
3. 测试质量（断言有效、无脆弱断言）；
4. 无过度工程、无越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_01_review_quality --claim-id <claim_id> --exit-code 0 --summary "组织任务1质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
