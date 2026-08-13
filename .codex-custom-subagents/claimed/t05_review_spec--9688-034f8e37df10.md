# Codex Custom Subagents task handoff v1

Task: t05_review_spec

## 任务：规格合规审查 —— 任务 5（硬编码跳转核对）

你是一个规格合规审查子智能体。验证核对任务是否按要求完成（预期无代码改动）。**不要信任实现者的报告**，独立验证。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。本任务预期无提交，HEAD 应为 `b470cf1`（任务 4 提交）。

### 要求的内容（任务 5 规格）

1. 执行扫描：`rg -n 'location\.href = "|window\.location\.(href|replace|assign)\(|href="/' frontend/src --glob "*.tsx" --glob "*.ts"` 与 `rg -n 'settings/ai-config|location\.href|window\.location|navigate\(' frontend/src/components/plan/AIGenerateButton.tsx`；
2. 预期基线：仅 `frontend/src/routes/index.tsx:36` MobileRedirect 命中（保持不动）；AIGenerateButton 无硬编码跳转；
3. 无代码改动，不产生提交；工作区干净（TASKS.md 未提交改动属正常）。

### 实现者声称

两命令执行完毕：全仓仅命中 routes/index.tsx:36（MobileRedirect，判定不改）；AIGenerateButton 无命中；附加 `window.open`/`href` 兜底扫描亦无命中；未产生提交，工作区仅 TASKS.md 未提交。

### 你的工作

1. `git log --oneline -2` 确认 HEAD 仍为 b470cf1（无新增提交）；
2. 复跑上述两条 rg 命令，确认命中清单与实现者一致；
3. 通读 `frontend/src/components/plan/AIGenerateButton.tsx`，确认无 `location.href`/`window.location`/`navigate("/")` 类根路径硬编码；
4. 检查是否有未报告的遗漏扫描范围（如 `frontend/src/mobile` 内的原生跳转）。

### 汇报格式

- ✅ 符合规格（经独立验证）
- ❌ 发现问题：[具体列出，附带 file:line]
