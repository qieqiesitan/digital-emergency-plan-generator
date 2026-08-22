# Codex Custom Subagents task handoff v1

Task: review_quality_t4_v2

## 任务：代码质量复审 — 提示词缓存修复（commit d365334）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

复审上一轮 t4 质量审查的必须修复项（DB 重复模板行未生效 + risk_notice_card_ai.py:88 旧引用 + 应急模板 normalize）是否已由 commit `d365334` 修复到位。这是只读审查：不要修改任何源码。

### 上一轮必须修复项（逐条核对）

1. `prompt_cache.py` 加载确定性排序：active 优先、同状态 id 降序（`order_by(case((status == "active", 0), else_=1), id.desc())`）
2. `db_migration_prompt_templates_cleanup.sql`：幂等 UPDATE status='0' → 'disabled'（存在 active 同 code 时），无 DELETE
3. `risk_notice_card_ai.py:88`：GB 6441-1986 → GB 6441-2025
4. `risk_notice_card_service.py`：应急模板查表前 normalize（与 match_signs 对称）
5. 新增测试验证旧值「瓦斯爆炸」应急模板命中「可燃气体爆炸」模板

### 验证方式

- `git show d365334` 阅读 5 个文件改动
- 运行 `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -m pytest tests/test_risk_notice_card_service.py tests/test_risk_notice_card_data.py tests/test_prompt_templates_onsite_cards.py tests/test_generation_batch_refactor.py -q`（预期 61 passed）
- 确认提交只含 5 个文件
- 确认 prompt_cache 查询含 case + order_by（无 import 错误）

### 汇报格式

- 结论：✅ 通过 | ❌ 需修复（逐条列出，附 file:line）
- 5 项逐条核验结果 + 门禁结果
- task_id、claim_id、path（claim_task.py 输出）
