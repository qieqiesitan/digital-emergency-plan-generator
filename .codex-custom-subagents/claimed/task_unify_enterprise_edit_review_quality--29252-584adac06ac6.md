# Codex Custom Subagents task handoff v1

Task: task_unify_enterprise_edit_review_quality

## 任务：代码质量审查——task_unify_enterprise_edit（规格审查通过后）

你是代码质量审查子智能体。请审查公共组件重构的代码质量。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD ca66d22）。

审查命令：`git log 154d90d..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码（重点 EnterpriseInfoWorkspace.tsx）。

### 审查重点

1. **Workspace 状态管理**：enterprise/completion 两个查询（loading/error 处理、降级）、GIS state（gisPos/floorPlanUrl/gisCleared/floorPlanCleared 组合语义）、保存成功后的 invalidate 与消息、无 navigate；
2. **导入候选**：onAddImported 页面级 vs localImported 本地承载的切换正确性、acceptImport 迁移完整性、_key 过滤/删除、来源标注；
3. **GIS 合并提交**：onSaved payload 组装（基本字段 + gis_lat/gis_lng/floor_plan_url）、清除语义（提交 null）、日期字段处理是否保留（DATE_FIELDS 由 EnterpriseInfoCards submit 处理）；
4. **回归**：引导页 importedByStep 链路、onDone 行为（标记完成+下一步）、编辑页保存后停留、EnterpriseCreatePage 未受影响；移动端不受影响；
5. 类型/样式：无 any、无 >100 字符行、无未使用导入/死代码（如 StepEnterprise/EditPage 残留导入）。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error（与基线逐项对比）
- `git diff --check` 干净；diff 无 any

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复

