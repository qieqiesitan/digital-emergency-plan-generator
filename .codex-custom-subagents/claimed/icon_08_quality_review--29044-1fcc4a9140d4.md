# Codex Custom Subagents task handoff v1

Task: icon_08_quality_review

## 目标

你是资深代码审查员，审查任务 8（全量门禁与收尾）的实现质量（规格合规审查已通过，本审查聚焦收尾动作质量与批次整体卫生）。问题分级、具体、可执行。

## 实现内容（DESCRIPTION）

任务 8：全量门禁（tsc/vitest/e2e 通过；eslint 280 项既有债经基线确认）、残留检查（旧图标零残留、AppIcon 生产 45 处）、设计文档追加 §10 实现状态并提交 7797acc、codegraph sync + graphify update 执行。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 8）。要点：门禁全绿（eslint 既有债除外）、残留归零、设计文档实现状态提交、图谱同步尝试。

## 待审查的 Git 范围

- **Base：** `6436047`
- **Head：** `7797acc`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat 6436047..7797acc
git -C <worktree> diff 6436047..7797acc
```

## 检查内容

**收尾文档质量：** 设计文档 §10 内容是否准确反映实现事实（对照批次清单）；是否简洁、无冗余。

**门禁与收尾动作：** 实现者报告的验证结果是否可信（可抽查命令输出）；eslint 既有债的记录是否完整；残留检查口径是否准确（`<AppIcon` 计数方法、location 表单字段误匹配是否被正确排除——规格审查已发现该点）。

**批次整体卫生（本次收尾视角）：**
- 分支提交链是否清晰（docs → 8 个 feat/fix → 收尾）；
- 工作区卫生（TASKS.md 未提交属惯例）；
- 已知遗留清单是否完整：既有 eslint lint 债（约 280 项、涉及 RegulationList/RiskSourceForm/RichTextEditor/HazardousChemicalsTab 等）、codegraph worktree 索引未含新增文件、移动端 lucide 第二阶段、安全标志 backend/app/static/signs 未动。

**生产就绪：** 无回归迹象；批次是否达到可合并状态。

## 输出格式

### 优点
### 问题（Critical / Important / Minor，每项含 File:line、为什么重要、怎么修）
### 建议
### 评估（可以合并吗：[是|否|修完再合] + 理由）

## 约束

- 只读审查，不修改文件；问题具体到 file:line；不要把既有 lint 债算作本次引入。

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。
