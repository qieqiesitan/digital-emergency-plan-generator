# Codex Custom Subagents task handoff v1

Task: task_b23_review_spec

## 任务：规格合规审查——task_b23_org_gen

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `f204355`：

git show f204355 --stat 与 git show f204355

### 要求的内容（任务 B2-3 原文摘要）

1. onboarding_service.py 追加 generate_org_candidates(enterprise_info, db)：根据企业概况生成应急组织框架（指挥部+小组），prompt 强制姓名/电话/职位留空，严格 JSON，防御解析（groups or [] + dict 过滤），复用 _get_ai_config_or_400。
2. 测试 1 个（monkeypatch llm，断言 group_key 与 name 为空）。
3. Commit：feat(onboarding): AI generate emergency org structure candidates。
4. 只改 2 个文件。

### 实现者声称构建了什么

- generate_org_candidates（29 行）+ 1 测试，271 passed
- 提交 f204355（2 文件）
- 自审：姓名留空指令到位；防御解析与 B2-2 一致；环境发现（Playwright Chromium 缺失是 26 个失败的根因）

### 你的工作

阅读实际代码验证：函数实现与要求一致（prompt 结构、姓名/电话留空、JSON 示例、防御解析）？复用 helper 正确？测试真实验证（monkeypatch llm、断言 name 空）？只改 2 个文件？

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
