# 预案附图扩展（三档图 + 缺数据降级 + 占位符）— 设计规格

> **日期**：2026-08-08 | **状态**：设计中 | **依赖**：预案生成增强（2026-08-08-plan-generation-enhancement-design.md）

---

## 1. 概述

在现有「仅 Mermaid 流程图」的基础上，为应急预案正文增加三类附图：

1. **LLM 生成的 mermaid 图**（组织架构图、信息上报时序图、处置时间轴、演练甘特图）——扩展现有提示词与渲染管线。
2. **数据自动绘制的风险矩阵图（L×S）**——从风险分级管控数据直接生成 SVG，不依赖 LLM 画图。
3. **数据自动绘制的厂区平面疏散图**——复用四色工作台平面图/分区/风险点坐标，叠加疏散标注。

全程**不接生图模型**：mermaid 走现有本地渲染，矩阵/疏散图为代码绘制 SVG。

企业数据不足时采用**三级策略**：自动降级（缺数据的图不生成）→ 编辑页提示并引导补数据 → 数据补齐后一键补图；未生成图的位置保留**占位块**，并在质量校验中产生 warning。

---

## 2. 现状基础

| 组件 | 现状 |
|------|------|
| `mermaid_renderer.py` | `render_mermaid_svg`（Playwright + 本地 mermaid.min.js）→ SVG；`render_svg_to_png` → PNG |
| `generation.py` | `_pre_render_mermaid_svgs` 提取并渲染 mermaid，存 `PlanSection.mermaid_svgs`（hash→SVG） |
| `export.py` / `docx_template.py` | 已支持从 `mermaid_svgs` 取 SVG → PNG 插入 Word |
| `SECTION_DIAGRAM_TYPE_MAP` | 现有 flowchart/sequenceDiagram 章节映射 |
| 前端 `MermaidRenderer.tsx` | 渲染 `code.language-mermaid` 块与预渲染 SVG；sanitize 已修复全角括号兼容 |
| 企业组织架构 | `enterprise.org_structure`（OrgGroup[]：group_name/members[role/name/position/phone/responsibilities]） |
| 风险分级管控 | `RiskZone.floor_plan_polygon`（v2 多边形）、`RiskObject.location_x/y`（0-100）、`RiskEvent.likelihood/severity/risk_level` |
| 厂区平面图 | `EnterpriseFloor.floor_plan_url` / `enterprise.floor_plan_url`、canvas 尺寸、`canvas_texts` |
| 应急资源 | `EmergencyResource`（category/name/location 等，含消防/疏散类） |

**实测数据覆盖**（177 家企业）：org_structure 3 家、floor_plan_url 11 家、risk_events 35 个、risk_objects 15 个、zones 1038 个、floors 150 个、resources 49 条——数据丰富度差异大，降级机制是必要项。

---

## 3. 图类型与数据依赖

| 图 | key | 来源 | 依赖数据 | 缺数据行为 |
|----|-----|------|---------|-----------|
| 应急组织架构图 | `org_chart` | LLM 生成 mermaid（graph TD），注入 org_structure 为依据 | org_structure（可选） | 无数据→占位 |
| 信息上报时序图 | `report_sequence` | LLM 生成 mermaid（sequenceDiagram） | 无 | 不依赖数据 |
| 处置时间轴 | `response_timeline` | LLM 生成 mermaid（timeline） | 无 | 不依赖数据 |
| 演练/恢复甘特图 | `drill_gantt` | LLM 生成 mermaid（gantt） | 无 | 不依赖数据 |
| 风险矩阵图 | `risk_matrix` | 数据自动绘制 SVG | risk_events（L/S） | 无数据→占位 |
| 厂区平面疏散图 | `evacuation` | 数据自动绘制 SVG | 平面图/分区/风险点（至少一项） | 无数据→占位 |

### 3.1 章节映射（新增）

在 `SECTION_DIAGRAM_TYPE_MAP` 基础上扩展：

| 章节 | 现有图 | 新增图 |
|------|--------|--------|
| sec_3（应急组织机构及职责） | flowchart | + org_chart |
| sec_4_2（信息报告程序） | - | + report_sequence |
| sec_5（应急响应） | flowchart | + response_timeline |
| sec_9_1（培训与演练） | - | + drill_gantt |
| sec_2（事故风险描述） | - | + risk_matrix |
| onsite sec_3_3（人员疏散路线） | - | + evacuation |

