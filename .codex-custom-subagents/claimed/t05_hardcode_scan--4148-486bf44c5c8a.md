# Codex Custom Subagents task handoff v1

Task: t05_hardcode_scan

## 任务：部署可交付性计划任务 5 —— 硬编码跳转核对（预期无代码改动）

你是一个实现子智能体。本任务以核对为主，**预期不需要改代码**。严格按步骤执行并汇报，不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。

### 背景

子路径部署时，前端代码中任何「以 `/` 开头的原生跳转」（`location.href`、`window.location.replace/assign`、`<a href="/...">`）都会丢失子路径前缀导致 404。任务 1-4 已让 router 内部跳转与路径判断支持子路径；本任务扫描确认没有遗漏的原生根路径跳转。

### 步骤 1：全仓扫描

在 worktree 根目录执行：

```bash
rg -n 'location\.href = "|window\.location\.(href|replace|assign)\(|href="/' frontend/src --glob "*.tsx" --glob "*.ts"
rg -n 'settings/ai-config|location\.href|window\.location|navigate\(' frontend/src/components/plan/AIGenerateButton.tsx
```

### 步骤 2：核对判定

预期基线（2026-08-10 已核实）：仅 `frontend/src/routes/index.tsx:35` 的 `MobileRedirect`
（`window.location.replace(window.location.pathname + window.location.search)`）命中——它只是
把当前完整 pathname（含前缀）原样重放，不丢前缀，**保持不动**；`AIGenerateButton.tsx` 无任何
硬编码跳转。

逐一判定每个命中：
- router 内 `navigate()`/`<Link>`/`<Navigate>`：由 basename 自动处理，不改；
- `window.location.href = "/xxx"`、`window.location.replace("/xxx")`、`<a href="/xxx">` 等原生
  绝对路径跳转：需拼接 `APP_BASE`（import 自 `@/utils/platform`），改为
  `window.location.href = APP_BASE + "/xxx"` 等，并纳入提交。

### 步骤 3：结论记录与提交

- 若扫描结果与预期一致（只有 MobileRedirect）：不产生代码改动，直接汇报「无改动」；
- 若发现额外硬编码：按步骤 2 规则修复，运行 `cd frontend && npx tsc -b` 与
  `npx eslint <改动文件>` 验证，提交消息 `fix(deploy): prefix hardcoded jumps with APP_BASE`。

### 门禁

1. 扫描命令真实执行并附命中清单；
2. 每个命中都有明确判定（改/不改 + 理由）；
3. 若有改动：`npx tsc -b` 0、eslint 无新增 error、`git diff --check` 干净；
4. 若无改动：工作区保持干净，不产生空提交。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；扫描命令与命中清单；每个命中的判定；是否产生提交（无则说明）；验证结果；任何疑虑。
