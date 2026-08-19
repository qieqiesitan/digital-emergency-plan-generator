# Codex Custom Subagents task handoff v1

Task: task_hazard_01_fix

## 目标

按隐患任务 1 质量审查的 2 条低优先建议修复，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`076e4f9`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1：补 3 条迁移索引对齐模型 index=True**

`db_migration_hazard_management.sql` 追加（`IF NOT EXISTS`）：

```sql
CREATE INDEX IF NOT EXISTS idx_hazard_checklist_templates_enterprise ON hazard_checklist_templates(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_hazard_inspection_plans_template ON hazard_inspection_plans(template_id);
CREATE INDEX IF NOT EXISTS idx_hazard_rectifications_user ON hazard_rectifications(user_id);
```

（迁移文件相应位置或末尾追加均可，选清晰位置。）

**2：动作表 user_id 改 SET NULL（留痕语义）**

`db_migration_hazard_management.sql` 中 `hazard_rectifications.user_id`、`hazard_reviews.user_id`、`hazard_approvals.user_id`、`hazard_notifications.user_id` 的 FK 从 `ON DELETE CASCADE` 改为 `ON DELETE SET NULL`；模型对应 `ForeignKey(..., ondelete="SET NULL")` 与 `nullable=True` 同步（构造/查询兼容：这些字段变可空，任务 2 状态机按实际用户必填不变）。

注意：`hazard_notifications.user_id` 若改为可空，通知「接收人」语义仍要求必填——保留 NOT NULL 而用 SET NULL 会冲突；方案：`hazard_notifications.user_id` 保持 NOT NULL + CASCADE（通知属轻量临时数据，删用户清通知合理），仅 rectifications/reviews/approvals 三张留痕动作表改 SET NULL。按此执行并在报告中说明。

## 验证

- `python -m pytest tests/test_hazard_models.py -v` 全部 PASS（模型 FK 变更后断言同步）；`python -m pytest tests/ -q` 无回归；
- 迁移本地复跑两遍幂等；`git diff --check` 干净。

## Commit

```bash
git add backend/db_migration_hazard_management.sql backend/app/models/hazard_management.py backend/tests/test_hazard_models.py
git commit -m "fix(hazard): align fk indexes and preserve action audit trails"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_01_fix --claim-id <claim_id> --exit-code 0 --summary "隐患任务1索引+留痕修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明（含 notifications 取舍）。

## 规则

- 用 `apply_patch` 编辑；只改列出的 3 个文件；阻塞时停下汇报。
