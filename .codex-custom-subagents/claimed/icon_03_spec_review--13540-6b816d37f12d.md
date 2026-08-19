# Codex Custom Subagents task handoff v1

Task: icon_03_spec_review

## 目标

审查任务 3（驾驶舱 ModuleNav 图标替换）实现是否与规格匹配——**不多不少**。独立阅读实际代码验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`85296ad`（父提交 `0b177df`）「feat(icon-system): replace cockpit module nav icons with AppIcon」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 修改 `frontend/src/components/enterprise/cockpit/ModuleNav.tsx`：
   - 顶部新增 `import AppIcon from "@/components/common/AppIcon";`；
   - 删除 `const stroke = {...}`；
   - 10 个内联 `<svg>` 全部替换为 `<AppIcon name="<name>" size={24} />`，映射：info→archive、org→org、geo→geo、chem→chem、risk→risk、hazard→hazard、rescue→rescue、assessment→assessment、investigation→investigation、plan→plan-manage；
   - label/en/to/hot/badge/onClick/onKeyDown 等其余结构不变。
2. 修改 `frontend/src/styles/cockpit.css:181`：`stroke: url(#cp-grad)` → `fill: url(#cp-grad); stroke: none`（其余属性不变；`cp-grad` 定义不动）。
3. 门禁：`npx tsc -b` exit 0；`npx eslint src/components/enterprise/cockpit/ModuleNav.tsx` exit 0；`npx vitest run` 130 passed；`npx playwright test e2e/enterprise-cockpit.spec.ts` 1 passed。
4. 提交契约：恰含 ModuleNav.tsx 与 cockpit.css；消息精确；`git show --check` 干净；无范围外文件。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：替换完成、CSS 适配、全部门禁通过、e2e 1 passed、截图目检 10 图标渐变正常（像素分析）、提交 85296ad 恰 2 文件、临时探针已清理。

## 审查方法

1. `git -C <worktree> show --stat 85296ad` 核对文件范围与消息；
2. 通读 `ModuleNav.tsx` 全文：确认 10 个 AppIcon name 映射精确、无残留内联 svg/`stroke` 常量、其余结构未动；
3. 核对 `cockpit.css:181` 精确改动、无其他 CSS 变更；
4. 独立运行：`npx tsc -b`、`npx eslint src/components/enterprise/cockpit/ModuleNav.tsx`、`npx vitest run`（在 frontend/ 下）；
5. 如有条件跑 e2e：`npx playwright test e2e/enterprise-cockpit.spec.ts`；
6. 检查有无规格外改动（如顺带改了 ModuleNav 其他逻辑）。

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

- 只读审查，不得修改任何文件；不得信任实现者报告。
