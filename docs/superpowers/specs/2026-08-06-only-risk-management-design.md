# 只保留风险分级管控：旧风险源收口设计

<!--
  文档元信息
  创建日期: 2026-08-06
  作者: Codex
  版本: 1.0
  状态: 待审查
  依赖: PRD-02, PRD-15
-->

## 1. 背景与目标

系统当前存在两条风险数据路径：

- 旧版 `risk_sources`：一维风险源记录，包含名称、位置、类别、可能性、严重性、风险等级和控制措施。
- 新版风险分级管控：`risk_zones -> risk_objects -> risk_units -> risk_events -> risk_measures` 五层结构，风险等级和分值位于 `risk_events`，管控措施位于 `risk_measures`。

用户目标是在企业信息中只保留「风险分级管控」作为风险数据入口，不再让用户使用旧版「风险源」入口。

本设计的成功标准是：

1. 旧 `risk_sources` 数据可以通过向导迁移到新五层结构，迁移过程原子、可重复执行、不丢数据。
2. 预案生成、风险评估、统计、chat 助手、Web 端和移动端全部改读新五层数据。
3. 迁移验证通过后，旧风险源入口从 Web 和移动端下线，旧表和旧 API 保留为兼容层，不物理删除。

## 2. 术语

| 术语 | 含义 |
|---|---|
| 旧风险源 | `RiskSource` 模型对应的旧版一维风险数据 |
| 风险分级管控 | `RiskZone -> RiskObject -> RiskUnit -> RiskEvent -> RiskMeasure` 五层新体系 |
| 迁移闭环 | 预览、确认、原子执行、写回 `migrated` 标记、迁移后刷新全链路的完整流程 |
| 风险事件数 | 新五层体系下 `risk_events` 的记录数，用于替代旧「风险源数」的统计口径 |

## 3. 已确认决策

| 决策项 | 结论 |
|---|---|
| 最终产品入口 | 企业信息只保留「风险分级管控」 |
| 旧数据 | 不自动丢弃，通过迁移向导迁移；旧表保留为备份 |
| 旧 API | 保留为 deprecated 兼容层，不删除路由 |
| 旧 Web Tab | 迁移验证通过后从页面移除 |
| 旧移动端 | 风险源列表页替换为风险分级管控列表页 |
| 统计口径 | 新「风险事件数」替代旧「风险源数」 |
| chat 助手 | 移除旧风险源增删改工具，读取新分级管控数据 |
| 迁移时机 | 由用户在风险分级管控页显式触发，不在启动时自动迁移 |
| 迁移记录 | 新增 `risk_objects.legacy_source_id`，用于幂等和审计 |

## 4. 现状与断点

### 4.1 迁移入口现状

- `RiskMigrationWizard.tsx` 已存在但未挂载到页面。
- 向导当前逐个调用 `createZone`、`createObject`、`createEvent`，不调用后端 `/migrate/execute`，因此不会写回 `RiskSource.migrated`，也不具备单事务回滚。
- 后端 `/migrate/execute` 已存在，但前端未消费。
- 后端 `/migrate/execute` 调用 `compute_risk("LS", params)` 时没有传入评估方法配置，LS 无阈值配置时会把所有数据回退为「低」。
- AI 预览接口返回 `suggested_accident_type` 和 `suggested_params`，前端 `MigrationItem` 读取的是 `suggested_event`，字段不一致。
- 后端没有可靠的幂等字段，重复执行可能产生重复对象。

### 4.2 下游链路现状

| 位置 | 当前行为 | 问题 |
|---|---|---|
| `generation.py` | 5 处查询旧 `RiskSource` | 预案提示词仍使用旧数据 |
| `external.py` | 查询旧 `RiskSource`，且调用 `_collect_enterprise_data` 时多传了 `accident_type` | 旧数据依赖 + 参数签名不一致 |
| `risk_assessment.py` | 生成上下文已用新五层，但前置检查仍查旧表 | 旧表为空时新五层有数据也会被拦截 |
| `dashboard.py` | 统计旧 `RiskSource` | 统计口径错误 |
| `enterprises.py` | 返回旧 `risk_sources_count` | 页面统计口径错误 |
| `chat_dispatch.py` | 读取和增删改旧 `RiskSource` | chat 会创建旧数据 |
| 移动端 | 使用旧 `risk-sources` 路由和旧 CRUD | 仍是旧入口 |
| `risk_context_builder.py` | 已生成层级上下文 | 缺少 `name/categories/location/control_measures`，与旧提示词兼容性不足 |

