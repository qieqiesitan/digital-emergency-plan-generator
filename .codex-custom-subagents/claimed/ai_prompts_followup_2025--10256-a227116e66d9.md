# Codex Custom Subagents task handoff v1

Task: ai_prompts_followup_2025

## 任务：补齐 AI 提示词两处遗留（:133 七维度指令 + seed_report_prompts 同步）

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；后端命令在 `backend` 子目录执行。Postgres 在 Docker 映射端口 5438，seed/测试需设置 `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5438/emergency_plan`。

### 背景

上一任务（ai_prompts_seed_2025）发现两处遗留，本任务补齐：

1. `backend/app/services/risk_assessment_service.py:133` 的「经营过程危险有害因素辨识分析」七维度指令仍含旧类型词（灼烧/机械伤害/车辆伤害/其他伤害/中毒和窒息）
2. `backend/seed_report_prompts.py` 从 risk_assessment_service 导入 SYSTEM_PROMPT 与 CHAPTER_DEFINITIONS，数据库里 `risk_assessment_system_default` 等行仍是旧文本（含 GB 6441-1986 与「淹溾」错字），需重跑 seed 同步

### 第 1 步：修改 `backend\app\services\risk_assessment_service.py`（仅 :133 一处）

将 :133 的（七）经营过程句：

`按火灾/爆炸、中毒和窒息、灼烧、触电、机械伤害、高处坠落、物体打击、车辆伤害、淹溺、其他伤害等事故类型`

替换为：

`按火灾/爆炸、中毒、窒息、灼烫、触电、机械致害、高处坠落、物体打击、厂（场）内车辆致害、淹溺、其他等事故类型`

（只替换这一句；同文件其他已更新处不动。）

### 第 2 步：重跑 seed 同步数据库

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5438/emergency_plan"
python seed_report_prompts.py
```

预期：输出 seed 完成统计（created/updated）。

### 第 3 步：验证数据库模板已更新

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT template_code, system_prompt LIKE '%GB 6441-2025%' AS has_new, system_prompt LIKE '%淹溾%' AS has_typo, user_prompt_template LIKE '%机械致害%' AS has_new_types FROM prompt_templates WHERE template_code IN ('risk_assessment_system_default','risk_assessment_section_hazard_identification','risk_assessment_section_factor_identification') OR category='risk_assessment_section' ORDER BY template_code;"
```

预期：`risk_assessment_system_default` 的 has_new=True、has_typo=False；含 7 维度指令的章节模板 has_new_types=True。

### 第 4 步：运行相关测试 + 提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_prompt_templates_onsite_cards.py tests/test_generation_batch_refactor.py -q
```

预期 PASS。提交：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/services/risk_assessment_service.py
git commit -m "fix(accident-types): update 7-dimension prompt wording and resync report seeds"
```

### 红线

- 只改 `backend/app/services/risk_assessment_service.py` 一个源码文件
- 不要更新 TASKS.md；中文保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 替换点、seed 输出、DB 验证结果、测试结果
- commit SHA（git log -1 --format=%h）
