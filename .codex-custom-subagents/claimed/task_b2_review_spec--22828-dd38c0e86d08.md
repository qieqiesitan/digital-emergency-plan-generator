# Codex Custom Subagents task handoff v1

Task: task_b2_review_spec

## 任务：规格合规审查——task_b2_chemical_link（含补充修复 bb5b489）

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `2463ab8` 与 `bb5b489`：

git show 2463ab8 --stat、git show bb5b489 --stat，并阅读实际代码。

### 要求的内容（任务 B2 原文摘要）

1. 迁移 SQL db_migration_risk_event_chemical.sql（chemical_id 可空 + SET NULL + 索引）。
2. 模型 RiskEvent.chemical_id（UUID FK → hazardous_chemicals, SET NULL, index）。
3. schema RiskEventCreate/RiskEventUpdate 增加 chemical_id。
4. 路由 create/update event 透传 chemical_id。
5. risk_context_builder._risk_source_item 输出 chemical_id。
6. generation.py _collect_enterprise_data：增加 chemicals 参数 + chemicals 列表 + risk_sources[].chemical（无关联 None）+ risk_method_config + last_plan_filing_date/authority；所有调用点（含 diagrams.py / external.py 补充修复）传参。
7. 新测试 test_risk_event_chemical.py 3 个。
8. Commit：feat(risk): link risk events to hazardous chemicals and inject into generation context（+ 补充修复 commit）。

### 实现者声称构建了什么

- 2463ab8：迁移/模型/schema/路由/上下文注入 + 2 个测试文件同步（test_batch_context/test_plan_diagram_service，签名演进影响面）
- bb5b489：diagrams.py / external.py 调用点补传 chemicals
- 全量 254 passed，无新增失败
- 自审说明：测试文件同步属签名演进的直接影响面，合理

### 你的工作

阅读实际代码并验证：

缺失的需求：所有要求是否实现？所有 _collect_enterprise_data 调用点（含 diagrams/external）是否都传 chemicals？
多余的工作：测试文件同步是否确为签名演进必需（若不改是否会失败）？
理解偏差：chemical_id 全链路命名/行为一致？chemical 注入字段正确（命中/未命中/None）？

通过阅读代码来验证，而非信任报告。

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
