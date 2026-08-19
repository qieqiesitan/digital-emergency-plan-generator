# Codex Custom Subagents task handoff v1

Task: task_hazard_13

## 目标

实现隐患管理任务 13「HazardInspectionTab + hazardService + 类型 + 路由 + Tab 接入」并提交。注意：后端缺 `GET /records`（列表）与 `GET /records/{rid}`（详情）端点（任务 5 只做了登记），本任务需先补后端补丁供前端消费。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`eb846dc`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**后端补丁（2 个 commit 中的第 1 个，若端点确认缺失）**

- `backend/app/routers/hazard_management.py` 追加：
  - `GET /records`：列表，支持筛选 status/level/source_type/scope=overdue（rectifying 且 deadline<today）/关键词 q（title/description/code ilike）；按 created_at 倒序；返回列表 + 可选统计（total/open/major/overdue，报告返回结构）；读=归属 404；字典中文标签（status/source_type/level）。
  - `GET /records/{rid}`：详情，含记录全部业务字段 + object/measure 名称 + rectifications（最近/全部，报告取舍）+ reviews + approvals + audit_logs（时间线数据）+ status/source_type/level 中文标签；读=归属 404。
- `backend/tests/test_hazard_record_api.py` 追加对应测试（筛选/统计/详情时间线/404/标签）。
- commit：`git commit -m "feat(hazard): record list and detail endpoints"`（仅后端 2 文件；若已存在则跳过并说明）。

**前端（第 2 个 commit，按契约）**

- 新建 `frontend/src/types/hazard.ts`：HazardRecord/HazardRecordDetail/HazardRectification/HazardReview/HazardApproval/HazardAuditLog/HazardInspectionPlan/HazardInspectionTask/HazardInspectionItem/HazardChecklistTemplate/HazardNotification 等类型（字段与后端 schema/端点响应一致，参考任务 3-11 后端实现）。
- 新建 `frontend/src/services/hazardService.ts`：封装后端端点（records 列表/详情/创建/grade/approve/reject/rectify/review/close、plans CRUD、tasks 列表/详情/提交/to-record、templates CRUD/copy、publicity 列表/token、dashboard、ai/*、导出链接），函数式 API 风格与 `riskManagementService.ts` 一致（api.get/post/put/delete + ApiResponse 解包）。
- 新建 `frontend/src/services/hazardService.test.ts`：对纯函数/URL 构造做 vitest 单测（项目惯例 service 测试覆盖）。
- 新建 `frontend/src/pages/Hazard/HazardInspectionTab.tsx`：台账页——统计条（未闭环/重大/超期/待确认等，来源 dashboard 或列表统计，报告来源）、筛选（状态/等级/来源/关键词）、新建隐患 Modal（复用 POST /records 字段：source_type/title/description/hazard_type/object_id/measure_id/location/photo_urls，AI 智能填写按钮调 /ai/record-assist 预填，报告实现）、导出按钮（/export/ledger.xlsx 链接）、各页入口（计划/任务/模板/驾驶舱/公示，路由占位或已注册路由，报告取舍）。
- `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`：接入 `HazardInspectionTab`（新 Tab key="hazard-inspection"，参考既有 Tab 分组样式）。
- 路由：`frontend/src/routes/index.tsx`（或 App.tsx）为后续页面注册路由占位（计划/任务/详情/模板/驾驶舱/公示/公开页——任务 14-16 逐个实现，本任务先注册 hazard 路由组或仅 Tab，报告取舍）。
- commit：`git commit -m "feat(hazard): inspection tab and hazard service"`。

**门禁（每批）**：`npx tsc -b` exit 0；eslint 改动文件 exit 0；`npx vitest run` 全绿（含新增 service 测试）；`git diff --check` 干净；后端全量 `python -m pytest tests/ -q` 无回归。

**参考文件**（自行阅读）

- 后端实现：`backend/app/routers/hazard_management.py`（全部端点与响应结构）、`backend/app/schemas/risk_management.py`（信封类型参考）。
- 前端先例：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`（Tab 页面结构）、`frontend/src/services/riskManagementService.ts`（service 风格）、`frontend/src/types/riskManagement.ts`（类型风格）、`frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`（Tab 接入点）、`frontend/src/routes/index.tsx`（路由）。
- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §14、§15（页面清单）。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_13 --claim-id <claim_id> --exit-code 0 --summary "隐患台账Tab+service实现完成"
```

最终回复报告：task_id、claim_id、commit SHA（两个）、改动文件清单、前后端门禁结果、设计决策说明（后端列表/详情结构/统计来源/新建表单/AI 预填/路由取舍）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
