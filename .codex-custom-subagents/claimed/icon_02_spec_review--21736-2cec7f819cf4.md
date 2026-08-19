# Codex Custom Subagents task handoff v1

Task: icon_02_spec_review

## 目标

审查任务 2（AppIcon 组件与 icons.tsx）实现是否与规格匹配——**不多不少**。独立阅读实际代码验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`0b177df`（父提交 `a2c09bd`）「feat(icon-system): add AppIcon component with 24 local svg icons」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 创建 `scripts/gen_icons_tsx.py`：
   - 读取 `frontend/src/assets/icons/*.svg`（24 个），输出 `frontend/src/components/common/icons.tsx`；
   - 生成 `AppIconName` 联合类型（24 个文件名，kebab-case）与 `ICONS: Record<AppIconName, { viewBox: string; body: ReactNode }>`；
   - SVG 属性转 JSX：`stroke-width→strokeWidth`、`stroke-linecap→strokeLinecap`、`stroke-linejoin→strokeLinejoin`、`xml:space→xmlSpace`；
   - 可复现：删除 icons.tsx 重跑产物一致；
   - 仅标准库。
2. 创建 `frontend/src/components/common/icons.tsx`：24 个图标；`AppIconName` 与资产文件名一致（archive/org/geo/chem/risk/hazard/rescue/assessment/investigation/plan-manage/dashboard/enterprise/plan-list/regulations/data-dict/prompt/ai/law/standard/policy/topic/safety/notice/location）。
3. 创建 `frontend/src/components/common/AppIcon.tsx`：
   - props：`name: AppIconName`、`size?: number`（默认 16）、`className?: string`、`style?: CSSProperties`；
   - 渲染 `<svg width={size} height={size} viewBox={icon.viewBox} fill="currentColor" aria-hidden="true" focusable="false">` + `{icon.body}`；
   - 未知名：DEV 下 `console.warn` 并返回 null。
4. 创建 `frontend/src/components/common/AppIcon.test.tsx`：3 用例（尺寸/viewBox/aria-hidden；className 转发；未知名 warn+空渲染）。
5. 验证：单测 3 PASS；全量 vitest 130 passed；`npx tsc -b` exit 0；eslint 3 文件 exit 0。
6. 提交契约：恰含 `scripts/gen_icons_tsx.py` + `frontend/src/components/common/`（icons.tsx、AppIcon.tsx、AppIcon.test.tsx）；消息精确；`git show --check` 干净；`frontend/src/assets/icons/` 24 个 SVG 未改动。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：TDD 红→绿；3/3 单测 PASS；全量 130 passed；tsc/eslint exit 0；提交 0b177df 恰 4 文件；生成脚本可复现（SHA-256 一致）；行尾统一；SVG 未改动。

## 审查方法

1. `git -C <worktree> show --stat 0b177df` 核对文件范围与消息；
2. 逐行阅读 `scripts/gen_icons_tsx.py`、`frontend/src/components/common/AppIcon.tsx`、`icons.tsx`、`AppIcon.test.tsx`，对照规格逐项核对；
3. 独立运行：`npx vitest run src/components/common/AppIcon.test.tsx`、`npx tsc -b`、`npx eslint src/components/common/AppIcon.tsx src/components/common/icons.tsx src/components/common/AppIcon.test.tsx`（在 frontend/ 下）；
4. 验证生成脚本可复现性（可选：复制资产到临时目录验证逻辑，不要删工作区文件）；
5. 检查 24 个 SVG 是否被改动（`git diff a2c09bd..0b177df --stat` 应无 assets 变更）；
6. 寻找多余内容：规格外参数/文件/功能。

## 汇报格式

- ✅ 符合规格（代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失/多余/偏差，附带 file:line 或命令证据]

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 约束

- 只读审查，不得修改任何文件（包括不得删除/覆盖工作区 icons.tsx 做复现验证，验证逻辑可用临时副本）；
- 不得信任实现者报告，一切以实际代码与命令输出为准。
