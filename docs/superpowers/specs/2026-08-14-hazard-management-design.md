# 隐患排查治理模块 — 设计规格

> **日期**：2026-08-14 | **状态**：设计中 | **依赖**：风险管理模块（分区/风险点/事件/措施/四色图）、AI 服务（DeepSeek `llm_text_completion`）、公开 token 模式（风险告知卡先例）、移动端 8082、`openpyxl`、APScheduler（新增）

---

## 1. 概述

新增独立「隐患排查治理」模块（双重预防机制第二支柱），与「风险分级管控增强」规格共同构成完整双重预防机制。范围 C 全流程数字化：

排查计划 → 任务下发（计划 × 风险清单 + AI）→ 上报登记（Web / 扫码公开 / 移动端）→ AI 辅助分级 → 重大挂牌督办 → 整改 → 复查 → 销号（标准/严格按企业配置），外加：检查表模板、隐患来源分类、重大隐患治理方案、整改证据、隐患整改公示、超期预警升级、状态回写联动、驾驶舱统计与监管台账导出。

硬性约束：**AI 全部为「辅助」而非「自动」**——AI 建议必须人工确认后才生效；AI 不可用时流程照常人工运行，不阻塞业务。

---

## 2. 需求决策（用户已逐项确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 范围 | C 全流程数字化：排查计划→任务下发→上报登记→分级→挂牌督办→整改→复查→销号 |
| 2 | 任务模型 | 混合：计划决定「何时查、谁查」，风险点清单决定「查什么」 |
| 3 | AI | A+C：AI 生成/补全排查清单 + AI 智能排程建议（频次/责任人），均人工确认 |
| 4 | 分级 | AI 辅助判定（含行业重大隐患判定要点）+ 重大隐患挂牌督办需管理员审批 |
| 5 | 渠道 | Web + 扫码公开上报（免登录、自动关联风险点）+ 移动端 8082（班组账号） |
| 6 | 闭环模式 | 按企业配置「标准 / 严格」（默认标准）；严格 = 重大隐患销号前二次复核；留痕日志两种模式均记录 |
| 7 | 联动 | 状态回写：闭环后风险点「未闭环隐患」标记消失、管控措施视为「已恢复」；未闭环期间持续显示「管控失效」 |
| 8 | 报表 | C 完整驾驶舱：指标卡 + 类型分布 + 趋势 + 重大专表 + 企业对比 + 监管台账导出 |
| 9 | 完整性补充 | 检查表模板（日常/综合/专项/节假日）、隐患来源分类、重大隐患治理方案、整改证据照片、隐患整改公示、超期升级、判定依据 |
| 10 | 二期 | 未闭环重大隐患写入预案生成、监管平台真实对接（本次不做） |

---

## 3. 现状基础

| 组件 | 现状 |
|------|------|
| 隐患模块 | **无独立模块**（全库 rg「隐患」仅 chat 上下文提及） |
| 风险数据 | `risk_zones` / `risk_objects`（含责任单位/人/电话、public_token）/ `risk_measures`（category/description/responsible_person/status）—— 关联与回写的数据源 |
| AI | `llm_text_completion`（DeepSeek）+ 系统级 AI 配置（加密存储）；`risk_ai_service` 调用模式可复制 |
| 公开 token | 风险告知卡已有公开只读页先例（`/r/:token`、`secrets.token_hex(32)`、无效 404 文案） |
| 导出 | `openpyxl`（xlsx）与 docx 管线已有 |
| 移动端 | 8082 应用存在（企业状态独立），可加页面复用同一后端 API |
| 定时任务 | **无现有机制** → 需新增（见 §13） |
| 组织 | `enterprises.org_structure` JSONB（部门/岗位信息，责任人选择可参考） |

---

## 4. 架构与组件

