# Codex Custom Subagents task handoff v1

Task: icon_03_impl

## 目标

实现图标系统计划**任务 3**：驾驶舱模块导航 10 项手绘图标替换为 `AppIcon`（iconfont 线性图标），并调整驾驶舱 CSS 保持渐变光效。前置：任务 2 已提交 AppIcon 组件（HEAD `0b177df`）。

## 工作目录

所有工作、git 操作在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

当前 HEAD 为 `0b177df`。前端命令在 `frontend/` 目录下运行。

## 任务描述（计划任务 3 全文）

**文件：**
- 修改：`frontend/src/components/enterprise/cockpit/ModuleNav.tsx`
- 修改：`frontend/src/styles/cockpit.css:181`

### 步骤 1：替换 ModuleNav 图标

`frontend/src/components/enterprise/cockpit/ModuleNav.tsx` 中：
1. 文件顶部加 `import AppIcon from "@/components/common/AppIcon";`（注意 `@/` 别名指向 `frontend/src`，与项目既有 import 风格一致）；
2. 删除 `const stroke = {...}` 定义；
3. 将 MODULES 中 10 个内联 `<svg>...</svg>` 整体替换为 `<AppIcon name="<name>" size={24} />`，映射（key → AppIcon name）：info→archive、org→org、geo→geo、chem→chem、risk→risk、hazard→hazard、rescue→rescue、assessment→assessment、investigation→investigation、plan→plan-manage；
4. 其余结构（label/en/to/hot/badge/onClick/onKeyDown）一律不动。

### 步骤 2：调整驾驶舱图标 CSS 保持渐变光效

`frontend/src/styles/cockpit.css:181` 由：

```css
.cp-nav svg { width: 26px; height: 26px; stroke: url(#cp-grad); filter: drop-shadow(0 0 5px rgba(0,212,255,.45)); }
```

改为：

```css
.cp-nav svg { width: 26px; height: 26px; fill: url(#cp-grad); stroke: none; filter: drop-shadow(0 0 5px rgba(0,212,255,.45)); }
```

（`cp-grad` 渐变定义在 `frontend/src/pages/Enterprise/EnterpriseCockpitPage.tsx:65`，不动。）

### 步骤 3：类型与 lint

在 `frontend/` 运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint src/components/enterprise/cockpit/ModuleNav.tsx`
预期：exit 0

### 步骤 4：现有测试回归

在 `frontend/` 运行：`npx vitest run`
预期：16 文件 / 130 测试全部通过

### 步骤 5：驾驶舱 e2e 与截图目检

在 `frontend/` 运行：`npx playwright test e2e/enterprise-cockpit.spec.ts`
预期：1 passed

截图目检：如 e2e 产物含驾驶舱截图则确认 10 个新图标以渐变描边光效正常渲染、大小无漂移；若 e2e 未截图，用 playwright 打开驾驶舱页面截图保存到 `frontend/e2e/screenshots/` 或临时目录并附路径。若环境无法完成截图，在汇报中说明并附 e2e 断言结果。

### 步骤 6：Commit

```bash
git add frontend/src/components/enterprise/cockpit/ModuleNav.tsx frontend/src/styles/cockpit.css
git commit -m "feat(icon-system): replace cockpit module nav icons with AppIcon"
```

## 约束

- 只改上述 2 个文件；不得改动其他源码/文档；
- 不提交临时文件；提交信息精确；`git show --check` 干净；
- 若替换后图标在 e2e/截图里明显异常（如不可见、变形），以 BLOCKED 上报并附截图路径与现象。

## 验证清单（提交前逐项确认）

1. `npx tsc -b` → exit 0
2. `npx eslint src/components/enterprise/cockpit/ModuleNav.tsx` → exit 0
3. `npx vitest run` → 130 passed
4. `npx playwright test e2e/enterprise-cockpit.spec.ts` → 1 passed
5. `git show --stat HEAD` 恰含 ModuleNav.tsx 与 cockpit.css 两个文件
6. `git show --check HEAD` → 干净

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
