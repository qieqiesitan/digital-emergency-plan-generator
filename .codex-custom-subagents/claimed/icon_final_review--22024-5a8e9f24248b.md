# Codex Custom Subagents task handoff v1

Task: icon_final_review

## 目标

对图标系统优化整个分支做**最终整体审查**：对照设计规格逐项核验整批实现，独立跑关键门禁，给出合并建议。不要信任各任务报告，以实际代码与命令为准。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
范围：`99120f5..HEAD`（HEAD 当前为 `7797acc`，共 34 个提交）
设计规格：`docs/superpowers/specs/2026-08-16-icon-system-design.md`（含 §4.3 映射表、§5 AppIcon 接口、§6 迁移批次）
实现计划：`docs/superpowers/plans/2026-08-16-icon-system.md`
前端命令在 `frontend/` 目录下运行。

## 审查清单

### 1. 规格覆盖度（§1-§10 逐节）
- §2 决策：线性统一、方案 1 双轨、通用 AntD 保留、SVG 本地化——是否落地；
- §4 资产层：24 个 SVG 命名与映射表一致（含 ai.svg 复用）、清洗规则（无 class/style/硬编码色）；
- §5 AppIcon：接口（name/size=16/className/style）、渲染属性（fill=currentColor、aria-hidden）、未知名 DEV warn；
- §6 迁移批次：ModuleNav 10、MainLayout 7、法规类型 4、AI 14、位置/通知/安全 10——逐项核对；
- §7 验证：AppIcon 单测 3 条、门禁、e2e；
- §9 后续：移动端 lucide 第二阶段（本批未做，属计划内延后）。

### 2. 提交链与卫生
- `git log --oneline 99120f5..HEAD` 全链核对（docs → feat 逐批 → fix → 收尾）；
- 抽查 3 个代表性提交 `git show --check`；
- 工作区卫生（仅 TASKS.md 未提交属惯例）。

### 3. 关键门禁（独立重跑）
- `npx tsc -b` → exit 0
- `npx vitest run` → 130 passed
- `npx playwright test e2e/enterprise-cockpit.spec.ts` → 1 passed
- `npx eslint src` → 既有债（280 项），确认零新增（对比基线 6436047 或抽查）
- `rg "RobotOutlined|EnvironmentOutlined|NotificationOutlined" frontend/src` → 零命中
- `<AppIcon` 生产代码恰 45 处

### 4. 已知遗留核验（如实列出）
- 既有 eslint lint 债（78 文件/280 项，非本次引入）；
- codegraph worktree 索引不含新增文件（索引属主工作区）；
- 移动端 lucide 统一（第二阶段）；
- backend/app/static/signs 未动（设计范围外）。

## 输出格式

### 总体结论
### 规格覆盖（逐节 ✅/❌）
### 提交链与卫生
### 门禁结果（独立运行证据）
### 问题（Critical / Important / Minor）
### 合并建议（可以合并 / 修完再合 / 不可以，附理由）

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 约束

- 只读审查，不修改任何文件（含不修改 TASKS.md 之外的文件）；不得信任任务报告。