## 5. 范围与非目标

### 5.1 范围内

- 旧风险源迁移服务、接口和前端向导。
- 新五层上下文补齐旧提示词所需字段。
- 预案生成、外部生成、风险评估前置检查切换。
- 统计、chat、Web 端、移动端切换。
- 旧风险源入口下线。

### 5.2 非目标

- 不在本设计内物理删除 `risk_sources` 表。
- 不在本设计内删除旧 CRUD 路由文件。
- 不在本设计内重做风险分级管控的五层 CRUD。
- 不在本设计内自动批量迁移所有企业，迁移由用户逐企业确认。

## 6. 总体架构

```text
用户进入风险分级管控页
  -> 查询 /risk-management/migrate/preview
  -> 存在未迁移旧风险源时显示迁移横幅
  -> 打开 RiskMigrationWizard
  -> 预览默认映射，可选 AI 建议覆盖
  -> 用户确认后 POST /risk-management/migrate/execute
  -> 后端单事务创建五层数据并标记 migrated
  -> 失效前端查询并刷新风险分级树

下游消费方
  -> build_risk_management_context 读取新五层
  -> generation / risk_assessment / chat 使用同一上下文
  -> 统计使用 risk_stats_service 统计 risk_events
```

## 7. 旧数据迁移闭环

### 7.1 数据映射

| 旧字段 | 新字段 | 规则 |
|---|---|---|
| `id` | `RiskObject.legacy_source_id` | 新增字段，用于幂等和审计 |
| `categories` | `RiskObject.category` | 取第一个类别，空则置空 |
| `name` | `RiskObject.name` | 直接映射 |
| `location` | `RiskObject.location` | 直接映射 |
| `location_x` | `RiskObject.location_x` | 直接映射 |
| `location_y` | `RiskObject.location_y` | 直接映射 |
| `description` | `RiskEvent.description` | 直接映射 |
| `likelihood` | `RiskEvent.method_params["l"]` | 旧值已为 1-5 整数，缺失默认 3 |
| `severity` | `RiskEvent.method_params["s"]` | 旧值已为 1-5 整数，缺失默认 3 |
| `risk_level` | `RiskEvent.risk_level` | 使用 `get_active_method_config` + `compute_risk` 重新计算 |
| `control_measures` | `RiskMeasure` | 按换行、`；`、`;` 拆分；默认 `measure_category=management` |
| 无 | `RiskZone.name` | AI 建议优先，兜底为「历史风险源」 |
| 无 | `RiskEvent.accident_type` | AI 建议优先，兜底为旧 `name`，空时用「安全生产事故」 |

每一条未迁移的旧风险源生成：

- 1 个分区（同企业同楼层同名称时复用，不重复创建）。
- 1 个对象，写入 `legacy_source_id`。
- 1 个事件，挂到对象下。
- 0 到 N 条措施，由 `control_measures` 拆分而来。

### 7.2 幂等与事务

- 新增数据库字段：

```sql
ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS legacy_source_id VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_ro_legacy_source
    ON risk_objects(enterprise_id, legacy_source_id);
```

- 迁移执行前只读取 `migrated=false` 的旧风险源。
- 如果 `RiskObject.legacy_source_id` 已存在，跳过创建并标记旧记录为已迁移。
- 所有写入在同一个事务中完成，任一环节失败则整体回滚。
- 迁移成功后将对应旧记录 `migrated=true`。

### 7.3 接口契约

#### GET `/enterprises/{enterprise_id}/risk-management/migrate/preview`

返回未迁移旧风险源的默认映射，不调用 AI。

```json
{
  "data": {
    "items": [
      {
        "source_id": "uuid",
        "source_name": "火灾",
        "source_location": "生产车间",
        "source_categories": ["火灾"],
        "suggested_zone": "历史风险源",
        "suggested_object": "火灾",
        "suggested_event": "火灾",
        "suggested_params": {"l": 3, "s": 3},
        "control_measures": "定期巡检"
      }
    ],
    "total": 1,
    "migrated_total": 18
  }
}
```

#### POST `/enterprises/{enterprise_id}/risk-management/ai/migrate-preview`

返回 AI 映射建议；AI 未配置或调用失败时，后端回退为默认映射，不返回错误。

#### POST `/enterprises/{enterprise_id}/risk-management/migrate/execute`

请求体：

```json
{
  "mappings": [
    {
      "source_id": "uuid",
      "zone_name": "历史风险源",
      "object_name": "火灾",
      "accident_type": "火灾",
      "method_params": {"l": 3, "s": 3}
    }
  ]
}
```

