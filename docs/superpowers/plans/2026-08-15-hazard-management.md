# 隐患排查治理模块 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现双重预防机制第二支柱「隐患排查治理」：排查计划/任务（计划×风险清单 + AI）、三渠道登记（Web/扫码公开/移动端复用 API）、AI 辅助分级与治理方案、挂牌督办、整改/复查/销号（标准/严格按企业配置）、超期预警与站内通知、状态回写联动、隐患公示（企业内+公开脱敏）、驾驶舱统计与台账/监管导出。

**架构：** 独立模块（router `/enterprises/{id}/hazard-inspection` + 11 张表）；状态机集中在 service 层（权限矩阵 + 标准/严格模式开关）；AI 全部文本通道复用 `llm_text_completion`，失败降级；公开上报/公示复用 token 模式；APScheduler 常驻任务生成与超期扫描（部署假设见 §13）。

**技术栈：** FastAPI + SQLAlchemy(async) + PostgreSQL、openpyxl、apscheduler（新增）、React 18 + Ant Design 5 + TanStack Query、Vitest、pytest。

**规格文档：** `docs/superpowers/specs/2026-08-14-hazard-management-design.md`（commit `422f202`）
**前置：** 本计划依赖 A 阶段（`data_dicts`/双等级/字典接口）与「企业组织与成员管理」计划（`enterprise_members` 选人）。

**测试约定（沿用项目现状）：** 无 db fixture；模型用元数据断言；服务/端点用 mock + `dependency_overrides`；async 测试必须 `@pytest.mark.asyncio`；前端 vitest 仅 service/utils；AI 用 `unittest.mock.patch` mock `llm_text_completion`。

---

## 文件结构

### 后端

| 文件 | 职责 |
|------|------|
| `backend/db_migration_hazard_management.sql` | 新建：9 张隐患业务表 + `enterprises.hazard_closure_mode/hazard_public_token/hazard_report_token/hazard_config` + B 字典类型种子 + 系统检查表模板种子 |
| `backend/app/models/hazard_management.py` | 新建：HazardInspectionPlan/Task/Item、HazardRecord、HazardRectification、HazardReview、HazardApproval、HazardAuditLog、HazardNotification、HazardChecklistTemplate |
| `backend/app/models/enterprise_org.py` | 修改：EnterpriseMember 增加 `display_name`（冗余姓名，选人显示用；迁移补列） |
| `backend/app/schemas/hazard_management.py` | 新建：计划/任务/清单项/隐患单/整改/复查/审批/通知/模板/驾驶舱/导出 schema |
| `backend/app/services/hazard_state_machine.py` | 新建：状态机（流转校验、权限矩阵、标准/严格模式、audit log 记录） |
| `backend/app/services/hazard_service.py` | 新建：任务生成、清单组装、派生回写、统计、公示 |
| `backend/app/services/hazard_ai_service.py` | 新建：AI 清单补全/排程/计划生成/检查表/治理方案/登记摘要/分级/向导（文本） |
| `backend/app/services/hazard_export_service.py` | 新建：台账/监管上报 xlsx |
| `backend/app/services/hazard_scheduler.py` | 新建：APScheduler（任务到期生成 + 超期扫描 + 到期前 2h 提醒） |
| `backend/app/routers/hazard_management.py` | 新建：鉴权端点 |
| `backend/app/routers/public_hazard.py` | 新建：扫码上报 `/public/hazard/report/{token}`、公示 `/public/hazard/{token}` |
| `backend/app/main.py` | 修改：注册路由 + 启动/关闭调度器 |
| `backend/requirements.txt` | 修改：加 `apscheduler` |
| `backend/tests/test_hazard_*.py` | 新建：按任务分文件 |

### 前端

| 文件 | 职责 |
|------|------|
| `frontend/src/types/hazard.ts` | 新建：类型 |
| `frontend/src/services/hazardService.ts` | 新建：API 封装（箭头函数 + 解包） |
| `frontend/src/services/hazardService.test.ts` | 新建 |
| `frontend/src/pages/Enterprise/HazardInspectionTab.tsx` | 新建：台账（统计条/筛选/新建/导出/入口） |
| `frontend/src/pages/Enterprise/HazardPlanPage.tsx` | 新建：计划配置（AI 排程） |
| `frontend/src/pages/Enterprise/HazardTaskPage.tsx` | 新建：任务执行（清单核对 + 一键转隐患） |
| `frontend/src/pages/Enterprise/HazardRecordDetailPage.tsx` | 新建：隐患单详情（状态机操作/治理方案/时间线） |
| `frontend/src/pages/Enterprise/HazardDashboardPage.tsx` | 新建：驾驶舱 |
| `frontend/src/pages/Enterprise/HazardTemplatePage.tsx` | 新建：检查表模板 |
| `frontend/src/pages/Enterprise/HazardPublicityPage.tsx` | 新建：企业内隐患公示（打印/公开链接） |
| `frontend/src/pages/PublicHazardReportPage.tsx` | 新建：扫码上报 `/h/report/:token` |
| `frontend/src/pages/PublicHazardPage.tsx` | 新建：公示公开页 `/h/:token` |
| `frontend/src/routes/index.tsx` | 修改：路由 |
| `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx` | 修改：新 Tab 入口 |

