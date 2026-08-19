# Codex Custom Subagents task handoff v1

Task: icon_05_spec_review

## 目标

审查任务 5（法规库类型图标替换）实现是否与规格匹配——**不多不少**。独立阅读实际代码验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`8802b46`（父提交 `31a5618`）「feat(icon-system): replace regulation type icons with AppIcon」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 修改 `frontend/src/components/regulation/RegulationList.tsx`：
   - 顶部新增 `import AppIcon from "@/components/common/AppIcon";`；
   - TYPE_CONFIG 4 项替换：法律→`<AppIcon name="law" />`、标准→`<AppIcon name="standard" />`、政策→`<AppIcon name="policy" />`、主题→`<AppIcon name="topic" />`（其余字段 label/color 不动）；
   - 统计条「法规总数」的 `<BookOutlined />`（约 line 68）保持 AntD 不动；
   - import 仅移除不再使用的 `AuditOutlined`、`SafetyCertificateOutlined`、`FlagOutlined`；`BookOutlined` 保留（统计条仍用）。
2. 门禁：`npx tsc -b` exit 0；`npx vitest run` 130 passed。**已知偏差**：`npx eslint src/components/regulation/RegulationList.tsx` 预期 exit 1——该文件在父提交即存在 5 项既有 lint 债（line 1 `@ts-nocheck`、未使用 Statistic/Tooltip/ClearOutlined/updateRegulation），非本次引入；规格审查须独立验证这一判断（对比父提交同文件 lint）。
3. 提交契约：恰含 RegulationList.tsx 一个文件；消息精确；`git show --check` 干净。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：4 项替换、import 清理、统计条未动、tsc/vitest 通过、eslint 因既有债失败（已对比父提交确认非本次引入）、截图确认 4 色图标正常渲染、提交 8802b46 恰 1 文件。

## 审查方法

1. `git -C <worktree> show --stat 8802b46` 核对范围与消息；
2. 通读 diff：4 处替换 name 精确、color/label 未动、统计条 BookOutlined 未动、import 清理正确；
3. 独立运行：`npx tsc -b`、`npx vitest run`（frontend/ 下）；
4. 独立验证 lint 债为既有：`git show 31a5618:frontend/src/components/regulation/RegulationList.tsx` 提取父版本到临时文件 lint（或用等价方式），确认错误集与当前版本一致（仅行号偏移）；
5. 检查无规格外改动。

## 汇报格式

- ✅ 符合规格（代码检查后一切匹配；lint 债确认既有即视为符合规格的已知偏差）
- ❌ 发现问题：[具体列出缺失/多余/偏差，附带 file:line 或命令证据]

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 约束

- 只读审查，不得修改任何文件；不得信任实现者报告。
