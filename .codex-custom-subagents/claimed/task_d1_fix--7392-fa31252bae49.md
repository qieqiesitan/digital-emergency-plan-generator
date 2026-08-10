# Codex Custom Subagents task handoff v1

Task: task_d1_fix

## 任务：修复 D-1 移动端完成度卡片（质量审查 2 项重要 + 次要）

你是实现子智能体。上一轮 task_d1_mobile_completion 实现已通过规格审查（提交 812fa9f），但代码质量审查未通过。请修复以下问题并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。必须 cd 到该目录操作，不要动主工作区。

### 审查发现（必须修复）

**重要 1：完成度缓存无失效路径。** 桌面端 OnboardingPage 每步保存后都 `invalidateQueries(["completion", id])`，但移动端所有数据编辑保存点都没有 invalidate 该 key；且 mobile client `refetchOnWindowFocus=false`、staleTime 60s，用户去补数据→编辑→返回 Dashboard 后最长 60s 内仍显示旧完成度。

修法（择一并保持一致）：
- 在移动端所有会改变企业数据完成度的保存点补 `queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] })`。保存点至少包括：EnterpriseEditScreen（编辑企业信息）、EnterpriseCreateScreen（创建后，key 为新建企业 id）、RiskAssessmentScreen/RiskSourceListScreen（风险评估）、ResourceInvestigationScreen/ResourceListScreen（应急资源）、RiskManagementListScreen（如有保存/删除操作）、ResourceListScreen、EnterpriseListScreen 删除企业后（key 为被删 id，可随 enterprises invalidate 一并处理）。
- 若个别页面拿不到企业 id，可用 prefix 形式 `["completion"]` 全量失效。
- 完成后用 rg 核对：所有 mutate/保存成功回调里新增 completion invalidate 与既有 invalidate 并列；Dashboard 卡片自身不改 staleTime。

**重要 2：卡片绕过移动端组件库。** DashboardScreen 完成度卡片手写内联样式（#1677ff 进度/边框、#d9d9d9 槽、#fff7e6/#ffe7ba 标签、原生 button），混用 antd 桌面色与移动端 tokens（bg-primary-500），且卡片内两套蓝色。

修法：
- 进度条改用已有 `ProgressBar` 组件（frontend/src/mobile/components/ui/ProgressBar.tsx），标签改用 `Chip`，按钮改用 `Button`（含 loading/disabled 语义），颜色一律走移动端 CSS 变量 `var(--color-primary-*)`（优先 primary-600 主 CTA 惯例，与全 App 一致），禁止混入 #1677ff 等 antd 色。
- 若 ProgressBar/Chip 现有 API 不满足（如百分比文案），优先扩展现有组件，不要另写内联。
- 保持卡片功能与跳转逻辑不变（未完成→/m/enterprises/:id，完成→/m/plans/new?enterprise_id=）。

**次要（一并处理，成本低）：**
- 补 loading 态（Spinner/Skeleton）与 error 态（失败提示而非静默消失）。
- 切换企业时避免卡片闪现（enabled 控制已有时，确保 loading 期间不渲染旧企业数据即可，用 query 的 data 归属校验或 isLoading 兜底）。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint src/mobile/screens/DashboardScreen.tsx`（及所有改动文件）不得新增 error（既有错误需逐项说明与 BASE 对比）
3. `git diff --check` 干净
4. 改动文件不得引入 `any`（可用 unknown/具体类型）
5. 单提交、提交信息描述清晰（如 `fix(mobile): completion card cache invalidation and component consistency`），只含相关文件

### 提交

完成后 `git add` + `git commit`，然后用 `complete` 脚本标记完成并在报告里给出：
- 改动文件清单 + 提交 SHA
- 每项重要/次要问题的修法简述
- 门禁验证输出摘要