---

## 任务 1：迁移 + 11 表模型

**文件：** `backend/db_migration_hazard_management.sql`、`backend/app/models/hazard_management.py`、`backend/tests/test_hazard_models.py`

- [ ] 失败测试（元数据/构造断言：11 个类的表名/关键列/关系）
- [ ] 迁移（按规格 §5.1-5.10 精确列定义；`IF NOT EXISTS`；企业配置列 `hazard_closure_mode`（默认 standard）/`hazard_public_token`/`hazard_report_token`/`hazard_config`；B 字典类型种子 `deadline_rules/publicity_scope/source_type/record_status_label`；系统检查表模板种子 5 条）
- [ ] 模型：UUID 主键、显式 FK、JSONB（zone_ids/photo_urls/rectification_plan/evidence/items）、`enabled`/`is_system` 构造默认（PlanSection 先例）
- [ ] 通过 + `git commit -m "feat(hazard): migration and models for hazard management"`（本地库复跑幂等验证）

---

## 任务 2：状态机 service（核心）

**文件：** `backend/app/services/hazard_state_machine.py`、`backend/tests/test_hazard_state_machine.py`

- [ ] 失败测试：状态流转表驱动（全路径矩阵：一般/重大 × 标准/严格 × 通过/退回）、权限矩阵、非法流转 409、复查人=整改人 422、audit log 写入
- [ ] 实现：

```python
TRANSITIONS = {
    "registered": {"grade"},
    "grading": {"rectify", "pending_approval"},
    "pending_approval": {"rectify"},
    "rectifying": {"review"},
    "reviewing": {"close", "rectify"},          # pass→close / fail→退回
    "second_review": {"close", "rectify"},
}

def can_transition(record, action, actor_role, strict_mode: bool) -> tuple[bool, str]:
    # 权限矩阵：grade=enterprise_admin；approve=enterprise_admin；rectify=整改人本人或 admin；
    # review=复查人≠整改人 且 actor 为指定复查人/admin；close=enterprise_admin（严格模式+重大 需先 second_review）
    ...

async def apply_transition(db, record, action, actor, payload, enterprise) -> HazardRecord:
    # 校验 → 流转 → 写 audit log（hazard_audit_logs）→ 更新 record（含 closed_at）
```

- [ ] 纯函数与 mock 端点测试全过 + `git commit -m "feat(hazard): state machine with permission matrix and audit log"`

---

## 任务 3：排查计划/任务/清单项端点

**文件：** `backend/app/routers/hazard_management.py`、`backend/app/services/hazard_service.py`、`backend/tests/test_hazard_plan_api.py`

- [ ] 计划 CRUD：`/plans`（字段按规格 §5.1；`zone_ids` 校验分区属于企业；`responsible_user_id` 从 `enterprise_members` 校验）
- [ ] 任务生成函数 `generate_tasks_for_plan(db, plan)`：按频次生成 `hazard_inspection_tasks`（due_at 默认当日 18:00）并组装 items（区域内风险点 + 措施 + 模板项 + AI 补全占位）
- [ ] 任务/清单项端点：`/tasks` 列表（按责任人/状态/超期）、`/tasks/{id}` 详情、`PUT /tasks/{id}` 提交核对结果（result/remark/photo_urls）、`POST /tasks/{id}/to-record` 一键转隐患（预填 object/measure/description）
- [ ] 测试（mock db）：计划校验、任务生成组装、清单项提交、转隐患；全量回归
- [ ] `git commit -m "feat(hazard): plan, task and checklist item endpoints"`

---

## 任务 4：检查表模板（系统默认 + 企业 CRUD + AI 生成）

**文件：** `backend/app/routers/hazard_management.py`、`backend/app/services/hazard_ai_service.py`、`backend/tests/test_hazard_template_api.py`

- [ ] 模板端点：`GET /templates`（系统+企业）、`POST/PUT/DELETE /templates`（企业自定义；系统模板复制后编辑）
- [ ] AI 生成：`POST /ai/checklist-template`（文本输入行业+风险点 → items 列表，mock LLM；失败降级返回空）
- [ ] 测试 + `git commit -m "feat(hazard): checklist templates with AI generation"`

