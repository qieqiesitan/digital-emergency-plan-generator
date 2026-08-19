# Codex Custom Subagents task handoff v1

Task: icon_04_impl

## 目标

实现图标系统计划**任务 4**：主导航 7 个业务菜单图标替换为 `AppIcon`（size 14），保留 5 个通用菜单入口的 AntD 图标。前置：AppIcon 已可用（HEAD `85296ad`）。

## 工作目录

所有工作、git 操作在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

当前 HEAD 为 `85296ad`。前端命令在 `frontend/` 目录下运行。

## 任务描述（计划任务 4 全文）

**文件：**
- 修改：`frontend/src/layouts/MainLayout.tsx`

### 步骤 1：替换 7 个业务菜单图标

`MainLayout.tsx` 顶部加 `import AppIcon from "@/components/common/AppIcon";`。以下菜单项 `icon` 替换（行号以当前文件为准，按 label 匹配）：

| 菜单项 | 原 icon | 新 icon |
|---|---|---|
| 工作台 | `<DashboardOutlined />` | `<AppIcon name="dashboard" size={14} />` |
| 企业管理 | `<BankOutlined />` | `<AppIcon name="enterprise" size={14} />` |
| 预案列表 | `<FileTextOutlined />` | `<AppIcon name="plan-list" size={14} />` |
| 法规库管理 | `<FileTextOutlined />` | `<AppIcon name="regulations" size={14} />` |
| 数据字典管理 | `<DatabaseOutlined />` | `<AppIcon name="data-dict" size={14} />` |
| 提示词管理 | `<EditOutlined />` | `<AppIcon name="prompt" size={14} />` |
| AI 配置 | `<KeyOutlined />` | `<AppIcon name="ai" size={14} />` |

替换后若某 AntD 图标在文件中不再使用，从 import 行移除（以 `npx eslint` 报 unused 为准逐个清理）。保留 AntD：用户管理（TeamOutlined）、角色管理（SafetyCertificateOutlined）、系统配置（SettingOutlined）、个人资料（UserOutlined）、退出登录（LogoutOutlined）以及头像下拉菜单中的同名入口——这些一律不动。

### 步骤 2：类型与 lint

在 `frontend/` 运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint src/layouts/MainLayout.tsx`
预期：exit 0

### 步骤 3：现有测试回归

在 `frontend/` 运行：`npx vitest run`
预期：16 文件 / 130 测试全部通过

### 步骤 4：截图目检

用 playwright 打开登录后首页/设置页截图（可复用项目 e2e 的 mock/登录方式；如 e2e 环境不便，可用临时 spec 或说明原因）。确认侧边菜单 7 个新图标渲染正常、尺寸 14px 与原有图标一致、无文字错位。截图保存到临时目录并在汇报中附路径。

### 步骤 5：Commit

```bash
git add frontend/src/layouts/MainLayout.tsx
git commit -m "feat(icon-system): replace main menu business icons with AppIcon"
```

## 约束

- 只改 `MainLayout.tsx`；不得改动其他文件；
- 不提交临时文件；提交信息精确；`git show --check` 干净；
- 若某菜单项渲染异常，以 BLOCKED 上报附截图。

## 验证清单（提交前逐项确认）

1. `npx tsc -b` → exit 0
2. `npx eslint src/layouts/MainLayout.tsx` → exit 0
3. `npx vitest run` → 130 passed
4. `git show --stat HEAD` 恰含 MainLayout.tsx 一个文件
5. `git show --check HEAD` → 干净
6. 截图确认 7 个新菜单图标正常（附路径）

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
