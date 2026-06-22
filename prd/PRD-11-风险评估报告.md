# PRD-11：风险评估报告模块

> **版本**：1.0 | **创建日期**：2026-06-07 | **依赖**：PRD-00, PRD-01, PRD-02, PRD-04

---

## 1. 模块概述

### 1.1 法规背景

根据《生产安全事故应急预案管理办法》（应急管理部令第2号）第十条：

> 编制应急预案前，编制单位应当进行事故风险辨识、评估和应急资源调查。

风险评估报告是应急预案编制的**法定前置文件**。系统已支持风险源数据录入，但缺少将录入数据转化为正式《风险评估报告》的功能。本模块补齐这一环节。

### 1.2 模块定义

基于企业在 isk_sources 表中已录入的风险源数据，调用 AI 大模型自动生成符合规范格式的**事故风险评估报告**。报告内容涵盖：风险辨识、风险等级评估（L×S 矩阵）、重大风险分析、管控措施汇总、风险管控建议。生成后可在线预览、导出为 .docx，并作为预案 AI 生成的核心上下文数据源。

### 1.3 与其他模块的关系

`
企业数据录入(PRD-02) → 风险评估报告(PRD-11) ──┐
                                               ├→ 应急预案生成(PRD-04/05)
企业数据录入(PRD-02) → 应急资源调查报告(PRD-12) ─┘
`

- **上游**：PRD-02 的 isk_sources、enterprises、surrounding_info 数据
- **下游**：PRD-04 的 AI 预案生成将引用报告的结构化摘要替代原始数据注入
- **并行**：PRD-12 应急资源调查报告（同一前置阶段）

---

## 2. 数据模型

### 2.1 risk_assessment_reports 表

`sql
CREATE TABLE risk_assessment_reports (
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

CREATE INDEX idx_risk_reports_enterprise ON risk_assessment_reports(enterprise_id);
CREATE UNIQUE INDEX idx_risk_reports_enterprise_unique
    ON risk_assessment_reports(enterprise_id)
    WHERE status != 'draft';
`

**设计说明**：
- 每个企业只保留一份有效的风险评估报告（通过唯一索引保证）
- content 存储 Markdown 格式的完整报告正文
- summary 存储结构化摘要（供预案 AI 生成时注入）
- 重新生成时覆盖旧记录

### 2.2 summary JSONB 结构

`json
{
  "risk_source_count": 12,
  "risk_level_distribution": {
    "重大": 2,
    "较大": 3,
    "一般": 4,
    "低": 3
  },
  "top_risks": [
    {
      "name": "储罐区火灾爆炸",
      "category": "火灾/爆炸",
      "risk_level": "重大",
      "likelihood": "高",
      "severity": "高",
      "location": "储罐区",
      "key_control_measures": "可燃气体报警、防火堤、泡沫灭火系统"
    }
  ],
  "risk_by_category": {
    "火灾": 3,
    "爆炸": 2,
    "触电": 2,
    "中毒窒息": 1,
    "机械伤害": 2,
    "高处坠落": 1,
    "物体打击": 1
  },
  "key_findings": [
    "储罐区和生产车间为公司两大重大风险区域",
    "触电风险广泛分布于各车间配电设施",
    "中毒窒息风险集中在有限空间作业环节"
  ],
  "overall_assessment": "企业整体风险等级为较大，其中储罐区火灾爆炸和生产车间化学品泄漏为重大风险，需重点管控。",
  "generated_at": "2026-06-07T10:00:00Z"
}
`

### 2.3 Pydantic Schema

`python
# schemas/risk_assessment.py

class RiskAssessmentGenerateRequest(BaseModel):
    custom_instruction: str | None = None

class RiskAssessmentSummary(BaseModel):
    risk_source_count: int = 0
    risk_level_distribution: dict[str, int] = {}
    top_risks: list[dict] = []
    risk_by_category: dict[str, int] = {}
    key_findings: list[str] = []
    overall_assessment: str = ""

class RiskAssessmentReportResponse(BaseModel):
    id: UUID
    enterprise_id: UUID
    title: str
    content: str
    summary: RiskAssessmentSummary
    status: str
    generated_by: str
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime

class RiskAssessmentPreviewResponse(BaseModel):
    report_id: UUID
    title: str
    html: str
`

---

## 3. AI 提示词设计

### 3.1 系统级提示词

`
你是一位持有国家注册安全工程师资格的风险评估专家，
熟悉《生产过程危险和有害因素分类与代码》(GB/T 13861) 和
《企业职工伤亡事故分类》(GB 6441) 的全部要求。

你的任务是根据企业提供的风险源数据，撰写一份完整、专业、合规的
《事故风险评估报告》。报告应使用正式的公文语言，内容结合企业实际，
不得编造不存在的信息。
`

### 3.2 报告章节结构

报告按以下 6 章结构生成（Markdown 格式）：

1. **评估目的与依据** — 评估目的、法律法规和标准依据
2. **企业基本情况** — 生产经营特点、厂区布局、周边环境
3. **风险辨识** — 按 GB/T 13861 的分类辨识危险有害因素，按 GB 6441 列出事故类型
4. **风险等级评估** — L×S 风险矩阵法，逐项评估结果，重大风险专项分析
5. **现有管控措施评价** — 工程/管理/个体防护/应急措施的充分性评价
6. **风险评估结论与建议** — 综合结论、改进建议

### 3.3 上下文构建

