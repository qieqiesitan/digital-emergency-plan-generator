# Codex Custom Subagents task handoff v1

Task: review_spec_t4_ai_prompts

## 任务：规格合规审查 — AI 提示词更新（commit aaf57af）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件：`.codex-custom-subagents\claimed\ai_prompts_seed_2025--8216-592da85d927e.md`

### 实现者声称构建了什么

- 17 处替换：risk_assessment_service.py 6 处（含淹溾→淹溺、15 类→27 类）、risk_ai_service.py 3 处、seed_prompts_full.py 3 行（8 处文本）
- 重跑 seed（1 new, 65 updated）；21 测试通过；commit aaf57af

### 关键：不要信任报告

必须独立验证：

- `git show aaf57af` 阅读实际改动，逐处与规格文件中的替换文本比对
- 验证 27 类全文与规格一致（关键：可燃液体蒸气爆炸、厂（场）内车辆致害）
- 全文件扫描确认无 `GB 6441-1986`、`淹溾` 残留：`rg -n "GB 6441-1986|淹溾" backend/app/services/risk_assessment_service.py backend/app/services/risk_ai_service.py backend/seed_prompts_full.py`
- 运行：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -m pytest tests/test_prompt_templates_onsite_cards.py tests/test_generation_batch_refactor.py -q`
- git show --stat 应恰 3 文件
- 确认 seed_prompts_full.py 的 :367/:432/:440 均已更新

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 替换点核对结果、残留扫描结果、门禁结果
- task_id、claim_id、path（claim_task.py 输出）
