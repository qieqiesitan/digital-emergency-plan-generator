# Codex Custom Subagents task handoff v1

Task: final_review_accident_types

## 任务：最终整体审查 — 事故类型全链路对齐 GB 6441-2025 分支

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

对分支 `codex/accident-types-2025` 的**整体实现**做最终审查（覆盖 `a703301..HEAD` 全部 12 个实现提交），确认：规格全覆盖、无遗留缺陷、门禁全绿、可合并。这是只读审查：不要修改任何源码。

### 审查范围与依据

- 规格：`docs/superpowers/specs/2026-08-21-accident-types-design.md`（工作区主目录 `C:\Users\55061\Documents\数字化预案自动生成 2\docs\superpowers\specs\...` 或 worktree 内同路径）
- 计划：`docs/superpowers/plans/2026-08-21-accident-types.md`
- 提交链：8682923 → c9713d5 → cba91ea → 4c41a86 → 4c4334b → 79080f8 → b3324a9 → a7171cd → aaf57af → cd99674 → adcdeea → d365334

### 审查清单

1. **规格覆盖**：设计文档 §4（27 类）、§5（映射）、§6（共享模块）、§7（消费点）、§8（迁移）、§9（测试）、§10（风险）、§11（验证）逐项对照实现，确认无遗漏
2. **一致性**：前后端 27 类清单逐项一致；映射表一致；无旧标准引用残留（排除映射表/测试/历史对照文档）
3. **门禁复跑**：
   - `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -m pytest -q`（预期 1042 passed, 1 skipped）
   - `cd ...\frontend && npx tsc -b && npx vitest run`（预期 exit 0、141 passed）
4. **提交卫生**：12 个提交逐个 `git show --stat` 检查文件范围与消息；工作树干净
5. **风险点确认**：迁移幂等（可重跑）；seed 已同步（DB risk_assessment_system 为新文本）；自由值保留；告知卡 27 类键全集
6. **已知遗留**（记录即可，不要求本次修复）：DB `ix_prompt_templates_template_code` 索引与堆不一致（既有问题）；`seed_prompts_full.json` 旧导出；`test_risk_notice_card_data.py:55/:62` docstring 旧词

### 汇报格式

- 结论：✅ 可合并 | ❌ 需修复（逐条列出）
- 规格覆盖逐项结果、一致性核对、门禁结果、提交卫生、风险点确认
- 已知遗留清单
- task_id、claim_id、path（claim_task.py 输出）
