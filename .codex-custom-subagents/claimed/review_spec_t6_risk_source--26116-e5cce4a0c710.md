# Codex Custom Subagents task handoff v1

Task: review_spec_t6_risk_source

## 任务：规格合规审查 — NameError 修复 + normalize 兜底（commit a7171cd）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件：`.codex-custom-subagents\claimed\risk_source_fix_2025--27780-d7ab01de3780.md`

### 实现者声称构建了什么

- risk_sources_ext.py：import ACCIDENT_TYPES_2025，4 处 PRESET_RISK_CATEGORIES → ACCIDENT_TYPES_2025
- risk_source_migration_service.py：normalize_accident_type 包 suggested_event 与 RiskEvent 创建
- 新增 test_risk_sources_ext.py 回归测试（模板下载 200、含机械致害、不含锅炉爆炸）
- 测试通过；commit a7171cd

### 关键：不要信任报告

必须独立验证：

- `git show a7171cd` 阅读实际改动，逐处与规格比对
- 确认 4 处替换位置（:184/:310/:522/:684 附近）都已改且无遗漏
- 确认 normalize 两处实现与规格一致
- 运行：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -m pytest tests/test_risk_sources_ext.py -q`
- 确认全文件无 `PRESET_RISK_CATEGORIES` 残留：`rg -n "PRESET_RISK_CATEGORIES" backend/app/routers/risk_sources_ext.py`
- git show --stat 应恰 3 文件

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 4 处替换核对、normalize 核对、测试结果
- task_id、claim_id、path（claim_task.py 输出）
