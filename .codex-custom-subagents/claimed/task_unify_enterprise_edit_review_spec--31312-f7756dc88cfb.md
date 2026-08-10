# Codex Custom Subagents task handoff v1

Task: task_unify_enterprise_edit_review_spec

## 任务：规格合规审查——task_unify_enterprise_edit

你是代码审查子智能体。请核验「统一引导页第 1 步与编辑企业页（方案 A）」实现是否符合设计。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD ca66d22）。

审查命令：`git log 154d90d..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 设计核验（对照任务 task_unify_enterprise_edit）

1. **EnterpriseInfoWorkspace.tsx**：完成度条（completion percent + enterprise_info 模块 ✓/待补充，失败降级）、EnterpriseInfoCards（onSaved 保存后停留 + invalidate + message）、GIS/平面图 Card（上传/预览/清除/选点/gisCleared/floorPlanCleared 迁移）、GIS 合并进 onSaved payload 一次提交（无独立保存按钮）、📄 导入现有数据（ImportDrawer single + CandidatesReview + acceptImport 迁移）、onDone 条件渲染。
2. **StepEnterprise.tsx**：变薄为标题/描述/错误态 + Workspace 透传（imported/onAddImported/onRemoveImported/onDone）；引导页资料包分流链路保持。
3. **EnterpriseEditPage.tsx**：仅 PageHeader + Workspace；保存后停留不 navigate；GIS 清除语义保留。
4. 不破坏 EnterpriseCreatePage。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error
- `git diff --check` 干净；diff 无 any

### 汇报格式

```
结论：PASS / FAIL（✅ 符合设计 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