---

## 任务 5：隐患登记（三渠道）+ AI 摘要分类

**文件：** `backend/app/routers/hazard_management.py`、`backend/app/routers/public_hazard.py`、`backend/app/services/hazard_ai_service.py`、`backend/tests/test_hazard_record_api.py`、`backend/tests/test_hazard_public_api.py`

- [ ] Web 登记：`POST /records`（source_type/hazard_type/object_id/measure_id/title/description/photo_urls/location/关联）；AI 摘要：`POST /ai/record-assist`（描述→title/hazard_type/分级建议，mock）
- [ ] 扫码公开：`POST /public/hazard/report/{token}`（token=风险点 public_token 或企业 hazard_report_token；nonce 防重：前端生成 nonce + 后端 5 分钟内存缓存，重复 409；`created_by=NULL`、source_type=report）
- [ ] 移动端：同一 `POST /records`（source_type=report/manual）——无需新端点，前端移动端接入后续说明
- [ ] 测试：三渠道、nonce 幂等、token 404、AI 摘要 mock、hazard_type 字典校验
- [ ] `git commit -m "feat(hazard): record registration via web, qr and mobile with AI assist"`

---

## 任务 6：分级/治理方案/挂牌审批

**文件：** `backend/app/routers/hazard_management.py`、`backend/app/services/hazard_ai_service.py`、`backend/tests/test_hazard_grade_api.py`

- [ ] `POST /records/{id}/grade`：level（一般/重大）+ grading_basis + hazard_type + deadline（字典 `deadline_rules`）；重大必填治理方案 `rectification_plan`（goal/measures/budget/emergency_measures/acceptance_criteria），缺 422
- [ ] `POST /ai/grade`：描述+判定要点（字典 `judgment_points`）→ 建议等级/依据（mock，失败降级）
- [ ] `POST /records/{id}/approve`（重大挂牌）：enterprise_admin；`POST /ai/governance-plan` 治理方案草稿
- [ ] 测试 + `git commit -m "feat(hazard): grading, governance plan and major hazard approval"`

---

## 任务 7：整改/复查/销号端点（状态机接线）

**文件：** `backend/app/routers/hazard_management.py`、`backend/tests/test_hazard_review_api.py`

- [ ] `POST /records/{id}/rectify`（整改人提交 content+evidence）、`POST /records/{id}/review`（复查 pass/fail+evidence，复查人≠整改人 422）、`POST /records/{id}/close`（管理员销号；严格+重大 先 `second_review`）
- [ ] 接线 `hazard_state_machine.apply_transition`；复查期限提醒（整改完成 + 字典复查天数）
- [ ] 测试：状态机全路径 API 级、权限 403、退回、二次复核、销号留痕
- [ ] `git commit -m "feat(hazard): rectify, review and close endpoints wired to state machine"`

---

## 任务 8：APScheduler（任务生成 + 超期扫描 + 提前提醒）

**文件：** `backend/app/services/hazard_scheduler.py`、`backend/app/main.py`、`backend/tests/test_hazard_scheduler.py`

- [ ] `AsyncIOScheduler`：每 5 分钟——①到期计划生成任务（防重：按 plan+date 唯一）；②rectifying 超期标记 + `hazard_notifications`（overdue，防重 overdue_notified_at）；③due_at 前 2h upcoming 提醒
- [ ] `main.py` 启动/关闭调度器（lifespan）；失败不阻塞启动
- [ ] 测试（直接调扫描函数 + mock db）：到期生成、超期通知防重、提前提醒
- [ ] `git commit -m "feat(hazard): scheduler for task generation and overdue notifications"`

---

## 任务 9：联动回写派生 + 四色图叠加

**文件：** `backend/app/services/hazard_service.py`、`backend/app/routers/risk_management.py`、`backend/app/routers/hazard_management.py`、`backend/tests/test_hazard_linkage.py`

- [ ] 派生计数：`open_hazard_count(db, object_id)`/`(measure_id)`（未 closed 记录数）；在风险层级/总览/管控清单响应增加 `open_hazard_count`（含前端类型）；告知卡数据源增加未闭环标记
- [ ] 四色图叠加：风险总览/工作台分区 badge 显示未闭环数（数据来自 hierarchy/workbench 响应扩展字段）
- [ ] 测试：派生计数正确、闭环后归零、端点字段存在
- [ ] `git commit -m "feat(hazard): derived open-hazard linkage on risk views"`

---

## 任务 10：隐患公示（企业内 + 公开脱敏）

**文件：** `backend/app/routers/hazard_management.py`、`backend/app/routers/public_hazard.py`、`backend/tests/test_hazard_publicity_api.py`

