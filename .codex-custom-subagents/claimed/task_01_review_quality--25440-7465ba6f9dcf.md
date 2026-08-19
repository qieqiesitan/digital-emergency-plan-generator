# Codex Custom Subagents task handoff v1

Task: task_01_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 1 的实现做**只读代码质量审查**（规格合规审查已通过），聚焦代码质量与项目模式一致性，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 提交：`618b8bc`（工作树 `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`，分支 `codex/dual-prevention`）
- 文件：
  - `backend/db_migration_data_dicts.sql`
  - `backend/app/models/data_dict.py`
  - `backend/tests/test_data_dict.py`
- 可对照：项目既有模型（`backend/app/models/enterprise.py`、`backend/app/models/role.py`、`backend/app/models/risk_notice_card.py`）与既有迁移 SQL（如 `backend/db_migration_risk_notice_card.sql`）的风格

## 审查要点

1. 与项目既有模型/迁移风格一致性（命名、类型注解、Mapped/mapped_column 用法、UUID 字符串主键、时间戳约定）；
2. `DataDict.__init__` 的 setdefault 模式与既有 `PlanSection` 先例的一致性、可维护性；
3. 测试质量：断言是否有意义、是否覆盖规格关键行为、是否有脆弱断言；
4. SQL 可读性、种子数据可维护性（INSERT 列是否显式、幂等性 IF NOT EXISTS）；
5. 潜在问题：命名、可空性、索引、约束、类型；
6. 是否有过度工程或不必要的复杂度（YAGNI）。

## 输出格式

在最终回复中给出：

- 结论：✅ 通过 / ❌ 需修复
- 问题清单，每条标注严重级：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_01_review_quality --claim-id <claim_id> --exit-code 0 --summary "代码质量审查完成"
```

## 规则

- 全程只读：不创建/修改/删除任何文件，不运行会改状态的命令（可运行 pytest 只读验证、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