---

## 4. 缺数据三级策略

### 4.1 自动降级

每个绘制器独立判断数据是否充足：

- `org_chart`：org_structure 非空（至少 1 组且 1 成员）才生成。
- `risk_matrix`：至少 1 个风险事件含有效 likelihood/severity 才生成。
- `evacuation`：存在 floor_plan_url 或至少 1 个带坐标的 zone/risk object 才生成；无底图但有坐标时输出纯 SVG 示意平面。
- LLM mermaid 图（时序/时间轴/甘特）：不依赖数据，始终尝试生成；LLM 输出为空则跳过。

数据不足的图不生成、不报错、不阻塞其余图与正文生成。

### 4.2 编辑页提示 + 跳转

`PlanEditorPage` 顶部提示条（Alert）：

> 「该企业缺 {缺失数据清单}，{N} 张图未生成」

按钮「去补数据」跳转：

- org_structure → 企业详情组织架构维护
- risk_events → 风险分级管控页
- 平面图/分区/风险点 → 四色工作台

### 4.3 一键补图

新增接口：

`POST /api/v1/plans/{plan_id}/diagrams/regenerate-missing`

逻辑：

1. 遍历预案章节，找出含「占位块」或缺失附图 key 的章节。
2. 仅重新生成这些附图（调用对应绘制器/LLM mermaid），不重跑正文。
3. 返回 `{regenerated: N, skipped: M, placeholders_remaining: K}`。

前端在「去补数据」跳转返回后提供「重新生成缺失附图」按钮。

---

## 5. 占位符

未生成图的位置写入**占位块**（HTML，存于章节 content 或单独字段，见 §6）：

```html
<div class="diagram-placeholder" data-diagram-key="risk_matrix"
     style="border:2px dashed #d9d9d9;border-radius:8px;padding:24px;text-align:center;color:#999;margin:16px 0;">
  <div style="font-size:14px;font-weight:500;color:#666;">【风险矩阵图】</div>
  <div style="font-size:12px;margin-top:8px;">待补充企业风险分级管控数据后生成</div>
</div>
```

规则：

- 占位块在数据缺失时写入 `diagram_svgs`（key 对应）或 content 末尾，保证编辑/导出可见。
- `plan_quality_service.check_plan` 增加规则：正文或 diagram_svgs 含 `diagram-placeholder` → warning「存在未生成的附图占位」。
- 导出 docx：占位块保留为文字占位（虚线框不导出，转为「【风险矩阵图】（待补充数据后生成）」文本行），避免交付空白。

---

## 6. 技术实现

### 6.1 存储

新增列（幂等迁移 `db_migration_plan_diagram_svgs.sql`）：

```sql
ALTER TABLE plan_sections
  ADD COLUMN IF NOT EXISTS diagram_svgs JSONB NOT NULL DEFAULT '{}';
```

结构：

```json
{
  "org_chart": {"svg": "<svg...>", "placeholder": false},
  "risk_matrix": {"placeholder": true, "reason": "missing_risk_events"}
}
```

### 6.2 后端绘制服务

新增 `backend/app/services/plan_diagram_service.py`：

- `build_org_chart_svg(org_structure) -> dict`：org_structure → mermaid graph TD 文本 → `render_mermaid_svg` → SVG；数据不足返回 placeholder。
- `build_risk_matrix_svg(risk_events) -> dict`：5×5 矩阵 SVG（横轴 L 1-5、纵轴 S 1-5，单元格按 risk_level 红/橙/黄/蓝着色，风险事件按 L/S 定位并标注名称）；数据不足返回 placeholder。
- `build_evacuation_svg(enterprise, floors, zones, objects, resources) -> dict`：0-100 坐标 → SVG 视口映射；底图（如有）→ 分区多边形 → 风险点 → 疏散箭头/集合点/消防设施标注；无底图输出示意平面；数据不足返回 placeholder。
- `make_placeholder(key, reason) -> dict`：统一占位结构。
- `regenerate_missing_diagrams(db, plan_id) -> dict`：供补图接口调用。

