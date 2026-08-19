# Codex Custom Subagents task handoff v1

Task: icon_06_impl

## 目标

实现图标系统计划**任务 6**：全站 AI 标识统一——12 处 `RobotOutlined` 替换为 `<AppIcon name="ai" />`（2 处装饰大图标带尺寸/样式）。前置：AppIcon 已可用（HEAD `543b0b8`）。

## 工作目录

所有工作、git 操作在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

当前 HEAD 为 `543b0b8`。前端命令在 `frontend/` 目录下运行。

## 任务描述（计划任务 6 全文）

**文件（修改，共 11 个）：**
- `frontend/src/pages/Chat/index.tsx:292,438`
- `frontend/src/pages/Hazard/HazardPlanPage.tsx:416`
- `frontend/src/components/plan/RichTextEditor.tsx:139`
- `frontend/src/pages/Hazard/HazardTemplatePage.tsx:328`
- `frontend/src/pages/Hazard/HazardRecordDetailPage.tsx:782,785`
- `frontend/src/components/plan/AIGenerateButton.tsx:157`
- `frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx:158`
- `frontend/src/components/enterprise/RiskEventForm.tsx:459,773`
- `frontend/src/components/enterprise/RiskSourceForm.tsx:119`
- `frontend/src/components/enterprise/EmergencyResourceForm.tsx:80`
- `frontend/src/components/enterprise/RiskMeasureForm.tsx:154`

### 步骤 1：逐文件替换

每个文件顶部加 `import AppIcon from "@/components/common/AppIcon";`（注意该文件可能已有 `@/components/common/...` 导入，合并去重）。将 `<RobotOutlined ... />` 替换为 `<AppIcon name="ai" ... />`，保留原有 props：

| 位置 | 原写法 | 新写法 |
|---|---|---|
| Chat/index.tsx:292 | `<RobotOutlined style={{ fontSize: 36, marginBottom: 12 }} />` | `<AppIcon name="ai" size={36} style={{ marginBottom: 12 }} />` |
| Chat/index.tsx:438 | `<RobotOutlined style={{ fontSize: 48, marginBottom: 16, color: "#d9d9d9" }} />` | `<AppIcon name="ai" size={48} style={{ marginBottom: 16, color: "#d9d9d9" }} />` |
| 其余 10 处按钮 | `<RobotOutlined />` | `<AppIcon name="ai" />` |

行号以当前文件实际为准，按 JSX 内容匹配。替换后若某文件不再使用 `RobotOutlined`，将其从 `@ant-design/icons` import 中移除（以 `npx eslint` unused 为准）。

### 步骤 2：类型与 lint

在 `frontend/` 运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint` 上述 11 个文件（逐行列全路径）
预期：exit 0

### 步骤 3：测试回归

在 `frontend/` 运行：`npx vitest run`
预期：16 文件 / 130 测试全部通过

### 步骤 4：截图目检

抽查预案编辑页（RichTextEditor AI 按钮）、预案 AI 生成按钮、隐患详情页 AI 按钮、聊天页大图标——确认按钮图标尺寸视觉一致（必要时给按钮场景补 `size={14}`），聊天页 36/48px 装饰图标正常。截图保存到临时目录并附路径；如个别页面不便打开，说明原因并至少覆盖 2 处。

### 步骤 5：Commit

```bash
git add <上述 11 个文件全路径>
git commit -m "feat(icon-system): unify AI icons with AppIcon ai"
```

## 约束

- 只改上述 11 个文件；不得改动其他文件；
- 不提交临时文件；提交信息精确；`git show --check` 干净；
- 若某处替换后按钮图标明显异常（尺寸/颜色/布局），以 BLOCKED 上报附截图。

## 验证清单（提交前逐项确认）

1. `npx tsc -b` → exit 0
2. `npx eslint` 11 个文件 → exit 0
3. `npx vitest run` → 130 passed
4. `git show --stat HEAD` 恰含 11 个文件
5. `git show --check HEAD` → 干净
6. 截图抽查 ≥2 处（附路径）

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
