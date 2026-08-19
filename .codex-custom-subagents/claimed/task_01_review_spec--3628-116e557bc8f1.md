# Codex Custom Subagents task handoff v1

Task: task_01_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 1 的实现做**只读规格合规审查**，对照 A 规格 §5.4（数据字典表）与实现计划任务 1 的范围，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 提交：`618b8bc`（工作树 `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`，分支 `codex/dual-prevention`）
- 文件：
  - `backend/db_migration_data_dicts.sql`（建表 + 15 条系统种子）
  - `backend/app/models/data_dict.py`（DataDict 模型，含 worker 补充的 `__init__`）
  - `backend/tests/test_data_dict.py`（元数据/构造断言）
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §5.4（工作树内）
- 计划：`docs/superpowers/plans/2026-08-14-risk-control-enhancement.md` 任务 1（工作树内，注意该文件在 master 上已更新测试约定，工作树内可能仍是旧版——以规格为准，测试约定以主仓库版本为准：无 db_session fixture，mock/元数据风格）

## 审查要点

1. 表结构与规格 §5.4 字段是否一致（dict_type/code/label/value JSONB/scope/enterprise_id/sort_order/enabled/is_system/description/时间戳/唯一约束 (dict_type, enterprise_id, code)）；
2. 种子数据是否覆盖规格要求的 measure_factors（4 类系数 + mode）、control_level_map（4 映射）、hazard_type（6 项），code/label/value 是否正确；
3. 模型映射是否与迁移一致（索引、可空、默认值、JSONB）；
4. 测试是否符合项目约定（无 db fixture、元数据/构造断言、无 async 标记需求）且覆盖规格关键行为；
5. **已知偏差评估**：worker 为 DataDict 添加了 `__init__`（`kwargs.setdefault("enabled", True)`，先例 `PlanSection`）——评估是否合理、是否影响 SQLAlchemy 默认行为，给出结论（接受/建议修改）。

## 输出格式

在最终回复中给出：

- 结论：✅ 符合规格（无必须修复项）或 ❌ 需修复（列问题）
- 问题清单，每条标注严重级：**必须修复 / 建议修改 / 仅供参考**，并给出文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_01_review_spec --claim-id <claim_id> --exit-code 0 --summary "规格审查完成"
```

## 规则

- 全程只读：不创建/修改/删除任何文件，不运行会改状态的命令（可运行 pytest 只读验证、git log/show/diff）；
- 任务池命令（认领/完成）在任务池目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 执行；代码审查在工作树目录进行。