```
backend/
  app/models/hazard_management.py        9 张表（§5）+ enterprises.hazard_closure_mode
  app/schemas/hazard_management.py       请求/响应模型
  app/routers/hazard_management.py       鉴权端点（计划/任务/隐患单/审批/驾驶舱/导出/模板）
  app/routers/public_hazard.py           公开端点（扫码上报 /h/report/:token、公示 /h/:token）
  app/services/hazard_ai_service.py      AI 清单生成、排程建议、分级建议（复用 llm_text_completion）
  app/services/hazard_service.py         状态机、任务生成、回写派生、统计、导出
  app/services/hazard_scheduler.py       APScheduler：任务生成 + 超期扫描
  db_migration_hazard_management.sql     表/配置/系统模板数据迁移

frontend/
  src/pages/Enterprise/HazardInspectionTab.tsx       企业详情页新 Tab（台账/驾驶舱/计划/公示/模板入口）
  src/pages/Enterprise/HazardPlanPage.tsx            排查计划配置（含 AI 排程建议）
  src/pages/Enterprise/HazardTaskPage.tsx            任务执行（清单核对）
  src/pages/Enterprise/HazardRecordDetailPage.tsx    隐患单详情（状态机操作/时间线）
  src/pages/Enterprise/HazardDashboardPage.tsx       驾驶舱
  src/pages/Enterprise/HazardTemplatePage.tsx        检查表模板管理
  src/pages/PublicHazardReportPage.tsx               扫码上报页（路由 /h/report/:token）
  src/pages/PublicHazardPage.tsx                     隐患公示公开页（路由 /h/:token）
  src/services/hazardService.ts                      类型与 API 封装

mobile/（8082） 新增：今日任务 / 任务执行 / 上报隐患 / 我的上报（复用同一 API）
```

---

## 5. 数据模型（9 张表 + 1 配置）

### 5.1 `hazard_inspection_plans` 排查计划

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| enterprise_id | UUID FK CASCADE | |
| name | String(255) NOT NULL | 计划名称 |
| category | String(20) NOT NULL | daily / comprehensive / special / holiday（日常/综合/专项/节假日） |
| frequency | String(20) NOT NULL | daily / weekly / monthly / custom |
| weekdays | JSONB NULL | weekly/custom 时的星期集合 |
| zone_ids | JSONB NOT NULL | 覆盖分区 id 列表 |
| template_id | UUID FK NULL | 关联检查表模板（可选） |
| responsible_user_id | UUID FK users NULL | 默认责任人 |
| ai_suggestion | JSONB NULL | AI 排程建议原文（供追溯） |
| enabled | Boolean 默认 true | |
| created_at / updated_at | DateTime | |

### 5.2 `hazard_inspection_tasks` 排查任务

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| plan_id | UUID FK CASCADE | |
| enterprise_id | UUID FK CASCADE | |
| title | String(255) | 如「生产车间日排查 · 08-14」 |
| status | String(20) | pending / processing / done / overdue |
| responsible_user_id | UUID FK users | |
| due_at | DateTime NOT NULL | 默认当日 18:00，计划可配 |
| completed_at | DateTime NULL | |
| overdue_notified_at | DateTime NULL | 防重复通知 |

### 5.3 `hazard_inspection_items` 排查清单项

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| task_id | UUID FK CASCADE | |
| object_id | UUID FK risk_objects NULL | 关联风险点 |
| measure_id | UUID FK risk_measures NULL | 关联管控措施 |
| content | Text NOT NULL | 核对内容 |
| expected_note | Text NULL | 期望状态/标准 |
| result | String(10) 默认 pending | pending / normal / abnormal / na |
| remark | Text NULL | 备注 |
| photo_urls | JSONB NULL | 异常佐证照片 |

### 5.4 `hazard_records` 隐患单

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| enterprise_id | UUID FK CASCADE | |
| code | String(32) NOT NULL | 展示编号 HD-{三位序号}（创建时生成，不复用） |
| source_type | String(20) NOT NULL | inspection / report / regulatory / accident / manual |
| source_task_id / source_item_id | UUID FK NULL | 来自排查任务时回填 |
| object_id | UUID FK risk_objects NULL | 关联风险点（扫码上报自动带） |
| measure_id | UUID FK risk_measures NULL | 关联管控措施 |
| title | String(255) NOT NULL | |
| description | Text NOT NULL | |
| photo_urls | JSONB NULL | 现场照片 |
| location | String(500) NULL | 位置描述（未关联对象时） |
| level | String(10) NULL | 一般 / 重大；分级前为 NULL |
| level_source | String(10) NULL | ai / manual |
| grading_basis | Text NULL | 判定依据（重大必填，引用标准条款/要点） |
| status | String(20) NOT NULL | registered / grading / pending_approval / rectifying / reviewing / second_review / closed |
| rectification_plan | JSONB NULL | 重大必填：goal / measures / budget / emergency_measures / acceptance_criteria |
| deadline | Date NULL | 整改期限（分级后按等级/配置生成） |
| rectification_user_id | UUID FK users NULL | 整改责任人 |
| reviewer_user_id | UUID FK users NULL | 复查人（≠ 整改人） |
| created_by | UUID FK users NULL | 登记人（扫码上报为 NULL） |
| closed_at | DateTime NULL | 销号时间 |
| created_at / updated_at | DateTime | |

