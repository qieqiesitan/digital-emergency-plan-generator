# Codex Custom Subagents task handoff v1

Task: task_hazard_14

## 目标

实现隐患管理任务 14「HazardPlanPage + HazardTaskPage」并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`cfd2cbd`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：新建 `frontend/src/pages/Hazard/HazardPlanPage.tsx`、`frontend/src/pages/Hazard/HazardTaskPage.tsx`，修改 `frontend/src/routes/index.tsx`（把 plans/tasks 占位路由替换为真实页面），按需扩展 `frontend/src/services/hazardService.ts`/`frontend/src/types/hazard.ts`。

**1. HazardPlanPage（计划配置，规格 §6 + 任务 3/12 后端）**

- 计划列表：GET /plans（名称/类别/频次/责任人/启用状态/覆盖分区数）；启用开关切换（PUT）。
- 计划 CRUD：新建/编辑 Modal（name/category/frequency/weekdays（weekly/custom 时）/zone_ids（多选，数据源=分区列表——从风险分区端点取，报告来源）/responsible_user_id（从企业成员 available 端点取）/template_id（可选，从模板列表取）/enabled）；删除=软删（DELETE → enabled=false）。
- **AI 排程建议卡**：计划编辑时调 `/ai/schedule-suggestion`（plan_draft=表单草稿文本），展示 {suggested_frequency, suggested_responsible_user_id, reason}，「采纳」把建议回填表单；降级 available:false 时提示不阻塞。
- 权限处理：403/404 提示（message.error）。

**2. HazardTaskPage（任务执行，规格 §6 + 任务 3/8 后端）**

- 任务列表：GET /tasks（责任人/状态/超期筛选，due_at 排序）；**超期标红**（overdue 状态或 due_at<now 行样式/标签）。
- 任务详情/执行：GET /tasks/{id}（items 清单）→ 逐项核对 result（pending/normal/abnormal/na）+ remark + photo_urls；PUT /tasks/{id} 提交（部分核对→processing、全部→done 由后端判定）。
- **一键转隐患**：abnormal 项行内按钮 → POST /tasks/{id}/to-record（预填 title/description/photo_urls），成功提示并刷新；非 abnormal 项按钮禁用。
- 任务状态标签（pending/processing/done/overdue 中文）+ 到期时间展示。
- 权限处理：403/404 提示。

**3. 门禁**：`npx tsc -b` exit 0；eslint 改动文件 exit 0；`npx vitest run` 全绿（若扩展 service 补测试）；`git diff --check` 干净；后端全量 `python -m pytest tests/ -q` 无回归（本批不改后端，仅验证）。

**4. 参考文件**（自行阅读）

- 后端端点：`backend/app/routers/hazard_management.py`（plans/tasks/to-record/AI schedule-suggestion 契约与响应）。
- 前端先例：`frontend/src/pages/Hazard/HazardInspectionTab.tsx`（本批风格）、`frontend/src/pages/Enterprise/RiskControlListPage.tsx`（表格+Modal 惯例）、`frontend/src/services/enterpriseOrgService.ts`（members/available 端点）。
- 类型：`frontend/src/types/hazard.ts`（已含 Plan/Task/Item 类型）。
- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §6、§15。

## Commit

```bash
git add frontend/src/pages/Hazard/HazardPlanPage.tsx frontend/src/pages/Hazard/HazardTaskPage.tsx frontend/src/routes/index.tsx frontend/src/services/hazardService.ts frontend/src/types/hazard.ts
git commit -m "feat(hazard): plan and task execution pages"
```

按实际改动文件调整 add 列表；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_14 --claim-id <claim_id> --exit-code 0 --summary "隐患计划页+任务页实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、门禁结果、设计决策说明（分区/成员/模板数据源、AI 采纳、超期标红、转隐患交互）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
