# Codex Custom Subagents task handoff v1

Task: icon_06_spec_review

## 目标

审查任务 6（全站 AI 标识统一）实现是否与规格匹配——**不多不少**。独立阅读实际代码验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`d9e7bc4`（父提交 `543b0b8`）「feat(icon-system): unify AI icons with AppIcon ai」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 11 个文件、12 处 `RobotOutlined` 全部替换为 `<AppIcon name="ai" />`：
   - Chat/index.tsx 两处装饰：292 → `size={36}` 保留 `style={{ marginBottom: 12 }}`；438 → `size={48}` 保留 `style={{ marginBottom: 16, color: "#d9d9d9" }}`；
   - 其余 10 处按钮：`<AppIcon name="ai" />`（**授权偏差**：计划步骤 4 允许按钮场景补 `size={14}` 以对齐 AntD 按钮 1em@14px 槽位，实现者统一用了 `size={14}`，属计划内授权）；
   - 每个文件新增 `import AppIcon from "@/components/common/AppIcon";`；替换后移除不再使用的 `RobotOutlined` import。
2. 门禁：`npx tsc -b` exit 0；`npx vitest run` 130 passed；**已知偏差**：eslint 11 个文件 exit 1（15 项既有 lint 债，父版本同文件逐条一致，非本次引入——审查须独立验证）。
3. 提交契约：恰含 11 个文件；消息精确；`git show --check` 干净。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：12 处替换完成（10 处按钮 size=14、2 处装饰 36/48）、import 清理、rg 零残留、tsc/vitest 通过、eslint 因既有债失败（已对比父版本）、截图确认 48/36/14px、提交 d9e7bc4 恰 11 文件。

## 审查方法

1. `git -C <worktree> show --stat d9e7bc4` 核对范围与消息；
2. 逐文件核对：`rg "RobotOutlined" <11 文件>` 零残留；`rg "AppIcon name=\"ai\"" <11 文件>` 恰 12 处；Chat 两处 size/style 精确；其余 10 处 size={14}；import 正确且无重复；
3. 独立运行：`npx tsc -b`、`npx vitest run`（frontend/ 下）；
4. 独立验证 lint 债既有：`git show 543b0b8:<file> | npx eslint --stdin` 对比（至少抽查 3 个文件）；
5. 检查无规格外改动（11 文件 diff 应只有 RobotOutlined→AppIcon 与 import 行）。

## 汇报格式

- ✅ 符合规格（含授权偏差与既有 lint 债判定）
- ❌ 发现问题：[具体列出缺失/多余/偏差，附带 file:line 或命令证据]

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 约束

- 只读审查，不得修改任何文件；不得信任实现者报告。
