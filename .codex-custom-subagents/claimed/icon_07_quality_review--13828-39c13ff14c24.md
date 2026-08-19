# Codex Custom Subagents task handoff v1

Task: icon_07_quality_review

## 目标

你是资深代码审查员，审查任务 7（位置/通知/安全图标替换）的实现质量（规格合规审查已通过，本审查聚焦代码质量）。问题分级、具体、可执行。

## 实现内容（DESCRIPTION）

任务 7：9 个文件、10 处替换（EnvironmentOutlined 8 处 → AppIcon location、NotificationOutlined 1 处 → notice、SafetyOutlined 1 处 → safety），尺寸 14/28/64 与样式保留，import 清理。提交 459dff3（24+/19-）。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 7）。要点：语义场景替换；按钮/行内 14px、平面图标记 28px 红+阴影、登录安全盾 64px；import 清理；门禁 tsc/vitest 必过（eslint 该批存在既有 lint 债，已确认非本次引入，不要作为本次问题上报）。

## 待审查的 Git 范围

- **Base：** `1b55674`
- **Head：** `459dff3`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat 1b55674..459dff3
git -C <worktree> diff 1b55674..459dff3
```

## 检查内容

**计划对齐：** 10 处替换、无顺手改动。

**代码质量 / 视觉细节：**
- 尺寸语义：按钮 14px、平面图标记 28px（保留 color/阴影）、登录盾 64px（保留 marginBottom）与上下文一致性；
- 行内标记（RiskSourceForm:72 红色小定位点）14px 是否合适；
- import 清理是否干净；
- **已知待查**：规格审查发现 RiskSourceForm:150 的 `icon=` 行缩进为 16 空格（父版本为 14）——请核实是否为本次引入的格式回归，如是列为 Minor 并给修复方式。

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
