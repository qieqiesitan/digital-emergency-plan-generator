# Codex Custom Subagents task handoff v1

Task: task_hazard_03

## 目标

实现隐患管理任务 3「排查计划/任务/清单项端点」并提交，为后续任务（4 模板、5 登记、8 调度器）打基础。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`16b3656`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：新建 `backend/app/services/hazard_service.py`、新建 `backend/app/routers/hazard_management.py`、新建 `backend/tests/test_hazard_plan_api.py`（路由文件注册方式参考既有路由：`backend/app/routers/enterprise_org.py` 的 router 注册模式，并确认 `backend/app/main.py` 或 `backend/app/routers/__init__.py` 挂载方式；若按现有惯例需在 `backend/app/main.py` include_router，请同步最小改动并在报告中说明）。

**1. 计划 CRUD**：前缀 `/enterprises/{enterprise_id}/hazard-inspection/plans`

- 字段按规格 §5.1：name（必填）、category（daily/comprehensive/special/holiday）、frequency（daily/weekly/monthly/custom）、weekdays（JSONB，weekly/custom 时必填）、zone_ids（JSONB 必填）、template_id（可选，关联 hazard_checklist_templates）、responsible_user_id（可选，默认责任人）、ai_suggestion（可选）、enabled（默认 true）。
- `zone_ids` 必须校验每个分区属于该企业（查风险点/区域模型确认企业归属链，规格 §6「按 zone_ids 查当前风险点 + 管控措施」；若区域概念在风险点表/楼层图模型上，用该模型的 enterprise 归属校验；校验失败返回 422 说明具体分区不属于企业）。
- `responsible_user_id` 必须校验为 `enterprise_members` 中 enabled 且绑定该企业用户的成员（参考 `enterprise_org_service.py` 既有查询与校验模式），失败 422。
- `template_id` 校验：系统模板（enterprise_id NULL）或本企业模板，否则 422。
- 写权限=企业主/企业管理员（参考 `enterprise_org.py` 的 `_get_owned_ent`/403 惯例，具体角色门控按项目既有模式）；读=企业归属校验（不属于 → 404）。
- 端点：POST 创建、GET 列表（支持 enabled 过滤、分页或全量按既有惯例）、GET /{plan_id} 详情、PUT /{plan_id} 更新（校验同上）、DELETE /{plan_id} 删除（软删/硬删按规格 §5.1 FK CASCADE 语义，选择后说明理由；若 FK 导致硬删级联删任务，需在报告中说明取舍）。
- 全部响应走项目 `ApiResponse` 信封（`code==0` + data）。

**2. 任务生成函数** `generate_tasks_for_plan(db, plan, on_date=None)`

- 放 `hazard_service.py`，纯服务层函数（任务 8 调度器会复用）。
- 按 frequency 生成 `hazard_inspection_tasks`：daily 每日；weekly/custom 按 weekdays（周一=0..周日=6 或按数据库约定，参照既有代码）；monthly 按当月 1 日或计划约定日（选一种并在 docstring 说明）；`due_at` 默认当日 18:00（企业本地时区，用 date 组装 datetime 即可，时区债务已有记录不阻塞）。
- 防重：同一 plan 同一天已有任务则跳过（返回已存在标记），供调度器防重。
- 组装 `hazard_inspection_items`：按 `zone_ids` 查当前风险点（`risk_objects`）+ 管控措施（`risk_measures`）生成动态项（content 用措施/风险点描述拼装，expected_note 可空）；若计划关联模板，追加模板 items（content/expected_note）；预留 AI 补全占位（本任务不调 LLM，注释标明任务 12 `ai/checklist` 补全入口）。
- title 如「{计划名} · MM-DD」；status=pending；responsible_user_id 取计划责任人。
- 返回生成的任务对象/列表，docstring 说明输入输出。

**3. 任务/清单项端点**：前缀 `/enterprises/{enterprise_id}/hazard-inspection/tasks`

- `GET /tasks`：列表，支持 `responsible_user_id`（仅本企业成员）/`status`/`overdue`（bool，超期未完成=due_at<now 且 status in pending/processing）过滤，按 due_at 排序。
- `GET /tasks/{task_id}`：详情（含 items 列表）。
- `PUT /tasks/{task_id}`：提交核对结果，body 传 items 核对数组（item_id + result: pending/normal/abnormal/na + remark + photo_urls）；校验 items 属于该任务、result 合法、责任人/可执行人提交（参考状态机身份校验风格：任务责任人本人或企业管理员，其余 403/422）；提交后更新 items 并写 completed_at、status=done（说明：存在 abnormal 时任务仍 done，隐患通过 to-record 转出；若部分核对则 status=processing）。
- `POST /tasks/{task_id}/to-record`：一键转隐患——必传 `item_id`（该任务下 result=abnormal 的项），创建 `hazard_record`（source_type=inspection、source_task_id/source_item_id 回填、object_id/measure_id 取 item、title 由 content 截断或 body 传 title、description 必填或默认 content + remark、photo_urls 取 item 照片），code 按 `HD-{三位序号}` 生成（查既有记录数+1 或现有同型逻辑，不复用）。
- 权限与归属：任务/计划/记录均先校验企业归属（不属于 → 404），写操作按项目角色惯例。

**4. 测试**（`backend/tests/test_hazard_plan_api.py`，mock db 风格与 `tests/test_enterprise_org.py` 一致）

- 项目测试约定：无 db fixture；服务/端点用 mock + `dependency_overrides`；async 测试必须 `@pytest.mark.asyncio`。
- 覆盖：计划创建（字段校验/zone_ids 归属/责任人校验/模板校验）、计划 CRUD 主路径、任务生成组装（频次/防重/items 来自风险点+措施+模板）、清单项提交（合法/非法 result/非责任人 403）、to-record 转隐患（预填字段/code 生成/source 回填）。
- 断言必须有效无空断言；提交前跑目标测试 + 全量回归。

**5. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §5.1-5.3、§6、§14、§16。
- 模型：`backend/app/models/hazard_management.py`（HazardInspectionPlan/Task/Item、HazardRecord）、`backend/app/models/enterprise_org.py`（EnterpriseMember）、风险点/措施模型（查 `backend/app/models/risk_management.py` 或等价文件确认类名与 enterprise 归属字段）。
- 迁移：`backend/db_migration_hazard_management.sql` L21-72。
- 惯例参考：`backend/app/routers/enterprise_org.py`、`backend/app/services/enterprise_org_service.py`、`backend/tests/test_enterprise_org.py`；`backend/app/routers/risk_management.py`（_get_ent/ApiResponse 信封）。

## 验证

- `python -m pytest tests/test_hazard_plan_api.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净；
- 若改动 `backend/app/main.py`（挂载路由），全量回归必须通过并说明。

## Commit

```bash
git add backend/app/services/hazard_service.py backend/app/routers/hazard_management.py backend/tests/test_hazard_plan_api.py
git commit -m "feat(hazard): plan, task and checklist item endpoints"
```

若确需挂载路由的最小改动（main.py/`__init__.py`），一并 add 并在报告中说明；不要提交 TASKS.md；commit 消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_03 --claim-id <claim_id> --exit-code 0 --summary "隐患计划/任务/清单项端点实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（防重/删除语义/状态流转/权限）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