坐标映射约定：SVG 视口 1000×700（16:10），0-100 坐标线性映射；底图存在时按 `canvas_width/height` 等比例适配。

### 6.3 生成流程接入

`generation.py` 单章与批量生成在写库前调用统一后处理 `_attach_diagrams(s, plan_type, enterprise_data, risk_context, db)`：

1. 按章节 key 判断需要哪些图。
2. LLM mermaid 图：随正文提示词输出（§3.1 映射），沿用 `_pre_render_mermaid_svgs`。
3. 数据图：调 `plan_diagram_service` 对应 builder。
4. 结果合并写入 `s.diagram_svgs`。

`_collect_enterprise_data` 返回结构扩展：`risk_events`（L/S/level/name）、`floors`、`zones`、`objects`、`resources`（含消防/疏散类过滤）。

### 6.4 前端

- `MermaidRenderer.tsx` 扩展为同时展示 `diagram_svgs` 预渲染 SVG 与占位块（组件更名或扩展 props：`DiagramRenderer`，兼容现有调用）。
- `PlanEditorPage`：读章节 `diagram_svgs`，readOnly 时渲染图/占位；顶部缺数据提示条 + 跳转 + 「重新生成缺失附图」按钮。
- `types/plan.ts`：`PlanSection` 增加 `diagram_svgs`。

### 6.5 导出

- `export.py` / `docx_template.py`：读取 `diagram_svgs`，非 placeholder 的 SVG → PNG 插入；placeholder 转为文字行。
- 预览 HTML：内嵌 SVG 或占位块样式。

---

## 7. 文件清单

**后端**

| 文件 | 操作 |
|------|------|
| `backend/db_migration_plan_diagram_svgs.sql` | 新增 |
| `backend/app/models/enterprise.py` | PlanSection + diagram_svgs |
| `backend/app/services/plan_diagram_service.py` | 新增（3 builder + placeholder + regenerate） |
| `backend/app/routers/generation.py` | `_attach_diagrams`、提示词映射扩展、enterprise_data 扩展 |
| `backend/app/routers/plans.py` 或新 `backend/app/routers/diagrams.py` | `POST /plans/{id}/diagrams/regenerate-missing` |
| `backend/app/services/prompt_cache.py` | 新增图提示词模板（org/timeline/gantt/sequence） |
| `backend/app/services/plan_quality_service.py` | 占位 warning 规则 |
| `backend/app/routers/export.py` / `docx_template.py` | diagram_svgs 导出 |
| 测试：`test_plan_diagram_service.py`、`test_plan_diagrams_api.py` | 新增 |

**前端**

| 文件 | 操作 |
|------|------|
| `frontend/src/types/plan.ts` | PlanSection + diagram_svgs |
| `frontend/src/components/plan/MermaidRenderer.tsx` | 扩展为 DiagramRenderer（预渲染 SVG + 占位） |
| `frontend/src/pages/Plan/PlanEditorPage.tsx` | 缺数据提示条、跳转、补图按钮 |
| `frontend/src/services/planService.ts` 或新 service | regenerateMissingDiagrams |

---

## 8. 测试计划

- `plan_diagram_service`：org_chart（有/无数据）、risk_matrix（L/S 定位、无数据降级、SVG 合法）、evacuation（坐标映射、无底图示意、无数据降级）、placeholder 结构。
- 补图接口：占位章节补图、无占位幂等、返回计数。
- `plan_quality_service`：占位 warning。
- 导出：含 diagram_svgs 的 docx 含图、placeholder 转文字。
- 前端：DiagramRenderer 展示 SVG/占位、补图按钮交互。
- 回归：后端全量（容器 182+ 基线）、前端 tsc + vitest。

---

## 9. 自检记录

- [x] 无占位符/TODO/待定项。
- [x] 内部一致性：`diagram_svgs` 结构、key 命名（org_chart/report_sequence/response_timeline/drill_gantt/risk_matrix/evacuation）在存储、绘制器、前端、导出中一致。
- [x] 范围聚焦：仅新增附图能力，不改变正文生成与既有 mermaid 行为。
- [x] 模糊性消除：数据充分性判定、坐标映射、占位渲染、补图范围均写明具体行为。
