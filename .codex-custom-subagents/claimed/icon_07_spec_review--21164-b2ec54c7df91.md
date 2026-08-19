# Codex Custom Subagents task handoff v1

Task: icon_07_spec_review

## 目标

审查任务 7（位置/通知/安全图标替换）实现是否与规格匹配——**不多不少**。独立阅读实际代码验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`459dff3`（父提交 `1b55674`）「feat(icon-system): replace location notice and safety icons with AppIcon」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 9 个文件、11 处替换：
   - 位置 `EnvironmentOutlined` → `<AppIcon name="location" />`：EnterpriseCreatePage:105、RiskZoneForm:129、FloorPlanPicker:99、RiskSourceForm:72+149、RiskObjectForm:180、EnterpriseInfoWorkspace:245、WorkbenchToolbar:30；
   - 通知 `NotificationOutlined` → `<AppIcon name="notice" />`：RiskManagementTab:367；
   - 安全 `SafetyOutlined` → `<AppIcon name="safety" />`：AuthLayout:30；
   - 尺寸规则：按钮/行内 14px（含 WorkbenchToolbar）、FloorPlanPicker 28px 保留红+阴影 style、AuthLayout 64px 保留 marginBottom；
   - 每文件新增 AppIcon import；不再使用的 AntD 图标 import 移除。
2. 门禁：`npx tsc -b` exit 0；`npx vitest run` 130 passed；**已知偏差**：eslint 9 个文件 3 项既有 lint 债（FloorPlanPicker:25 set-state-in-effect、RiskSourceForm:79 no-explicit-any、RiskSourceForm:131 未用变量），父版本同文件一致，非本次引入——审查须独立验证。
3. 提交契约：恰含 9 个文件；消息精确；`git show --check` 干净。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：11 处替换完成、import 清理、tsc/vitest 通过、eslint 3 项既有债（已 stash 对比父版本）、截图确认 64/28/14px 与颜色保留、提交 459dff3 恰 9 文件。

## 审查方法

1. `git -C <worktree> show --stat 459dff3` 核对范围与消息；
2. 逐文件核对：`rg "EnvironmentOutlined|NotificationOutlined" <9 文件>` 应零残留（或仅在仍使用处保留）；`rg "AppIcon name=\"location\"|name=\"notice\"|name=\"safety\""` 各点位；尺寸/样式精确（FloorPlanPicker 28+红+阴影、AuthLayout 64、其余 14）；
3. 独立运行：`npx tsc -b`、`npx vitest run`（frontend/ 下）；
4. 独立验证 lint 债既有（父版本对比，至少抽查 3 处）；
5. 检查无规格外改动。

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