响应体：

```json
{
  "data": {
    "migrated": 1,
    "skipped": 0,
    "created": {
      "zones": 1,
      "objects": 1,
      "events": 1,
      "measures": 1
    }
  }
}
```

校验规则：

- `source_id` 必须属于当前企业且 `migrated=false`。
- `zone_name`、`object_name`、`accident_type` 必须非空。
- `method_params` 的 `l` 和 `s` 必须为 1-5 数值，缺失时使用默认 3。
- 风险等级通过 `get_active_method_config` 获取企业或系统 LS 配置后计算。

### 7.4 前端迁移向导

修改 `RiskMigrationWizard.tsx`：

1. 打开时先调用 `GET /migrate/preview` 展示默认映射。
2. 再尝试调用 `POST /ai/migrate-preview`，成功则用 AI 建议覆盖映射；失败则保留默认映射。
3. 用户可逐条采纳、修改、跳过。
4. 确认后调用 `POST /migrate/execute`，不再逐个调用 `createZone/createObject/createEvent`。
5. 成功后失效 `risk-hierarchy`、`enterprise`、`migrate-preview` 查询并刷新。

将迁移入口挂到 `RiskManagementTab.tsx`：

- 查询 `GET /migrate/preview`。
- `total > 0` 时显示迁移提示横幅和「迁移旧风险源」按钮。
- `total == 0` 时不显示迁移入口。

## 8. 下游链路切换

### 8.1 风险上下文

扩展 `build_risk_management_context` 返回的每条风险源记录：

```python
{
    "zone": zone.name,
    "object": obj.name,
    "unit": unit.name if unit else None,
    "name": obj.name,
    "categories": obj.category or "",
    "location": obj.location or "",
    "accident_type": event.accident_type,
    "risk_level": event.risk_level,
    "risk_score": event.risk_score,
    "description": event.description,
    "triggers": event.trigger_conditions,
    "consequences": event.consequences,
    "control_measures": "；".join(m.description for m in event.measures),
    "measures": [
        {"category": m.measure_category, "description": m.description}
        for m in event.measures
    ],
}
```

同时补齐 `build_risk_management_context` 的企业信息字段，避免风险评估服务委托新上下文后丢失原有企业字段：

```python
{
    "name": ent.name,
    "industry": ent.industry,
    "address": ent.address,
    "employee_count": ent.employee_count,
    "business_scope": ent.business_scope,
    "building_overview": ent.building_overview,
    "surrounding_info": ent.surrounding_info,
    "legal_representative": ent.legal_representative,
    "credit_code": ent.credit_code,
    "economic_type": ent.economic_type,
    "established_date": str(ent.established_date) if ent.established_date else None,
    "registered_capital": ent.registered_capital,
    "phone": ent.phone,
    "land_area": ent.land_area,
    "building_area": ent.building_area,
    "safety_officer": ent.safety_officer,
    "safety_standardization": ent.safety_standardization,
    "fire_approval": ent.fire_approval,
    "main_products": ent.main_products,
    "hazardous_chemicals": ent.hazardous_chemicals,
    "special_equipment": ent.special_equipment,
    "fire_protection_summary": ent.fire_protection_summary,
    "special_equipment_detail": ent.special_equipment_detail,
    "main_equipment_list": ent.main_equipment_list,
    "natural_conditions": ent.natural_conditions,
}
```

### 8.2 预案生成

修改 `generation.py`：

- 删除 5 处 `RiskSource` 查询。
- 在收集企业数据前调用 `build_risk_management_context`。
- `_collect_enterprise_data` 的 `risk_sources` 改由新上下文组装，同时保留旧提示词所需的 `categories/name/location/description/risk_level/control_measures` 字段。
- 统一 `_collect_enterprise_data` 的参数签名，并让 `external.py` 按新签名调用，修复当前多传 `accident_type` 的问题。

`external.py` 同步切换：

- 删除 `RiskSource` 查询。
- 调用 `build_risk_management_context` 后传给 `_collect_enterprise_data`。

### 8.3 风险评估

修改 `risk_assessment.py`：

- 先调用 `build_risk_management_context`。
- 前置检查改为 `total_events == 0`，提示「请先录入风险分级管控数据」。
- 删除 `RiskSource` 查询和不再使用的 import。

同步处理 `risk_assessment_service.py`：

- 让旧 `build_risk_assessment_context` 委托给新上下文构建器。
- 删除其对 `RiskSource` 的直接查询，保留 `risk_source_count` 字段名作为 AI 摘要兼容字段。