### 5.5 `hazard_rectifications` 整改记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| record_id | UUID FK CASCADE | |
| user_id | UUID FK users | 整改人 |
| content | Text NOT NULL | 整改内容/措施 |
| evidence | JSONB NULL | 整改后照片/佐证 |
| submitted_at | DateTime | |

### 5.6 `hazard_reviews` 复查/复核记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| record_id | UUID FK CASCADE | |
| review_type | String(20) | first_review / second_review / close |
| user_id | UUID FK users | 复查/复核人 |
| result | String(10) | pass / fail |
| comment | Text NULL | |
| evidence | JSONB NULL | 复查照片/佐证 |
| created_at | DateTime | |

### 5.7 `hazard_approvals` 挂牌督办审批

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| record_id | UUID FK CASCADE | |
| user_id | UUID FK users | 审批人（管理员角色） |
| action | String(10) | approve / reject |
| comment | Text NULL | |
| created_at | DateTime | |

### 5.8 `hazard_audit_logs` 留痕日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| enterprise_id | UUID FK CASCADE | |
| record_id | UUID FK NULL | 隐患单相关操作时回填 |
| user_id | UUID FK users NULL | 操作人 |
| action | String(50) | 登记/分级/AI建议/审批/整改/复查/退回/销号/超期通知 等 |
| detail | JSONB NULL | 变更前后 |
| created_at | DateTime | |

### 5.9 `hazard_checklist_templates` 检查表模板

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| enterprise_id | UUID FK NULL | NULL = 系统默认模板 |
| name | String(255) NOT NULL | |
| category | String(20) NOT NULL | daily / comprehensive / special / holiday |
| items | JSONB NOT NULL | `[{content, expected_note}]` |
| is_system | Boolean | |
| created_at / updated_at | DateTime | |

### 5.10 企业配置

- `enterprises.hazard_closure_mode` String(20) 默认 `standard`（standard / strict）；
- `enterprises.hazard_public_token` String(64) UNIQUE NULL（隐患公示公开页 token，生成/重置）；
- 扫码上报 token：**复用 `risk_objects.public_token`**（风险点二维码）与新增企业级 `enterprises.hazard_report_token`（无风险点场景/通用二维码）。

### 5.11 状态机

```
registered → grading（AI 建议后人工确认）
  ├─ 一般 → rectifying → reviewing → closed（标准模式）
  └─ 重大 → pending_approval（管理员审批）→ rectifying → reviewing
         → [严格模式] second_review → closed
  reviewing / second_review 不通过 → 退回 rectifying
```

- 超期：rectifying 且 deadline 过期 → 派生 `overdue` 标记（不改 status 值域）+ 上级通知一次（audit log）；
- 复查人 ≠ 整改人（后端强制校验）；
- 标准模式：销号 = 管理员确认（review_type=close）；严格模式且重大：先 second_review 通过再 close。

---

## 6. 排查计划与任务（含 AI）

- **计划 CRUD**：名称、类别（日常/综合/专项/节假日）、频次（日/周/月/自定义+星期）、覆盖分区（多选）、责任人、关联模板（可选）、启用开关；
- **AI 排程建议**：`POST /ai/schedule-suggestion`，输入计划草稿，返回 `{suggested_frequency, suggested_responsible_user_id, reason}`（依据：分区风险等级、历史隐患频次、责任人岗位负载——历史隐患来自 `hazard_records`）；页面「采纳 / 忽略」；
- **任务生成**：调度器按计划到期生成任务（默认当日 18:00 截止）；生成时按 `zone_ids` 查当前风险点 + 管控措施组装清单项（动态快照，含 object/measure 关联）；
- **AI 清单补全**：`POST /ai/checklist`，输入任务上下文，返回建议新增项（LLM），页面勾选后合并去重；AI 失败时任务仍可执行（默认项即可）；
- **任务执行**：逐项核对 normal / abnormal / na；abnormal 可一键转隐患登记（预填对象/措施/描述/照片）；
- **超期**：扫描标记 + 上级通知（驾驶舱角标 + 列表标红 + audit log）。

---

## 7. 检查表模板

- 系统默认库：日常检查表、综合检查表、专项-消防、专项-危化品、节假日检查表（items 预置，来自常见检查要点）；
- 企业自定义模板 CRUD（复制系统模板后编辑）；
- 计划可选关联模板；未关联则纯动态生成（风险点+措施+AI）。

---

## 8. 隐患登记（三渠道）

