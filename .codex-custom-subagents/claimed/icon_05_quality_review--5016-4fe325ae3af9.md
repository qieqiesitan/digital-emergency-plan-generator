# Codex Custom Subagents task handoff v1

Task: icon_05_quality_review

## 目标

你是资深代码审查员，审查任务 5（法规库类型图标替换）的实现质量（规格合规审查已通过，本审查聚焦代码质量）。问题分级、具体、可执行。

## 实现内容（DESCRIPTION）

任务 5：`frontend/src/components/regulation/RegulationList.tsx` TYPE_CONFIG 4 项图标替换为 `<AppIcon name="law|standard|policy|topic" />`，import 清理（删 AuditOutlined/SafetyCertificateOutlined/FlagOutlined，保留 BookOutlined），统计条图标未动。提交 8802b46（5+/5-，单文件）。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 5）。要求：4 项精确替换、统计条保留、import 清理、门禁（tsc/vitest 必过；eslint 该文件因**既有 lint 债** exit 1，属已确认的已知偏差，非本次引入，不要将其作为本次问题上报）。

## 待审查的 Git 范围

- **Base：** `31a5618`
- **Head：** `8802b46`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat 31a5618..8802b46
git -C <worktree> diff 31a5618..8802b46
```

## 检查内容

**计划对齐：** 替换精确、无顺手改动。

**代码质量 / 视觉细节：**
- TYPE_CONFIG 中 AppIcon 未传 size（默认 16）在彩色标签块中的渲染一致性（与 AntD 图标 16px 对比）；
- `color` 字段对 AppIcon 的实际生效方式（fill: currentColor 继承色块颜色）——实现者截图确认四色正确，可独立判断；
- import 清理是否干净、可读性。

**测试：** 现有 vitest 覆盖；是否值得补法规列表渲染测试（注意 YAGNI，纯图标替换）。

**生产就绪：** 提交卫生；无回归迹象；既有 lint 债是否值得在本任务记录/单独立项（不要在本任务修）。

**额外检查：** 文件无膨胀、职责未变。

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