`python
async def build_risk_assessment_context(enterprise_id: UUID) -> dict:
    enterprise = await get_enterprise(enterprise_id)
    risk_sources = await get_risk_sources(enterprise_id)
    risk_order = {"重大": 0, "较大": 1, "一般": 2, "低": 3}
    risk_sources.sort(key=lambda r: risk_order.get(r.risk_level, 99))
    return {
        "enterprise": {
            "name": enterprise.name,
            "industry": enterprise.industry,
            "address": enterprise.address,
            "employee_count": enterprise.employee_count,
            "business_scope": enterprise.business_scope,
            "building_overview": enterprise.building_overview,
            "surrounding_info": enterprise.surrounding_info,
        },
        "risk_sources": [
            {
                "name": rs.name,
                "categories": rs.categories,
                "location": rs.location,
                "description": rs.description,
                "likelihood": rs.likelihood,
                "severity": rs.severity,
                "risk_level": rs.risk_level,
                "control_measures": rs.control_measures,
            }
            for rs in risk_sources
        ],
    }
`

---

## 4. API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/enterprises/{id}/risk-assessment | 获取已生成的报告 |
| POST | /api/v1/enterprises/{id}/risk-assessment/generate | 生成/重新生成报告（SSE 流式） |
| GET | /api/v1/enterprises/{id}/risk-assessment/preview | 报告预览（HTML） |
| GET | /api/v1/enterprises/{id}/risk-assessment/export | 导出 .docx |
| GET | /api/v1/enterprises/{id}/risk-assessment/summary | 仅获取结构化摘要 |

### 4.1 POST generate（SSE 流式）

`
POST /api/v1/enterprises/{id}/risk-assessment/generate
Body（可选）: { "custom_instruction": "请重点分析储罐区的火灾爆炸风险" }
`

**前置检查**：
- 企业存在且属于当前用户（否则 20001）
- 企业至少 1 条风险源（否则 20002）
- 用户已配置 AI 模型（否则 40001）
- 无正在进行的生成任务（否则 20003）

**SSE 事件类型**：
`
data: {"type": "progress", "message": "正在生成...", "stage": "risk_identification"}
data: {"type": "chunk", "content": "..."}
data: {"type": "done", "report_id": "uuid", "title": "..."}
data: {"type": "error", "message": "..."}
`

### 4.2 报告唯一性

每个企业仅保留一份有效报告（唯一索引保证）。重新生成时直接覆盖旧记录。

### 4.3 摘要提取

生成完成后，调用一次轻量 LLM 请求从完整报告中提取结构化 summary JSON。

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

### 5.2 预案生成上下文整合

在预案 AI 生成时（PRD-04），不再直接注入原始 isk_sources JSON，而是注入风险评估报告摘要：

`python
# 修改 generation.py 的 _collect_enterprise_data 或 PromptBuilder
risk_summary = await get_risk_assessment_summary(enterprise_id)
context["risk_assessment"] = risk_summary  # 替代原来的 risk_sources 列表
`

---

## 6. 前端页面

### 6.1 入口

在企业详情页（EnterpriseDetailPage.tsx）新增第 5 个 Tab：「风险评估」。

### 6.2 三种状态

**未生成**：空状态提示 + 「一键生成风险评估报告」按钮（无风险源时按钮禁用并提示先录入）

**生成中**：进度条 + 实时流式渲染的 Markdown 内容 + 「取消生成」按钮

**已完成**：工具栏（标题、时间、重新生成、导出 Word、预览） + A4 纸样式的 Markdown 渲染正文

### 6.3 报告预览页

路由：/enterprises/:id/risk-assessment/preview
全屏模拟 Word 外观的 HTML 渲染。

---

## 7. 后端实现清单

| 文件 | 操作 | 说明 |
|------|------|------|
| ackend/app/models/risk_assessment.py | **新增** | RiskAssessmentReport ORM 模型 |
| ackend/app/schemas/risk_assessment.py | **新增** | Pydantic Schema |
| ackend/app/routers/risk_assessment.py | **新增** | 5 个 API 端点 |
| ackend/app/services/risk_assessment_service.py | **新增** | 上下文构建 + 摘要提取 |
| ackend/app/main.py | 修改 | 注册路由 |
| ackend/app/routers/generation.py | 修改 | 预案生成引用摘要替代原始数据 |

### 前端实现清单

| 文件 | 操作 | 说明 |
|------|------|------|
| rontend/src/types/riskAssessment.ts | **新增** | TS 类型定义 |
| rontend/src/services/riskAssessmentService.ts | **新增** | API 调用 + SSE 消费 |
| rontend/src/pages/Enterprise/RiskAssessmentTab.tsx | **新增** | Tab 组件 |
| rontend/src/pages/Enterprise/RiskAssessmentPreview.tsx | **新增** | 预览页 |
| rontend/src/pages/Enterprise/EnterpriseDetailPage.tsx | 修改 | 新增 Tab |

### 数据库迁移

- 创建 isk_assessment_reports 表 + 索引

---

## 8. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC-R01 | 无风险源时拒绝生成 | 自动化：POST generate → 20002 |
| AC-R02 | 有风险源时成功启动流式生成 | E2E：点击生成 → 实时显示内容 |
| AC-R03 | 生成完成后报告持久化 | 自动化：生成完成 → GET → content 非空 |
| AC-R04 | summary 正确提取 | 自动化：GET summary → 各字段数值匹配风险源数据 |
| AC-R05 | 重新生成覆盖旧报告 | 自动化：v1 → v2 → GET → 内容为 v2 |
| AC-R06 | 导出 .docx 格式正确 | 人工：下载 .docx 检查格式 |
| AC-R07 | 预览 HTML 正常 | E2E：预览页展示完整报告 |
| AC-R08 | 生成中拒绝重复请求 | 自动化：并发 POST generate → 第二次返回 20003 |
| AC-R09 | 预案生成引用风险摘要 | 自动化：生成预案章节 → prompt 含 risk_assessment |

---

## 9. 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-06-07 | 初始版本 |
