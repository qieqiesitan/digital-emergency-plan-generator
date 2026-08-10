# Codex Custom Subagents task handoff v1

Task: task_b1_review_spec

## 任务：规格合规审查——task_b1_ai_config_system（含补充修复 40bf552）

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `5f14ec8` 与 `40bf552`（B1 补充修复）：

git show 5f14ec8 --stat、git show 40bf552 --stat，并阅读实际代码。

### 要求的内容（任务 B1 原文摘要）

1. 迁移 SQL db_migration_ai_config_system.sql（user_id DROP NOT NULL + is_system 列）。
2. 模型 AIConfig：user_id 可空（移除 unique）、新增 is_system。
3. 新服务 ai_config_service.get_system_ai_config（user_id IS NULL + is_system + is_active）。
4. risk_ai_service._get_ai_config 改系统级，未配置 400「系统未配置 AI 模型，请联系管理员」。
5. ai_config.py 路由 GET/PUT/DELETE 系统级 + require_admin。
6. 调用点切换（generation/chat/chat_dispatch/external/hazardous_chemicals/regulations/resources_ext + 补充修复的 resource_investigation/risk_assessment/risk_sources_ext/surrounding_ai）：无 `AIConfig.user_id ==` 残留。
7. 新测试 test_ai_config_system.py 3 个（返回 None、过滤 user_id IS NULL、_get_ai_config 400）。
8. Commit：refactor(ai): consolidate AI config to system-level singleton（+ 补充修复 commit）。

### 实现者声称构建了什么

- 13 文件 +118/-64（5f14ec8）+ 4 文件（40bf552），全量测试与基线一致无回归
- 自审发现并修复：原计划清单外的 4 个文件用户级查询（resource_investigation/risk_assessment/risk_sources_ext/surrounding_ai）已补充切换
- 测试适配说明：AsyncMock 改同步 MagicMock（真实 Result.scalar_one_or_none 是同步方法）

### 你的工作

阅读实际代码并验证：

缺失的需求：是否所有要求都实现？9+4 个文件是否全部切换？
多余的工作：是否构建了未被要求的内容？
理解偏差：模型迁移是否正确（user_id nullable、is_system）？路由权限是否正确？测试适配是否合理（断言与要求一致）？
完整性：全库是否还有生成/聊天/导入路径的 `AIConfig.user_id ==` 查询残留？（可 rg 验证）

通过阅读代码来验证，而非信任报告。

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
