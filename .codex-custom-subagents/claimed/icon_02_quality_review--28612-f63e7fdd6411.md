# Codex Custom Subagents task handoff v1

Task: icon_02_quality_review

## 目标

你是资深代码审查员，审查任务 2（AppIcon 组件与 icons.tsx）的实现质量（规格合规审查已通过，本审查聚焦代码质量）。问题分级、具体、可执行。

## 实现内容（DESCRIPTION）

任务 2：新增 `scripts/gen_icons_tsx.py`（62 行，从 24 个 SVG 生成 icons.tsx）、`frontend/src/components/common/icons.tsx`（AppIconName 联合 + ICONS 记录）、`frontend/src/components/common/AppIcon.tsx`（统一图标组件）、`AppIcon.test.tsx`（3 用例）。提交 0b177df。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 2）。核心要求：gen 脚本（标准库、ATTR_MAP 4 映射、可复现）；icons.tsx（24 图标、类型联合）；AppIcon（name/size=16/className/style；svg 属性；未知名 DEV warn+null）；测试 3 用例；tsc/eslint/vitest 门禁；提交契约。

## 待审查的 Git 范围

- **Base：** `a2c09bd`
- **Head：** `0b177df`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat a2c09bd..0b177df
git -C <worktree> diff a2c09bd..0b177df
```

## 检查内容

**计划对齐：** 实现匹配计划？偏差是否有道理？

**代码质量：** 关注点分离（gen 脚本 / icons / AppIcon 各司其职）；错误处理（无 SVG 资产、XML 解析失败、未知 name）；类型安全（AppIconName 联合、无 any）；DRY；边界情况（viewBox 缺失、空 body、属性值含引号——JSX 字符串引号转义是否正确）。

**架构：** 生成脚本职责单一、可复现；组件 API 设计（size/className/style）是否合理；与既有 `frontend/src/components/common/` 模式是否一致；24 图标内联 JSX 的打包体积与 tree-shake 影响（icons.tsx 单文件是否可接受，是否符合计划约定）。

**测试：** 3 用例是否验证真实渲染行为（renderToStaticMarkup）；未知 name 用 `as never` 的测试方式是否合理；是否值得补 viewBox 差异图标（如 plan-list 1025 宽）用例。

**生产就绪：** 文档（docstring）；无 bug；提交卫生；生成脚本可复现性已由规格审查验证，可复用其结论。

**额外检查：** 每个文件单一职责；文件大小是否合理（icons.tsx 单行密集是生成产物，是否符合计划预期）。

## 输出格式

### 优点
### 问题（Critical / Important / Minor，每项含 File:line、为什么重要、怎么修）
### 建议
### 评估（可以合并吗：[是|否|修完再合] + 理由）

## 约束

- 只读审查，不修改文件；不跑未经验证的结论；问题具体到 file:line。

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。
