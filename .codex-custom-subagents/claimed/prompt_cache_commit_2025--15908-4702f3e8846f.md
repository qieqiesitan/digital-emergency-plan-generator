# Codex Custom Subagents task handoff v1

Task: prompt_cache_commit_2025

## 任务：完成 prompt_cache 修复的 DB 下线验证与提交

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；Postgres 在 Docker 端口 5438。

### 背景

上一 worker 已完成 5 个文件的代码修改但未提交，并在 DB 迁移步骤因本地库唯一索引 `ix_prompt_templates_template_code` 与堆数据不一致（`=` 走索引查不到重复行）而 BLOCKED。代码改动仍在工作区未提交，需要你完成最后两步。

### 第 1 步：确认代码改动在磁盘上

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git status --short
git diff --stat
```

预期可见 5 个文件未提交改动：
- `backend/app/services/prompt_cache.py`（order_by active 优先 + id 降序）
- `backend/app/services/risk_notice_card_ai.py`（GB 6441-2025）
- `backend/app/services/risk_notice_card_service.py`（应急模板查表 normalize）
- `backend/db_migration_prompt_templates_cleanup.sql`（新增，status='0' → 'disabled' 幂等）
- `backend/tests/test_risk_notice_card_service.py`（新增测试）

若 prompt_cache.py 或 risk_notice_card_service.py 改动缺失（被其他并行任务覆盖），按任务背景重建：prompt_cache 查询加 `.order_by(case((PromptTemplate.status == "active", 0), else_=1), PromptTemplate.id.desc())`；risk_notice_card_service 应急模板查表前 `normalize_accident_type(at)`。

### 第 2 步：强制 seq scan 执行迁移

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
$sql = "SET enable_indexscan=off; SET enable_bitmapscan=off;`n" + (Get-Content -Raw backend\db_migration_prompt_templates_cleanup.sql)
$sql | docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1
```

验证：

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT id, template_code, status FROM prompt_templates WHERE template_code = 'risk_assessment_section_ch1_hazard_id' ORDER BY id;"
```

预期：id 173 status='disabled'、id 200 status='active'。若仍 UPDATE 0，把两条 SQL 合并到单个 `-c` 参数里重试（如 `docker exec emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 -c "SET enable_indexscan=off; SET enable_bitmapscan=off; UPDATE prompt_templates old SET status='disabled' WHERE old.status='0' AND EXISTS (SELECT 1 FROM prompt_templates act WHERE act.template_code = old.template_code AND act.status='active');"`）。

### 第 3 步：复跑测试 + 提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_risk_notice_card_service.py tests/test_risk_notice_card_data.py tests/test_prompt_templates_onsite_cards.py tests/test_generation_batch_refactor.py -q
```

预期 PASS（61 passed）。提交：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/services/prompt_cache.py backend/app/services/risk_notice_card_ai.py backend/app/services/risk_notice_card_service.py backend/db_migration_prompt_templates_cleanup.sql backend/tests/test_risk_notice_card_service.py
git commit -m "fix(accident-types): deterministic prompt cache ordering, retire legacy template rows"
```

### 红线

- 只提交上述 5 个文件（若第 1 步发现其他并行任务的改动，精确 git add 目标文件，不得 add -A）
- 禁止 DELETE/TRUNCATE；迁移只做 UPDATE status 下线
- 不要更新 TASKS.md；中文保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 代码改动确认结果、DB 下线验证（id 173/200 状态）、测试结果、commit SHA
- 索引损坏问题是否仍存在（记录即可，不擅自修库）
