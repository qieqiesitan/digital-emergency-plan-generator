# Codex Custom Subagents task handoff v1

Task: icon_08_spec_review

## 目标

审查任务 8（全量门禁与收尾）实现是否与规格匹配——**不多不少**。独立验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`7797acc`（父提交 `6436047`）「docs(icon-system): mark design spec as implemented」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 全量门禁：`npx tsc -b` exit 0；`npx vitest run` 130 passed；`npx playwright test e2e/enterprise-cockpit.spec.ts` 1 passed；`npx eslint src` 结果为既有债（259 errors/21 warnings，经基线对比确认非本次引入——审查须独立抽查验证）。
2. 残留检查：`rg "RobotOutlined|EnvironmentOutlined|NotificationOutlined" frontend/src` 零命中；`<AppIcon` 生产代码恰 45 处。
3. 设计文档 `docs/superpowers/specs/2026-08-16-icon-system-design.md` 末尾追加 §10「实现状态」（内容符合实现事实：AppIcon+24 SVG、ModuleNav 10、菜单 7、法规 4、AI 14、位置/通知/安全 10、保留 AntD、遗留 lint 债、移动端第二阶段）。
4. 提交契约：恰含设计文档一个文件；消息精确；`git show --check` 干净。
5. 图谱同步：codegraph sync 与 graphify update 已执行（结果以命令输出为准，审查可抽查日志/状态，不强制重跑）。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：门禁全绿（eslint 为既有债 280 项经基线对比）、残留归零、AppIcon 45 处、设计文档 §10 已提交 7797acc、codegraph/graphify 成功。

## 审查方法

1. `git -C <worktree> show --stat 7797acc` 核对范围与消息；
2. 阅读设计文档 §10 内容与实现事实对照；
3. 独立运行：`npx tsc -b`、`npx vitest run`、`npx playwright test e2e/enterprise-cockpit.spec.ts`（frontend/ 下）；
4. 残留检查：`rg` 三条命令 + `<AppIcon` 计数；
5. eslint 既有债抽查：从父版本 `git show 6436047:<file>` 对至少 3 个文件跑 `npx eslint --stdin` 对比错误集；
6. 检查提交无范围外改动。

## 汇报格式

- ✅ 符合规格（含既有 lint 债判定）
- ❌ 发现问题：[具体列出缺失/多余/偏差，附带 file:line 或命令证据]

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 约束

- 只读审查，不得修改任何文件；不得信任实现者报告。