- [ ] 企业内：`GET /publicity`（列表：编号/名称/等级/状态/整改情况；口径来自字典 `publicity_scope`）+ token 生成/重置
- [ ] 公开：`GET /public/hazard/{token}`（脱敏：无责任人/联系方式/照片；404「链接已失效」；generated_at）
- [ ] 测试 + `git commit -m "feat(hazard): publicity page with desensitized public endpoint"`

---

## 任务 11：驾驶舱 + 台账/监管导出

**文件：** `backend/app/services/hazard_export_service.py`、`backend/app/routers/hazard_management.py`、`backend/tests/test_hazard_dashboard_api.py`

- [ ] `GET /dashboard`：指标卡（未闭环风险点数/整改及时率/重大挂牌/超期/月度环比/扫码待确认）+ 类型分布 + 月度趋势 + 重大专表 + 企业对比（同账号多企业）；未读数（notifications）
- [ ] 导出：`/export/ledger.xlsx`（台账/超期/重大 3 sheet）、`/export/report.xlsx`（监管上报字段）
- [ ] 测试（mock）：统计口径（整改及时率/平均周期）、导出内容、未读数
- [ ] `git commit -m "feat(hazard): dashboard stats and ledger/report export"`

---

## 任务 12：AI 辅助端点（plan-builder / schedule-suggestion / checklist / governance-plan / record-assist / grade / setup-wizard）

**文件：** `backend/app/routers/hazard_management.py`、`backend/app/services/hazard_ai_service.py`、`backend/tests/test_hazard_ai_api.py`

- [ ] 全部 AI 端点统一模式：文本输入 → `llm_text_completion` → JSON 解析（复用 `_parse_ai_json`）→ 失败 `{available:false}` 降级；每个端点 mock LLM 的 ok/fallback 用例
- [ ] `setup-wizard`：问答输入 → 返回 组织树建议 + 计划建议 + 检查表建议 三块（复用既有 AI 函数）
- [ ] 测试 + `git commit -m "feat(hazard): text-only AI assist endpoints"`

---

## 任务 13-16：前端页面（分 4 批，每批含 service/类型/路由/门禁）

- **13**：`HazardInspectionTab`（台账：统计条/筛选/新建/导出/各页入口）+ `hazardService` + 类型 + 路由 + EnterpriseDetailPage Tab 接入 → `git commit -m "feat(hazard): inspection tab and hazard service"`
- **14**：`HazardPlanPage`（计划 CRUD + AI 排程卡）+ `HazardTaskPage`（清单核对 + 一键转隐患 + 超期标红）→ `feat(hazard): plan and task execution pages`
- **15**：`HazardRecordDetailPage`（时间线 + 状态机按钮按角色显示 + 治理方案表单 + 重大审批 Modal）→ `feat(hazard): record detail with state machine actions`
- **16**：`HazardDashboardPage` + `HazardTemplatePage` + `HazardPublicityPage` + `PublicHazardReportPage`（/h/report/:token 免登录，nonce）+ `PublicHazardPage`（/h/:token 脱敏）→ `feat(hazard): dashboard, templates, publicity and public pages`

每批门禁：`npx tsc -b`、eslint（改动文件）、`npx vitest run`（service 测试）、`git diff --check`。

---

## 任务 17：回归门禁 + 手工冒烟

**文件：** 无

- [ ] 后端 `python -m pytest tests/ -q` 全绿（约 481 + 本模块新增）；
- [ ] 前端 `npx tsc -b`、`npx vitest run`、eslint（分支改动文件零新增）；
- [ ] 迁移 `db_migration_hazard_management.sql` 本地幂等复跑两遍；字典种子行数核对；
- [ ] 手工冒烟（用户浏览器验证项）：计划自动生成任务、扫码公开上报、分级→挂牌→整改→复查→销号全链路（标准/严格两模式）、超期角标、四色图未闭环 badge、公示/公开页、驾驶舱与导出；
- [ ] 如发现缺陷修复提交（`fix(hazard): ...`）。

---

## 自检结论

**规格覆盖度**：B 规格 §1-§19 全部映射到任务 1-17（数据模型/状态机/计划任务/模板/三渠道/分级治理/整改复查/调度器/联动/公示/驾驶舱/AI/前端/门禁）；§20 二期（预案联动/监管对接/通知中心/拍照识别）不在本计划。

**占位符**：无 TODO；关键算法（状态机/派生计数/调度扫描）给出代码骨架；端点与表字段以规格 §5/§14 为准（本计划引用，不重复整表）。

**类型一致性**：`hazard_state_machine.apply_transition`、`hazard_service.generate_tasks_for_plan`、`open_hazard_count` 在任务 2/3/9 定义并被后续任务引用，签名一致。
