# Codex Custom Subagents task handoff v1

Task: task_b22_review_quality

## 任务：代码质量审查——task_b22_extract_classify（规格审查已通过）

你是一个代码质量审查子智能体。目的：验证实现是否构建良好。规格合规性已由前序审查通过，本任务只关注代码质量。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

BASE_SHA：83466ed；HEAD_SHA：7d16d41。

审查命令：cd 到 worktree 后运行 git diff 83466ed..7d16d41 并阅读实际代码。

### 实现内容

- onboarding_service.py 追加 MODULE_SCHEMA_HINTS / extract_candidates / classify_modules（模块级导入）
- 2 个测试（monkeypatch llm）
- 提交 7d16d41（2 文件）

### 审查重点

1. Prompt 设计是否合理（防注入/清晰/截断）？JSON 解析失败处理（_parse_ai_json 抛 500 是否合适）？
2. 模块 key 与完成度/前端计划一致性？
3. 测试是否真正验证行为（mock ai_config 的 coroutine 问题——评估是否影响测试有效性）？
4. 有无明显缺陷（异常处理、超时、文本截断边界）？
5. 代码风格与项目一致？

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复
