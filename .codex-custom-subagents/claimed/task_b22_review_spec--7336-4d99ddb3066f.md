# Codex Custom Subagents task handoff v1

Task: task_b22_review_spec

## 任务：规格合规审查——task_b22_extract_classify

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `7d16d41`：

git show 7d16d41 --stat 与 git show 7d16d41

### 要求的内容（任务 B2-2 原文摘要）

1. onboarding_service.py 追加 MODULE_SCHEMA_HINTS（5 个模块）、extract_candidates(module, text, db)（按模块 schema 提取，LLM JSON 解析，未配置 AI 抛 ValueError）、classify_modules(text, db)（模块识别，只返回已知 key）。
2. 测试 2 个（extract 解析 JSON、classify 解析 JSON，monkeypatch llm）。
3. Commit：feat(onboarding): LLM extraction and module classification for imports。
4. 只改 2 个文件；保留现有 compute_completion。

### 实现者声称构建了什么

- 模块级导入（无循环依赖）+ 末尾追加两函数
- 2 测试通过；全量与基线一致零新增失败（26 个基线环境失败）
- 提交 7d16d41（2 文件）

### 你的工作

阅读实际代码验证：两函数实现与要求一致（prompt 结构、12000 截断、严格 JSON、未配置报错）？模块 key 与完成度权重一致（无 reports——报告为系统生成非导入目标）？测试真实验证行为（monkeypatch llm）？只改 2 个文件、compute_completion 保留？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
