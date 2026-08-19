# Codex Custom Subagents task handoff v1

Task: icon_05_impl

## 目标

实现图标系统计划**任务 5**：法规库类型图标替换为 `AppIcon`（法律/标准/政策/主题 4 项）。前置：AppIcon 已可用（HEAD `31a5618`）。

## 工作目录

所有工作、git 操作在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

当前 HEAD 为 `31a5618`。前端命令在 `frontend/` 目录下运行。

## 任务描述（计划任务 5 全文）

**文件：**
- 修改：`frontend/src/components/regulation/RegulationList.tsx`

### 步骤 1：替换 TYPE_CONFIG 图标

`RegulationList.tsx` 顶部加 `import AppIcon from "@/components/common/AppIcon";`。TYPE_CONFIG（约 27-30 行，以实际为准）：

| 类型 | 原 icon | 新 icon |
|---|---|---|
| 法律 | `<AuditOutlined />` | `<AppIcon name="law" />` |
| 标准 | `<SafetyCertificateOutlined />` | `<AppIcon name="standard" />` |
| 政策 | `<FlagOutlined />` | `<AppIcon name="policy" />` |
| 主题 | `<BookOutlined />` | `<AppIcon name="topic" />` |

统计条（约 68 行「法规总数」的 `<BookOutlined />`）保持 AntD **不动**。import 中仅移除不再使用的 `AuditOutlined`、`FlagOutlined`；`BookOutlined` 因统计条仍用而保留；`SafetyCertificateOutlined` 若本文件其他地方无引用则移除（以 `npx eslint` unused 为准）。

### 步骤 2：类型与 lint

在 `frontend/` 运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint src/components/regulation/RegulationList.tsx`
预期：exit 0

### 步骤 3：测试回归

在 `frontend/` 运行：`npx vitest run`
预期：16 文件 / 130 测试全部通过

### 步骤 4：截图目检

打开法规库页面截图（可复用项目登录方式或临时 spec；如不便，说明原因）。确认 4 个类型图标在彩色标签/色块中正常渲染（TYPE_CONFIG 的 color 应仍生效于图标颜色），统计条图标未变。截图保存到临时目录并附路径。

### 步骤 5：Commit

```bash
git add frontend/src/components/regulation/RegulationList.tsx
git commit -m "feat(icon-system): replace regulation type icons with AppIcon"
```

## 约束

- 只改 `RegulationList.tsx`；不得改动其他文件；
- 不提交临时文件；提交信息精确；`git show --check` 干净；
- 若类型图标在彩色标签中颜色异常（如变黑/不可见），以 BLOCKED 上报附截图。

## 验证清单（提交前逐项确认）

1. `npx tsc -b` → exit 0
2. `npx eslint src/components/regulation/RegulationList.tsx` → exit 0
3. `npx vitest run` → 130 passed
4. `git show --stat HEAD` 恰含 RegulationList.tsx 一个文件
5. `git show --check HEAD` → 干净
6. 截图确认 4 个类型图标正常（附路径）

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 汇报格式

完成后汇报：
- **状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现了什么、验证清单逐项结果（含截图路径/现象）
- 提交 SHA 与文件清单
- 自审发现（如有）
- 任何问题或疑虑
