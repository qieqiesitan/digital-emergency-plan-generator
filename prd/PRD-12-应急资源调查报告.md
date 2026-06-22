# PRD-12：应急资源调查报告模块

> **版本**：1.0 | **创建日期**：2026-06-07 | **依赖**：PRD-00, PRD-01, PRD-02, PRD-04

---

## 1. 模块概述

### 1.1 法规背景

根据《生产安全事故应急预案管理办法》（应急管理部令第2号）第十条：

> 编制应急预案前，编制单位应当进行事故风险辨识、评估和应急资源调查。

应急资源调查报告是应急预案编制的**法定前置文件**。系统已支持应急资源数据录入（内部物资 + 外部救援力量），但缺少将录入数据转化为正式《应急资源调查报告》的功能。本模块补齐这一环节。

### 1.2 模块定义

基于企业在 emergency_resources 表中已录入的应急资源数据和 isk_assessment_reports 中的风险评估结论，调用 AI 大模型自动生成符合规范格式的**应急资源调查报告**。报告内容涵盖：内部资源清点、外部救援力量评估、资源需求-能力差距分析、资源补充建议。生成后可在线预览、导出为 .docx，并作为预案 AI 生成的核心上下文数据源。

### 1.3 与其他模块的关系

`
企业数据录入(PRD-02) → 风险评估报告(PRD-11) ──┐
                                               ├→ 应急预案生成(PRD-04/05)
企业数据录入(PRD-02) → 应急资源调查报告(PRD-12) ─┘
`

- **上游**：PRD-02 的 emergency_resources、enterprises、org_structure 数据；PRD-11 的风险评估结论
- **下游**：PRD-04 的 AI 预案生成将引用调查报告的结构化摘要
- **并行**：PRD-11 风险评估报告（建议先生成风险评估，再生成资源调查）

---

## 2. 数据模型

### 2.1 resource_investigation_reports 表

`sql
CREATE TABLE resource_investigation_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'generating', 'completed')),
    generated_by VARCHAR(20) NOT NULL DEFAULT 'ai'
        CHECK (generated_by IN ('ai', 'manual')),
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_resource_reports_enterprise ON resource_investigation_reports(enterprise_id);
CREATE UNIQUE INDEX idx_resource_reports_enterprise_unique
    ON resource_investigation_reports(enterprise_id)
    WHERE status != 'draft';
`

**设计说明**：表结构与 isk_assessment_reports 完全对称，统一设计模式。每个企业仅保留一份有效报告。

### 2.2 summary JSONB 结构

`json
{
  "internal_resource_count": 25,
  "external_resource_count": 5,
  "internal_by_category": {
    "消防设施": 8,
    "急救物资": 4,
    "防护装备": 5,
    "通讯设备": 3,
    "照明设备": 2,
    "破拆工具": 2,
    "侦检设备": 1,
    "堵漏器材": 0
  },
  "external_by_category": {
    "消防队": 1,
    "医院": 2,
    "公安机关": 1,
    "安监部门": 1,
    "环保部门": 0
  },
  "resource_gaps": [
    {
      "category": "堵漏器材",
      "needed": "化学品类堵漏工具",
      "reason": "储罐区化学品泄漏风险需配备专用堵漏器材",
      "severity": "高"
    },
    {
      "category": "侦检设备",
      "needed": "多气体检测仪",
      "reason": "有限空间作业需配备多种气体同时检测设备",
      "severity": "中"
    }
  ],
  "key_findings": [
    "消防设施和急救物资配备较为充足，基本满足日常应急需要",
    "堵漏器材和侦检设备存在明显短板，需优先补充",
    "周边最近消防站距离 8km，响应时间约 15 分钟",
    "外部协议单位联系方式已确认，均为有效"
  ],
  "overall_assessment": "企业应急资源整体满足一般事故应急需求，但针对储罐区重大风险场景，堵漏器材和专用防护装备存在缺口，建议在 30 日内完成补充。",
  "generated_at": "2026-06-07T10:30:00Z"
}
`

### 2.3 Pydantic Schema

`python
# schemas/resource_investigation.py

class ResourceInvestigationGenerateRequest(BaseModel):
    custom_instruction: str | None = None

class ResourceGap(BaseModel):
    category: str
    needed: str
    reason: str
    severity: str  # 高/中/低

class ResourceInvestigationSummary(BaseModel):
    internal_resource_count: int = 0
    external_resource_count: int = 0
    internal_by_category: dict[str, int] = {}
    external_by_category: dict[str, int] = {}
    resource_gaps: list[ResourceGap] = []
    key_findings: list[str] = []
    overall_assessment: str = ""

class ResourceInvestigationReportResponse(BaseModel):
    id: UUID
    enterprise_id: UUID
    title: str
    content: str
    summary: ResourceInvestigationSummary
    status: str
    generated_by: str
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime

class ResourceInvestigationPreviewResponse(BaseModel):
    report_id: UUID
    title: str
    html: str
`

---

## 3. AI 提示词设计

