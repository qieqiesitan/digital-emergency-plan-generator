# Codex Custom Subagents task handoff v1

Task: task_hazard_01

## 目标

实现「隐患排查治理」计划任务 1：迁移（11 张表 + 企业配置列 + B 字典种子 + 系统检查表模板种子）+ 模型，按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`9ebfe48`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 文件

- 创建：`backend/db_migration_hazard_management.sql`
- 创建：`backend/app/models/hazard_management.py`
- 测试：`backend/tests/test_hazard_models.py`

## 表定义（来自 B 规格 §5.1-5.10；所有表 id=UUID PK default gen_random_uuid()、created_at/updated_at=TIMESTAMPTZ default now()；`IF NOT EXISTS` 幂等）

1. **hazard_inspection_plans**：enterprise_id UUID NOT NULL FK enterprises CASCADE；name VARCHAR(255) NOT NULL；category VARCHAR(20) NOT NULL（daily/comprehensive/special/holiday）；frequency VARCHAR(20) NOT NULL（daily/weekly/monthly/custom）；weekdays JSONB NULL；zone_ids JSONB NOT NULL；template_id UUID NULL FK hazard_checklist_templates；responsible_user_id UUID NULL FK users；ai_suggestion JSONB NULL；enabled BOOLEAN default TRUE
2. **hazard_inspection_tasks**：plan_id UUID NOT NULL FK plans CASCADE；enterprise_id UUID NOT NULL FK enterprises CASCADE；title VARCHAR(255)；status VARCHAR(20) default pending；responsible_user_id UUID NULL FK users；due_at TIMESTAMPTZ NOT NULL；completed_at TIMESTAMPTZ NULL；overdue_notified_at TIMESTAMPTZ NULL
3. **hazard_inspection_items**：task_id UUID NOT NULL FK tasks CASCADE；object_id UUID NULL FK risk_objects；measure_id UUID NULL FK risk_measures；content TEXT NOT NULL；expected_note TEXT NULL；result VARCHAR(10) default pending；remark TEXT NULL；photo_urls JSONB NULL
4. **hazard_records**：enterprise_id UUID NOT NULL FK enterprises CASCADE；code VARCHAR(32) NOT NULL；source_type VARCHAR(20) NOT NULL；source_task_id/source_item_id UUID NULL；object_id UUID NULL FK risk_objects；measure_id UUID NULL FK risk_measures；title VARCHAR(255) NOT NULL；description TEXT NOT NULL；photo_urls JSONB NULL；location VARCHAR(500) NULL；hazard_type VARCHAR(20) NULL；cause_analysis TEXT NULL；level VARCHAR(10) NULL；level_source VARCHAR(10) NULL；grading_basis TEXT NULL；status VARCHAR(20) NOT NULL default registered；rectification_plan JSONB NULL；deadline DATE NULL；rectification_user_id UUID NULL FK users；reviewer_user_id UUID NULL FK users；created_by UUID NULL FK users；closed_at TIMESTAMPTZ NULL
5. **hazard_rectifications**：record_id UUID NOT NULL FK records CASCADE；user_id UUID NOT NULL FK users；content TEXT NOT NULL；evidence JSONB NULL；submitted_at TIMESTAMPTZ
6. **hazard_reviews**：record_id UUID NOT NULL FK records CASCADE；review_type VARCHAR(20) NOT NULL（first_review/second_review/close）；user_id UUID NOT NULL FK users；result VARCHAR(10) NOT NULL（pass/fail）；comment TEXT NULL；evidence JSONB NULL
7. **hazard_approvals**：record_id UUID NOT NULL FK records CASCADE；user_id UUID NOT NULL FK users；action VARCHAR(10) NOT NULL（approve/reject）；comment TEXT NULL
8. **hazard_audit_logs**：enterprise_id UUID NOT NULL FK enterprises CASCADE；record_id UUID NULL；user_id UUID NULL FK users；action VARCHAR(50) NOT NULL；detail JSONB NULL
9. **hazard_notifications**：enterprise_id UUID NOT NULL FK enterprises CASCADE；user_id UUID NOT NULL FK users；record_id UUID NULL；type VARCHAR(20) NOT NULL；message VARCHAR(500)；read_at TIMESTAMPTZ NULL
10. **hazard_checklist_templates**：enterprise_id UUID NULL FK enterprises CASCADE（NULL=系统默认）；name VARCHAR(255) NOT NULL；category VARCHAR(20) NOT NULL；items JSONB NOT NULL default '[]'；is_system BOOLEAN default FALSE
11. **enterprise_members** 已在组织计划落地——本任务不建。

**企业配置列**：`ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS hazard_closure_mode VARCHAR(20) NOT NULL DEFAULT 'standard'`、`hazard_public_token VARCHAR(64)`、`hazard_report_token VARCHAR(64)`、`hazard_config JSONB default '{}'`；部分唯一索引 `uq_enterprises_hazard_public_token`/`uq_enterprises_hazard_report_token`（WHERE NOT NULL）。

**B 字典种子**（data_dicts，ON CONFLICT DO NOTHING）：deadline_rules（major→{days:15}、general→{days:7}、review→{days:3}）、publicity_scope（ongoing/closed/all）、source_type（inspection 排查/report 上报/regulatory 监管检查/accident 事故/manual 手工）、record_status_label（registered 已登记/grading 待分级/pending_approval 待审批/rectifying 整改中/reviewing 复查中/second_review 二次复核/closed 已销号）。

**系统检查表模板种子**（hazard_checklist_templates，enterprise_id NULL、is_system TRUE）：日常检查表、综合检查表、专项-消防、专项-危化品、节假日检查表（items 各含 3-5 条 `{content, expected_note}`）。

## 模型

`hazard_management.py`：11 个类（上述 10 表 + 不含 enterprise_members），UUID 字符串主键、显式 FK、JSONB、`enabled`/`is_system`/`status` 构造默认（`__init__` setdefault，PlanSection 先例）、唯一约束命名（code 企业内唯一：`UniqueConstraint("enterprise_id","code", name="uq_hazard_records_ent_code")`）。

## 步骤（TDD）

- [ ] **步骤 1：失败测试**（`backend/tests/test_hazard_models.py`）：10 个类的表名/关键列子集断言 + 构造断言（status/result/level 默认值、photo_urls/rectification_plan 默认 []/{} 或 None 按实现）
- [ ] **步骤 2：确认失败 → 步骤 3：迁移 + 模型 → 步骤 4：通过 + `python -m pytest tests/ -q` 无回归 + 迁移本地幂等复跑两遍**
- [ ] **步骤 5：Commit**

```bash
git add backend/db_migration_hazard_management.sql backend/app/models/hazard_management.py backend/tests/test_hazard_models.py
git commit -m "feat(hazard): migration and models for hazard management"
```

不要提交 TASKS.md；消息精确匹配；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_01 --claim-id <claim_id> --exit-code 0 --summary "隐患迁移+模型完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、迁移验证、自审结论。

## 规则

- 严格 TDD；用 `apply_patch` 编辑；只改列出的 3 个文件；阻塞时停下汇报。
