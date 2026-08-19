# Codex Custom Subagents task handoff v1

Task: icon_04_quality_review

## 目标

你是资深代码审查员，审查任务 4（主导航业务菜单图标替换）的实现质量（规格合规审查已通过，本审查聚焦代码质量）。问题分级、具体、可执行。

## 实现内容（DESCRIPTION）

任务 4：`frontend/src/layouts/MainLayout.tsx` 中 7 个业务菜单图标替换为 `<AppIcon name="..." size={14} />`，清理 5 个不再使用的 AntD import（保留 KeyOutlined 因头像下拉仍用），5 个通用入口与头像下拉保持 AntD。提交 31a5618（8+/12-，单文件）。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 4）。要求：7 项精确替换（size=14）、import 清理、保留项不动、门禁全绿。

## 待审查的 Git 范围

- **Base：** `85296ad`
- **Head：** `31a5618`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat 85296ad..31a5618
git -C <worktree> diff 85296ad..31a5618
```

## 检查内容

**计划对齐：** 替换精确、无顺手改动。

**代码质量 / 视觉细节：**
- AntD Menu 的 icon 槽位渲染 AppIcon（14px）与 AntD 图标 14px 的视觉一致性（菜单项对齐/行高）；
- 替换后菜单配置可读性与维护性；
- import 清理是否干净且未误删。

**测试：** 现有 vitest 覆盖；评估是否值得补菜单渲染测试（注意 YAGNI，纯图标替换通常由截图/e2e 兜底）。

**生产就绪：** 提交卫生；无回归迹象。

**额外检查：** 文件无膨胀、职责未变。

## 输出格式

### 优点
### 问题（Critical / Important / Minor，每项含 File:line、为什么重要、怎么修）
### 建议
### 评估（可以合并吗：[是|否|修完再合] + 理由）

## 约束

- 只读审查，不修改文件；问题具体到 file:line。

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。