### 3.1 系统级提示词

`
你是一位持有国家注册安全工程师资格的应急管理专家，
熟悉《应急物资分类及编码》(GB/T 38565) 和
《生产安全事故应急预案管理办法》的全部要求。

你的任务是根据企业提供的应急资源数据、风险评估结论和组织架构信息，
撰写一份完整、专业、合规的《应急资源调查报告》。
报告应使用正式的公文语言，内容结合企业实际，不得编造不存在的信息。

特别注意：
1. 对照企业的风险类型和等级，评估现有应急资源的充分性和适用性
2. 识别资源缺口时，要具体说明：缺什么、为什么缺、建议补充什么
3. 对周边可调用的外部资源，评估其响应时间和可达性
`

### 3.2 报告章节结构

报告按以下 6 章结构生成（Markdown 格式）：

1. **调查目的与依据** — 调查目的、法律法规依据
2. **企业基本情况与风险概况** — 企业概况 + 引用风险评估结论（主要风险类型和等级）
3. **内部应急资源调查** — 按类别逐一清点：消防设施、急救物资、防护装备、通讯设备、照明设备、破拆工具、侦检设备、堵漏器材
4. **外部救援资源调查** — 周边消防队、医院、公安机关、安监部门、环保部门的名称、距离、联系方式、协议情况
5. **应急资源需求与能力评估** — 对照风险场景，评估各类资源的充足性，识别资源缺口
6. **调查结论与建议** — 综合评估结论、资源补充计划、建议采购清单

### 3.3 上下文构建

`python
async def build_resource_investigation_context(enterprise_id: UUID) -> dict:
    enterprise = await get_enterprise(enterprise_id)
    resources = await get_resources(enterprise_id)
    internal = [r for r in resources if not r.is_external]
    external = [r for r in resources if r.is_external]

    # 尝试获取风险评估结论
    risk_summary = None
    risk_report = await get_risk_assessment_report(enterprise_id)
    if risk_report and risk_report.status == "completed":
        risk_summary = risk_report.summary

    return {
        "enterprise": {
            "name": enterprise.name,
            "industry": enterprise.industry,
            "address": enterprise.address,
            "employee_count": enterprise.employee_count,
            "building_overview": enterprise.building_overview,
            "org_structure": enterprise.org_structure,
        },
        "internal_resources": [
            {
                "category": r.category,
                "name": r.name,
                "specification": r.specification,
                "quantity": r.quantity,
                "unit": r.unit,
                "location": r.location,
                "responsible_person": r.responsible_person,
                "contact_phone": r.contact_phone,
            }
            for r in internal
        ],
        "external_resources": [
            {
                "category": r.category,
                "name": r.name,
                "address": r.external_address,
                "distance_km": r.external_distance_km,
                "contact_phone": r.contact_phone,
                "responsible_person": r.responsible_person,
            }
            for r in external
        ],
        "risk_conclusion": risk_summary.get("overall_assessment", "尚未完成风险评估")
            if risk_summary else "尚未完成风险评估",
        "top_risks": risk_summary.get("top_risks", []) if risk_summary else [],
    }
`

---

## 4. API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/enterprises/{id}/resource-investigation | 获取已生成的报告 |
| POST | /api/v1/enterprises/{id}/resource-investigation/generate | 生成/重新生成报告（SSE 流式） |
| GET | /api/v1/enterprises/{id}/resource-investigation/preview | 报告预览（HTML） |
| GET | /api/v1/enterprises/{id}/resource-investigation/export | 导出 .docx |
| GET | /api/v1/enterprises/{id}/resource-investigation/summary | 仅获取结构化摘要 |

### 4.1 POST generate（SSE 流式）

`
POST /api/v1/enterprises/{id}/resource-investigation/generate
Body（可选）: { "custom_instruction": "请重点分析储罐区消防资源是否充足" }
`

**前置检查**：
- 企业存在且属于当前用户（否则 20001）
- 企业至少 1 条应急资源数据（否则 20004 "请先录入应急资源数据"）
- 用户已配置 AI 模型（否则 40001）
- 无正在进行的生成任务（否则 20005 "报告正在生成中"）

**SSE 事件类型**（与风险评估对称）：
`
data: {"type": "progress", "message": "正在清点内部资源...", "stage": "internal_survey"}
data: {"type": "chunk", "content": "..."}
data: {"type": "done", "report_id": "uuid", "title": "..."}
data: {"type": "error", "message": "..."}
`

**stage 枚举**：
- context_building — 构建上下文
- internal_survey — 内部资源清点
- external_survey — 外部资源评估
- gap_analysis — 需求-能力差距分析
- conclusion — 结论与建议

### 4.2 其他接口

与 PRD-11 风险评估报告完全对称：
- GET .../resource-investigation — 获取报告
- GET .../resource-investigation/preview — HTML 预览
- GET .../resource-investigation/export — 导出 .docx
- GET .../resource-investigation/summary — 结构化摘要

**导出文件名**：{企业名称}_应急资源调查报告.docx

