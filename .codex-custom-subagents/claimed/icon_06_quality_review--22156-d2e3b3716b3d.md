# Codex Custom Subagents task handoff v1

Task: icon_06_quality_review

## 目标

你是资深代码审查员，审查任务 6（全站 AI 标识统一）的实现质量（规格合规审查已通过，本审查聚焦代码质量）。问题分级、具体、可执行。

## 实现内容（DESCRIPTION）

任务 6：11 个文件、14 处 `RobotOutlined` 替换为 `<AppIcon name="ai" />`（Chat 两处装饰 size=36/48 保留 style；其余 12 处按钮 size=14），import 清理。提交 d9e7bc4（35+/25-）。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 6）。要点：AI 语义场景全量替换；按钮 size=14 为授权偏差（对齐 AntD 按钮 1em@14px）；装饰图标保留原尺寸/样式；import 清理；门禁 tsc/vitest 必过（eslint 该批文件存在**既有 lint 债**，已确认非本次引入，不要作为本次问题上报）。

## 待审查的 Git 范围

- **Base：** `543b0b8`
- **Head：** `d9e7bc4`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat 543b0b8..d9e7bc4
git -C <worktree> diff 543b0b8..d9e7bc4
```

## 检查内容

**计划对齐：** 14 处替换（含计划修正后计数）、无顺手改动。

**代码质量 / 视觉细节：**
- 按钮场景 `size={14}` 与 AntD Button icon 槽位（1em@14px）的一致性；装饰图标 36/48 与 style 保留；
- 11 个文件 import 是否干净（AppIcon 不重复、RobotOutlined 零残留）；
- 有无可抽公共 AI 按钮组件的必要性评估（注意 YAGNI——12 处按钮内联 AppIcon 是否可接受）。

**测试：** 现有 vitest 覆盖；纯替换场景是否值得补测试（注意 YAGNI）。

**生产就绪：** 提交卫生；无回归；既有 lint 债是否值得记录为收尾项。

**额外检查：** 各文件无膨胀、职责未变。

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
