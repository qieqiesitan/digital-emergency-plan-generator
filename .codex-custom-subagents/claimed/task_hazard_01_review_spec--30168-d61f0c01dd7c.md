# Codex Custom Subagents task handoff v1

Task: task_hazard_01_review_spec

## 目标

对「隐患排查治理」计划任务 1 的实现做**只读规格合规审查**（对照 B 规格 §5 与任务 1 契约），输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`076e4f9`（父 `9ebfe48`）
- 文件：`backend/db_migration_hazard_management.sql`、`backend/app/models/hazard_management.py`、`backend/tests/test_hazard_models.py`
- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §5.1-5.10

## 审查要点

1. 迁移：10 表列/类型/FK/默认值与规格一致、幂等；企业配置列 + 部分唯一索引；B 字典种子 18 条码值/标签正确；系统模板 5 张 items 合规；
2. 模型：10 类映射一致、唯一约束命名、`__init__` setdefault；
3. 测试：21 断言有效；
4. 无越界改动：提交仅含上述 3 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_01_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患任务1规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