### 8.4 统计

新增 `backend/app/services/risk_stats_service.py`：

- `count_enterprise_risk_events`：统计单企业 `risk_events` 数。
- `count_user_risk_events`：统计当前用户全部企业的 `risk_events` 数。
- `count_enterprises_risk_events`：批量统计企业列表的 `risk_events` 数，避免 N+1。

修改：

- `enterprises.py`：`EnterpriseResponse` 新增 `risk_events_count`，保留 `risk_sources_count` 作为旧数据兼容字段。
- `dashboard.py`：`DashboardStats` 新增 `risk_event_count`，保留 `risk_source_count` 为旧数据兼容字段；统计逻辑改用新服务。
- 前端 Dashboard 和企业列表显示新「风险事件数」。

### 8.5 chat 助手

修改 `chat_dispatch.py`：

- `_get_dashboard` 的 `risk_source_count` 保留旧值，新增 `risk_event_count`。
- `_get_enterprise` 的 `risk_sources` 改为读取新上下文，返回层级化风险数据。
- `_list_risk_sources` 改为读取新上下文，不再调用旧 CRUD。
- 移除 `_create_risk_source`、`_update_risk_source`、`_delete_risk_source` 的 chat 工具注册。

修改 `chat.py`：

- 删除旧风险源增删改工具定义。
- 更新工具描述和系统提示，不再宣称「管理风险源」。

### 8.6 Web 端

修改 `EnterpriseDetailPage.tsx`：

- 删除旧「风险源」Tab 和 `RiskSourceForm` 引用。
- 保留「风险分级管控」Tab，必要时调整 Tab 顺序。

修改 `EnterpriseListPage.tsx`：

- 表格列从「风险源数」改为「风险事件数」。
- `dataIndex` 使用 `risk_events_count`。

修改 `DashboardPage.tsx`：

- 统计标题从「风险源数」改为「风险事件数」。
- 数据字段使用 `risk_event_count`。

### 8.7 移动端

新增 `frontend/src/mobile/screens/RiskManagementListScreen.tsx`：

- 使用 `getFullHierarchy` 展示分区、对象、事件和风险等级。
- 只读查看，不做旧风险源新增或删除。

修改 `frontend/src/mobile/routes.tsx`：

- 新路由 `enterprises/:id/risk-management`。
- 移除 `enterprises/:id/risk-sources` 路由。

修改 `EnterpriseDetailScreen.tsx`：

- 统计卡片显示「风险事件」。
- 风险 Tab 改为读取新五层数据并跳转风险分级管控页。

修改 `PlanCreateScreen.tsx`：

- 事故类型从 `risk_events.accident_type` 生成。
- 文案从「风险源」改为「风险事件」。

## 9. 下线策略

实施顺序分为三个阶段，避免一次性切换导致数据缺口：

### 阶段 1：迁移闭环

- 新增 `legacy_source_id` 字段和迁移 SQL。
- 新增迁移服务、Schema 和接口。
- 挂载并重写 `RiskMigrationWizard`。
- 旧风险源 Tab 暂时保留，作为迁移前后的对照入口。

### 阶段 2：下游切换

- 切换预案生成、外部生成、风险评估前置检查。
- 切换统计、chat、Web 端和移动端。
- 阶段 2 完成后，旧表仍保留数据，但新业务不再读旧表。

### 阶段 3：入口下线

- 删除 Web 旧「风险源」Tab。
- 删除移动端旧风险源路由和旧列表页。
- 删除 chat 旧风险源增删改工具。
- 保留旧 CRUD 路由和旧表作为兼容层。

## 10. 验收标准