- **Web**：表单含来源（inspection / report / regulatory / accident / manual）、关联风险点/措施（可搜索）、标题、描述、照片、位置；登记人 = 当前用户；
- **扫码公开**：`/h/report/:token`（风险点 token 自动关联对象；企业通用 token 则手选/留空位置）→ 免登录表单（描述 + 照片）→ 落库 `source_type=report`、`created_by=NULL`、状态 registered，待管理员处理；
- **移动端**：登录后「+ 上报隐患」→ 同 Web 简化版；来源 report / manual；
- **幂等**：公开表单带一次性 nonce（前端生成 + 后端 5 分钟有效），重复提交返回 409；
- 提交成功提示「已提交，待企业管理员确认」，不暴露内部信息。

---

## 9. 隐患分级与挂牌督办

- **AI 分级建议**：`POST /ai/grade`，输入描述/照片说明 + 判定要点，返回 `{suggested_level, basis, confidence}`；人工确认或修改后落库（`level_source` 记录 ai / manual）；
- **判定要点库**：内置常见行业重大隐患判定要点（危化品储运 / 消防 / 特种设备 / 粉尘涉爆 / 有限空间等，文本常量，来源为国家重大事故隐患判定标准要点摘要）；页面标注「参考提示，以现行有效判定标准为准」，不声称完整法律效力；
- **分级规则**：一般 → 直接进入整改（按配置生成默认期限）；重大 → 治理方案必填（goal / measures / budget / emergency_measures / acceptance_criteria）→ 管理员审批挂牌（hazard_approvals）→ 整改；
- 重大隐患 `grading_basis` 必填。

---

## 10. 整改 / 复查 / 销号

- **整改**：责任人提交整改内容 + 证据照片（hazard_rectifications）；
- **复查**：复查人由管理员指定且 ≠ 整改人（422 拦截）；pass/fail + 证据；fail → 退回整改并留痕；
- **销号**：标准模式管理员 close；严格模式且重大 → second_review（安全总监级，即管理员角色）通过后 close；
- 全程 `hazard_audit_logs` 留痕（两种模式都记录，严格模式额外多一道复核节点）。

---

## 11. 联动回写与隐患公示

### 11.1 状态回写（派生实现）

- 风险点/措施「未闭环隐患」标记 = **实时派生计算**（`hazard_records` 中该 object/measure 关联且未 closed 的数量），不修改风险源表字段，避免破坏既有 `status` 值域；
- 展示位置：风险层级树、风险总览、风险告知卡（「存在未闭环隐患」badge）、管控清单；
- 隐患闭环后派生数量归零，标记自动消失——即用户确认的「状态回写」效果；
- 每次状态变更写 audit log，保证可追溯。

### 11.2 隐患整改公示

- 企业内公示列表（编号/名称/等级/状态/整改情况）+ 打印样式；
- 公开页 `/h/:token`（`enterprises.hazard_public_token`）：只读、脱敏（不含责任人/联系方式）；
- 公示口径可配：进行中 / 已闭环（默认全部）。

---

## 12. 驾驶舱与导出

**指标卡**：未闭环隐患风险点数、整改及时率（按期闭环/应闭环）、重大挂牌数、超期数、月度隐患数（环比）、扫码待确认数。

**图表**：隐患类型分布（饼图）、月度趋势（折线）、重大隐患专表（表）、企业间对比（横向条形，同账号多企业）。

**导出（openpyxl）**：

- 台账 xlsx：sheet1 台账（全部字段）、sheet2 超期清单、sheet3 重大隐患；
- 监管上报台账 xlsx：编号 / 名称 / 位置 / 等级 / 判定依据 / 整改期限 / 责任单位 / 整改进度。

**统计口径**：整改及时率、平均整改周期（闭环时间 - 登记时间）、超期率，均按自然月滚动计算。

---

## 13. 定时任务（假设，需审查确认）

- 新增 `APScheduler`（`AsyncIOScheduler`）随 FastAPI 进程启动：每 5 分钟扫描——①到期计划生成任务；②rectifying 超期标记与通知；
- **假设**：后端运行于单容器/单进程（与现有部署一致）；若部署不支持常驻进程，退化为外部 cron 调用内部端点（端点保留，仅调度方式切换）；
- 该假设在规格审查时请用户确认。

---

