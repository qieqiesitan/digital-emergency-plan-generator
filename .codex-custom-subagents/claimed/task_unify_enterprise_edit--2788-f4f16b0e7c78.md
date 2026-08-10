# Codex Custom Subagents task handoff v1

Task: task_unify_enterprise_edit

## 任务：统一引导页第 1 步与编辑企业页（抽公共组件 EnterpriseInfoWorkspace）

你是实现子智能体。用户反馈「引导页企业信息」和「企业管理信息编辑页」是两张皮，已确认方案 A：抽公共组件，两处共用同一套交互，编辑页补齐导入/完成度，保存后停留。请实现并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 154d90d）。直接在主工作区修改提交。

### 设计

**新建 `frontend/src/components/enterprise/EnterpriseInfoWorkspace.tsx`**（公共企业信息工作台）：

```tsx
interface Props {
  enterpriseId: string;
  onDone?: () => void;   // 引导页「标记完成，下一步」按钮；编辑页不传则不渲染
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}
```

组件内部（参考 StepEnterprise 与 EnterpriseEditPage 现有实现迁移）：
1. `useQuery(["enterprise", enterpriseId], getEnterprise)` + `useQuery(["completion", enterpriseId], getEnterpriseCompletion)`；
2. **完成度条**：顶部一行「📊 数据完成度 xx%」+ antd Progress（percent 取 completion.percent；同时显示「企业信息」模块 done 状态 ✓/待补充，从 completion.modules 找 key==="enterprise_info"）；
3. **EnterpriseInfoCards**（enterprise、onSaved：updateEnterprise(enterpriseId, payload) + invalidate ["enterprise",id]/["completion",id] + message.success，**不跳转**）——保存按钮同时带上 GIS 字段（见下）；
4. **GIS 定位与平面图 Card**（迁移 EnterpriseEditPage 的完整逻辑：existingGis/gisCleared/floorPlanCleared/上传/预览/清除/地图选点；GIS 值保存在组件 state，**合并进 EnterpriseInfoCards 的 onSaved payload**（onSaved 回调里 `updateEnterprise({...values, gis_lat, gis_lng, floor_plan_url})`），这样一处「保存」同时提交基本信息和 GIS，不再需要独立「保存 GIS 信息」按钮）；
5. **📄 导入现有数据**：右上角按钮 → ImportDrawer mode="single" module="enterprise_info" → 候选经 onAddImported 交给页面（引导页）或本地 state（编辑页无页面级 imported 时用本地 state 承载）→ CandidatesReview 展示，acceptImport 迁移 StepEnterprise 现有实现（patch + updateEnterprise + onRemoveImported + refreshAll）；
6. **onDone 按钮**：props.onDone 存在时底部显示「标记完成，下一步」（type="primary"），调用 onDone；不存在则不渲染（编辑页没有下一步）。

**改 `frontend/src/pages/Onboarding/StepEnterprise.tsx`**（变薄）：
- 移除内部 EnterpriseInfoCards/GIS Card/ImportDrawer/候选核对/手动填写抽屉实现；
- 顶部保留「企业信息」标题 + 描述 + ✍️ 手动填写/📄 导入按钮？——导入按钮移入 Workspace 后，StepEnterprise 仅保留标题/描述/错误态，主体换成 `<EnterpriseInfoWorkspace enterpriseId={enterpriseId} onDone={onDone} imported={imported} onAddImported={onAddImported} onRemoveImported={onRemoveImported} />`；
- 保留 isError（企业不存在/已删除）分支与 onPrev；
- 注意：引导页侧边栏的「标记完成」走 onDone；Workspace 内 onDone 按钮同样触发。

**改 `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx`**（变薄）：
- 移除 EnterpriseInfoCards + GIS Card + mutation 保存逻辑；
- 保留 PageHeader「编辑企业」+ 返回；
- 主体换成 `<EnterpriseInfoWorkspace enterpriseId={id} />`（不传 onDone/imported）；
- 保存行为：保存后**停留**（Workspace 内部处理 message+invalidate，不再 navigate 回详情页）。

### 约束与注意

- 不改变 EnterpriseCreatePage（仍用 EnterpriseInfoCards + 自己的 GIS Card）；
- 保持引导页资料包分流（importedByStep）链路：StepEnterprise 透传的 imported/onAddImported/onRemoveImported 由 Workspace 消费；
- 编辑页 GIS「清除」语义保留（清空后提交 null）；
- 完成度查询失败时进度条降级为不显示（不阻塞页面）；
- 不引入新依赖；风格沿用现有 antd/tailwind 惯例。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 HEAD 154d90d 逐项对比）
3. `git diff --check` 干净；改动文件不得新增 `any`；新增代码无 >100 字符行
4. 按组件/页面拆 1-3 个逻辑提交均可（信息清晰），只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、实现要点（Workspace 结构、GIS 合并提交、导入候选迁移）、门禁验证输出摘要。