---

## 5. 业务逻辑

### 5.1 报告状态流转

`
draft → generating → completed
  ↑        │              │
  └────────┘              │
  生成失败/中断            │
                           │
              重新生成 ────┘
`

### 5.2 与风险评估的联动

- 生成应急资源调查报告时，自动尝试获取该企业的风险评估报告
- 如果风险评估报告已生成（status = completed），将其结论和重大风险列表注入上下文
- 如果风险评估报告未生成，仍可生成资源调查报告，但会提示"建议先生成风险评估报告"
- **不做强制依赖**：用户可以独立生成任一报告

### 5.3 资源缺口分析逻辑

AI 根据以下规则识别资源缺口：
1. 对照 	op_risks 中每个重大/较大风险所需的典型应急资源
2. 逐项检查企业是否具备对应资源
3. 输出缺口清单：缺什么、为什么缺、建议补充什么

### 5.4 预案生成上下文整合

在预案 AI 生成时，同时注入风险评估摘要和资源调查摘要：

`python
# 修改 generation.py 的上下文构建
risk_summary = await get_risk_assessment_summary(enterprise_id)
resource_summary = await get_resource_investigation_summary(enterprise_id)
context["risk_assessment"] = risk_summary
context["resource_investigation"] = resource_summary
`

---

## 6. 前端页面

### 6.1 入口

在企业详情页（EnterpriseDetailPage.tsx）新增第 6 个 Tab：「应急资源调查」。

### 6.2 三种状态

**未生成**：
- 空状态提示 + 「一键生成应急资源调查报告」按钮
- 如无应急资源数据，按钮禁用并提示"请先在「应急资源」标签页录入至少一条资源"

**生成中**：
- 进度条 + 阶段文字 + 实时流式渲染内容 + 「取消生成」按钮

**已完成**：
- 顶部工具栏：标题、生成时间、重新生成、导出 Word、预览
- 正文：A4 纸样式的 Markdown 渲染报告
- 如资源调查报告引用了风险评估结论，顶部提示"本报告关联了风险评估结论"

### 6.3 报告预览页

路由：/enterprises/:id/resource-investigation/preview
全屏模拟 Word 文档外观。

### 6.4 仪表盘集成（可选 P1）

在工作台仪表盘添加"应急资源调查状态"卡片：
- 已完成：绿色 + "已完成" + 资源总数和缺口数
- 未生成：黄色 + "未完成" + "点击前往生成"

---

## 7. 后端实现清单

| 文件 | 操作 | 说明 |
|------|------|------|
| ackend/app/models/resource_investigation.py | **新增** | ResourceInvestigationReport ORM 模型 |
| ackend/app/schemas/resource_investigation.py | **新增** | Pydantic Schema |
| ackend/app/routers/resource_investigation.py | **新增** | 5 个 API 端点 |
| ackend/app/services/resource_investigation_service.py | **新增** | 上下文构建 + 摘要提取 |
| ackend/app/main.py | 修改 | 注册路由 |
| ackend/app/routers/generation.py | 修改 | 预案生成注入资源摘要 |
| ackend/app/models/__init__.py | 修改 | 导入新模型 |

### 前端实现清单

| 文件 | 操作 | 说明 |
|------|------|------|
| rontend/src/types/resourceInvestigation.ts | **新增** | TS 类型定义 |
| rontend/src/services/resourceInvestigationService.ts | **新增** | API 调用 + SSE 消费 |
| rontend/src/pages/Enterprise/ResourceInvestigationTab.tsx | **新增** | Tab 组件 |
| rontend/src/pages/Enterprise/ResourceInvestigationPreview.tsx | **新增** | 预览页 |
| rontend/src/pages/Enterprise/EnterpriseDetailPage.tsx | 修改 | 新增第 5、6 个 Tab |

### 数据库迁移

- 创建 esource_investigation_reports 表 + 索引

---

## 8. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC-S01 | 无资源数据时拒绝生成 | 自动化：POST generate → 20004 |
| AC-S02 | 有资源数据时成功启动流式生成 | E2E：点击生成 → 实时显示内容 |
| AC-S03 | 生成完成后报告持久化 | 自动化：生成完成 → GET → content 非空 |
| AC-S04 | summary 正确提取，含资源分类统计和缺口 | 自动化：GET summary → internal_by_category 数值匹配数据库 |
| AC-S05 | 重新生成覆盖旧报告 | 自动化：v1 → v2 → GET → content 为 v2 |
| AC-S06 | 导出 .docx 格式正确 | 人工：下载 .docx 检查格式 |
| AC-S07 | 预览 HTML 正常 | E2E：预览页展示完整报告 |
| AC-S08 | 生成中拒绝重复请求 | 自动化：并发 POST → 第二次返回 20005 |
| AC-S09 | 预案生成同时注入风险摘要和资源摘要 | 自动化：生成预案 → prompt 含 risk_assessment 和 resource_investigation |

---

## 9. 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-06-07 | 初始版本 |