| 编号 | 验收项 | 通过条件 |
|---|---|---|
| AC-01 | 迁移预览 | 只返回当前企业 `migrated=false` 的旧风险源 |
| AC-02 | 默认映射 | 无 AI 配置时也能生成可执行映射 |
| AC-03 | AI 建议 | AI 可用时返回 `suggested_accident_type` 和 `suggested_params`，前端可正确合并 |
| AC-04 | 原子迁移 | 迁移过程中任一记录失败时，整批不产生部分写入 |
| AC-05 | 幂等执行 | 同一旧记录不会因重复执行产生重复对象 |
| AC-06 | 数据完整性 | 旧位置、坐标、类别、描述、风险参数和控制措施迁移后仍可读 |
| AC-07 | 风险等级 | 新事件风险等级由 LS 配置计算，不再全部回退为「低」 |
| AC-08 | 预案生成 | `generation.py` 和 `external.py` 不再查询 `RiskSource` |
| AC-09 | 风险评估 | 新五层有事件但旧表为空时，前置检查可以通过 |
| AC-10 | 统计口径 | Dashboard、企业列表、企业详情的风险事件数与 `risk_events` 一致 |
| AC-11 | chat 读取 | chat 企业详情和风险列表返回新五层数据 |
| AC-12 | chat 写入 | chat 不再暴露旧风险源增删改工具 |
| AC-13 | Web 入口 | 企业详情页不再显示旧「风险源」Tab |
| AC-14 | 移动端入口 | 移动端不再存在旧 `risk-sources` 路由和旧列表页 |
| AC-15 | 兼容层 | 旧 `risk_sources` 表仍存在，旧 CRUD API 仍可调用但无前端入口 |
| AC-16 | 回归 | 后端 pytest、前端 tsc、vitest、Playwright 和构建均通过 |

## 11. 受影响文件

### 后端

- `backend/app/models/risk_management.py`：新增 `legacy_source_id`。
- `backend/db_migration_risk_source_consolidation.sql`：新增幂等迁移 SQL。
- `backend/app/services/risk_source_migration_service.py`：新增迁移服务。
- `backend/app/services/risk_stats_service.py`：新增统计服务。
- `backend/app/schemas/risk_management.py`：迁移 Schema。
- `backend/app/schemas/enterprise.py`：新增 `risk_events_count`。
- `backend/app/schemas/dashboard.py`：新增 `risk_event_count`。
- `backend/app/routers/risk_management.py`：迁移接口接入服务。
- `backend/app/routers/generation.py`：切换上下文。
- `backend/app/routers/external.py`：切换上下文并修复参数。
- `backend/app/routers/risk_assessment.py`：前置检查切换。
- `backend/app/services/risk_assessment_service.py`：委托新上下文。
- `backend/app/routers/enterprises.py`：统计切换。
- `backend/app/routers/dashboard.py`：统计切换。
- `backend/app/services/chat_dispatch.py`：读取切换、移除写工具。
- `backend/app/routers/chat.py`：工具定义更新。
- `backend/app/services/risk_context_builder.py`：补齐提示词兼容字段。

### 前端

- `frontend/src/services/riskManagementService.ts`：新增迁移预览和执行。
- `frontend/src/components/enterprise/RiskMigrationWizard.tsx`：重写执行流程。
- `frontend/src/pages/Enterprise/RiskManagementTab.tsx`：挂载迁移入口。
- `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`：移除旧 Tab。
- `frontend/src/pages/Enterprise/EnterpriseListPage.tsx`：统计列切换。
- `frontend/src/pages/Dashboard/DashboardPage.tsx`：统计字段切换。
- `frontend/src/types/enterprise.ts`：新增 `risk_events_count`。
- `frontend/src/types/dashboard.ts`：新增 `risk_event_count`。
- `frontend/src/mobile/screens/RiskManagementListScreen.tsx`：新增。
- `frontend/src/mobile/screens/EnterpriseDetailScreen.tsx`：切换。
- `frontend/src/mobile/screens/PlanCreateScreen.tsx`：切换。
- `frontend/src/mobile/routes.tsx`：路由切换。

## 12. 风险与假设

| 风险 | 缓解措施 |
|---|---|
| 旧数据质量差，名称是位置而非事故类型 | AI 建议优先；兜底使用旧名称；用户可在向导中修改 |
| 旧控制措施为自由文本 | 按常见分隔符拆分，无法拆分时作为一条措施保留 |
| 旧记录缺少可能性或严重性 | 默认 `l=3`、`s=3` |
| AI 预览不稳定 | 预览失败时保留默认映射，不阻塞迁移 |
| 统计口径迁移引入回归 | 新增独立 `risk_stats_service`，用单测覆盖对象事件和单元事件计数 |
| 旧 Tab 提前下线导致数据缺失 | 只有在阶段 2 完成、迁移验证通过后才进入阶段 3 |
| 旧表数据未来不再维护 | 保留备份 SQL 和 deprecated API，不做物理删除 |

## 13. 假设说明

- 每个旧风险源在迁移时生成一个 `RiskEvent`，不强行拆分为多个事件。
- 新迁移对象统一放入默认楼层。
- 风险等级优先使用系统或企业的 LS 方法配置重新计算，保证与新五层 CRUD 口径一致。
- 旧 `risk_sources_count`、`risk_source_count` 字段名暂时保留，仅用于兼容和迁移对照。
