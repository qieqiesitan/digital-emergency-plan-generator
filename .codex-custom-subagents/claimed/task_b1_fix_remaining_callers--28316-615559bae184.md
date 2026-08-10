# Codex Custom Subagents task handoff v1

Task: task_b1_fix_remaining_callers

## 任务：切换剩余 4 个文件的 AI 配置调用点到系统级（B1 补充修复）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 5f14ec8。启动时 `cd` 到该目录，git status 确认干净。

### 背景

B1（AI 配置全局化）已把 9 个文件切到系统级配置，但全库仍有 4 个文件使用用户级配置查询（`AIConfig.user_id == ...`），会导致这些端点在系统配置下查不到而 400：

- backend/app/routers/resource_investigation.py（约 256 行）
- backend/app/routers/risk_assessment.py（约 391 行）
- backend/app/routers/risk_sources_ext.py（约 445/619 行）
- backend/app/routers/surrounding_ai.py（约 188/272 行）

### 步骤 1：替换为用户级 → 系统级

逐一读这 4 个文件，将所有形如：

```python
ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id, AIConfig.is_active == True))).scalar_one_or_none()
```

或等价写法（含 user_id == user_id / current_user.id 的 AIConfig 查询）替换为：

```python
from app.services.ai_config_service import get_system_ai_config
ai_config = await get_system_ai_config(db)
```

保持未配置时的错误语义（若原为 400「请先在系统设置中配置 AI 模型」可改为「系统未配置 AI 模型，请联系管理员」或保持原文案，按文件内一致性选择）。

清理不再使用的导入（AIConfig、select 若不再使用）。

### 步骤 2：全库残留检查

运行：

```
rg -n "AIConfig" backend/app/routers --glob "*.py"
```

确认除 ai_config.py（路由自身）外，不再有 `AIConfig.user_id ==` 的生成/聊天/导入相关查询残留（保留 ai_config.py 中系统级 upsert 的合理引用）。

### 步骤 3：全量后端测试

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（与 B1 基线一致；若个别环境失败，说明并对比基线）。

### 步骤 4：Commit

```bash
git add backend/app/routers/resource_investigation.py backend/app/routers/risk_assessment.py backend/app/routers/risk_sources_ext.py backend/app/routers/surrounding_ai.py
git commit -m "refactor(ai): switch remaining routers to system-level AI config"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 逐一读文件确认查询写法再替换
2. rg 残留检查
3. 全量测试
4. 提交
5. 自审：4 个文件全部切换？无用户级查询残留？无导入残留？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、rg 结果、测试结果、提交 SHA、自审发现