## 14. 接口清单（概览）

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/enterprises/{id}/hazard-inspection/plans` | 排查计划 |
| CRUD | `/enterprises/{id}/hazard-inspection/tasks` | 排查任务（含执行提交 items） |
| CRUD | `/enterprises/{id}/hazard-inspection/records` | 隐患单（登记/详情/列表） |
| POST | `/enterprises/{id}/hazard-inspection/records/{rid}/grade` | 分级确认 |
| POST | `/enterprises/{id}/hazard-inspection/records/{rid}/approve` | 挂牌审批 |
| POST | `/enterprises/{id}/hazard-inspection/records/{rid}/rectify` | 提交整改 |
| POST | `/enterprises/{id}/hazard-inspection/records/{rid}/review` | 复查/二次复核 |
| POST | `/enterprises/{id}/hazard-inspection/records/{rid}/close` | 销号 |
| GET | `/enterprises/{id}/hazard-inspection/dashboard` | 驾驶舱 |
| GET | `/enterprises/{id}/hazard-inspection/export/ledger.xlsx` | 台账导出 |
| GET | `/enterprises/{id}/hazard-inspection/export/report.xlsx` | 监管上报台账 |
| CRUD | `/enterprises/{id}/hazard-inspection/templates` | 检查表模板 |
| POST | `/enterprises/{id}/hazard-inspection/ai/schedule-suggestion` | AI 排程建议 |
| POST | `/enterprises/{id}/hazard-inspection/ai/checklist` | AI 清单补全 |
| POST | `/enterprises/{id}/hazard-inspection/ai/grade` | AI 分级建议 |
| POST | `/public/hazard/report/{token}` | 扫码上报（免登录） |
| GET | `/public/hazard/{token}` | 隐患公示公开页（脱敏） |
| POST | `/enterprises/{id}/hazard-inspection/publicity-token` | 生成/重置公示 token |
| 扩展 | risk hierarchy / overview / notice card | 增加未闭环隐患派生计数 |

---

## 15. 前端页面

| 页面 | 说明 |
|------|------|
| `HazardInspectionTab` | 企业详情页新 Tab：台账列表（统计条/筛选/新建/导出台账/驾驶舱入口） |
| `HazardPlanPage` | 计划配置（含 AI 排程建议卡） |
| `HazardTaskPage` | 任务执行（清单核对 + 一键转隐患） |
| `HazardRecordDetailPage` | 隐患单详情（时间线 + 按角色/状态显示操作按钮） |
| `HazardDashboardPage` | 驾驶舱（指标卡 + 图表 + 导出按钮） |
| `HazardTemplatePage` | 检查表模板管理 |
| `PublicHazardReportPage` | 扫码上报（`/h/report/:token`，免登录） |
| `PublicHazardPage` | 公示公开页（`/h/:token`，脱敏） |
| 移动端 | 今日任务 / 任务执行 / 上报隐患 / 我的上报 |

---

## 16. 错误处理

- AI 失败/超时 → 返回「无 AI 建议」降级，不阻塞流程；
- token 无效 → 404「链接已失效」；
- 公开表单重复提交 → 409；
- 复查人 = 整改人 → 422；
- 重大隐患缺治理方案 / 判定依据 → 422；
- 超期任务重复通知 → 以 `overdue_notified_at` 防重；
- 并发操作（同一隐患单）→ 乐观锁/状态前置校验，非法流转 409。

---

## 17. 测试策略

- **pytest**：
  - 状态机全路径：一般/重大 × 标准/严格（含退回、二次复核、销号）；
  - 权限矩阵：登记/整改/复查/审批/销号各角色；
  - 超期扫描与防重通知；任务到期生成；
  - AI 降级（mock LLM 失败）；分级校验；幂等 nonce；
  - 回写派生计数；驾驶舱统计口径；导出内容；
  - 公开端点脱敏与 404；
- **前端 vitest**：清单核对交互、表单校验、筛选、驾驶舱数据映射、公开页渲染；
- **移动端**：任务/上报页冒烟；
- **门禁**：tsc / eslint / vitest / pytest 全绿 + `git diff --check`，与既有惯例一致。

---

## 18. 部署与迁移

- 应用 `db_migration_hazard_management.sql`（9 张表 + 企业配置列 + 系统模板种子数据）；
- 新增依赖：`apscheduler`；
- 后端容器重建；移动端 8082 构建部署；
- 公开路由 `/h/report/:token`、`/h/:token` 加入 SPA 路由（Vite fallback 已在 `signs` 先例中处理）。

---

## 19. 验收标准

1. 按计划自动生成任务，清单含默认 + 模板 + AI 项，可执行核对；
2. 三渠道均可登记隐患，排查异常项一键转隐患；
3. 一般/重大流程 × 标准/严格模式行为正确（含退回、二次复核）；
4. 超期预警与上级通知生效且不重复；
5. 隐患闭环后风险点「未闭环隐患」标记消失，告知卡/清单实时反映；
6. 驾驶舱数据正确，台账与监管上报台账可导出；
7. 公示页/公开页无敏感信息；
8. 全部门禁通过。

---

## 20. 二期（本次不做）

- 未闭环重大隐患写入预案生成章节/附件；
- 与监管平台真实系统对接上报；
- 通知中心（站内信/短信/企业微信）。
