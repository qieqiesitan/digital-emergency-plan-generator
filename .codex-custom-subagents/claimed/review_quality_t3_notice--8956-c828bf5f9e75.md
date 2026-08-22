# Codex Custom Subagents task handoff v1

Task: review_quality_t3_notice

## 任务：代码质量审查 — 风险告知卡 27 类升级（commit b3324a9）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现是否**构建良好**。规格合规审查已通过。这是只读审查：不要修改任何源码。

### 审查对象

- 提交：`b3324a9`（BASE 4c4334b）
- 文件：`backend/app/services/risk_notice_card_data.py`、`risk_notice_card_service.py`、`backend/tests/test_risk_notice_card_data.py`、`test_risk_notice_card_service.py`
- 规格：`.codex-custom-subagents\claimed\notice_cards_2025--17092-10ff174fa1df.md`

### 审查关注点

- SIGN_GROUPS/EMERGENCY_TEMPLATES 重建是否清晰可维护；11 个新键的标志组合与既有 36 个 SVG 资产是否匹配（可用脚本校验 svg 存在）
- match_signs 的 normalize 兼容是否最小侵入（去重/排序/限量逻辑未被破坏）
- 测试是否验证真实行为；旧键测试替换是否完整
- 是否遵循仓库模式；是否有过度构建
- 常量/注释是否准确（如「锅炉爆炸」旧注释是否残留）

### 汇报格式

- 优点（列出）
- 问题（按 关键/重要/次要 分级，附 file:line）
- 评估结论：✅ 通过 | ❌ 需修复（列出必须修复项）
- task_id、claim_id、path（claim_task.py 输出）
