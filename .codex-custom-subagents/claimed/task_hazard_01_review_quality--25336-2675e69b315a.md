# Codex Custom Subagents task handoff v1

Task: task_hazard_01_review_quality

## 目标

对「隐患排查治理」计划任务 1 的实现做**只读代码质量审查**（规格审查已通过），聚焦代码质量。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`076e4f9`（父 `9ebfe48`）
- 文件：`backend/db_migration_hazard_management.sql`、`backend/app/models/hazard_management.py`、`backend/tests/test_hazard_models.py`
- 可对照：`backend/app/models/risk_management.py`、`backend/app/models/data_dict.py`、`backend/db_migration_data_dicts.sql`

## 审查要点

1. 模型风格一致性（Mapped/mapped_column、UUID 主键、FK、__init__ setdefault、时间戳、唯一约束命名）；
2. 迁移可读性/幂等（部分唯一索引、ON CONFLICT）；
3. 10 类模型职责清晰、关系（relationship）是否需要（评估 lazy 策略）；
4. 测试质量（21 断言）；
5. 无过度工程、无越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_01_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患任务1质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
