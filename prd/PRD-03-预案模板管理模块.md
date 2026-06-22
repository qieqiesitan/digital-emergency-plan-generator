# PRD-03：预案模板管理模块

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00

---

## 1. 模块概述

管理系统内置的三类预案模板（综合、专项、现场处置），每类模板严格遵循 **GB/T 29639-2020** 章节结构。模板定义了：章节层级、每节的属性（是否可 AI 生成、是否必填等）、AI 提示词模板。用户创建预案时绑定对应模板，系统按模板结构初始化预案的章节列表。

---

## 2. 模板结构定义

### 2.1 模板 JSON Schema

```json
{
  "plan_type": "comprehensive",
  "name": "生产安全事故综合应急预案",
  "standard": "GB/T 29639-2020",
  "version": "1.0.0",
  "sections": [
    {
      "key": "approval_page",
      "title": "批准页",
      "level": 0,
      "sort_order": 1,
      "ai_generatable": false,
      "user_editable": true,
      "required": true,
      "auto_fill": true,
      "auto_fill_source": "enterprise.name",
      "gb_requirement": "应急预案批准发布的相关信息，含批准人、审核人、编制人签字",
      "subsections": []
    },
    {
      "key": "general_principles",
      "title": "1. 总则",
      "level": 1,
      "sort_order": 2,
      "ai_generatable": false,
      "user_editable": true,
      "required": true,
      "auto_fill": false,
      "gb_requirement": "编制目的、编制依据、适用范围、应急预案体系、应急工作原则",
      "subsections": [
        {
          "key": "purpose",
          "title": "1.1 编制目的",
          "level": 2,
          "sort_order": 1,
          "ai_generatable": true,
          "user_editable": true,
          "required": true,
          "auto_fill": false,
          "gb_requirement": "简述应急预案编制的目的",
          "prompt_template": "请为 {{ enterprise.name }} 撰写《生产安全事故综合应急预案》'编制目的'章节...",
          "data_dependencies": ["enterprise.name", "enterprise.industry"],
          "subsections": []
        }
      ]
    }
  ]
}
```

### 2.2 章节属性说明

| 属性 | 类型 | 说明 |
|------|------|------|
| `key` | string | 唯一标识，蛇形命名，如 `general_principles` |
| `title` | string | 显示标题，含编号如 `1.1 编制目的` |
| `level` | int | 层级 0=封面级，1=一级标题，2=二级，3=三级 |
| `sort_order` | int | 同级排序 |
| `ai_generatable` | bool | 是否允许 AI 生成内容 |
| `user_editable` | bool | 是否允许用户手动编辑 |
| `required` | bool | 是否必填（导出时检查） |
| `auto_fill` | bool | 是否从企业数据自动填充 |
| `auto_fill_source` | str\|null | 自动填充的数据路径 |
| `gb_requirement` | str | GB/T 标准对该章节的内容要求 |
| `prompt_template` | str\|null | AI 生成的提示词模板（Jinja2） |
| `data_dependencies` | list[str] | 生成该章节需要注入的数据字段列表 |
| `subsections` | list | 子章节（递归相同结构） |

---

## 3. 三类预案章节结构

### 3.1 综合应急预案（comprehensive）

```
批准页                              (level=0, auto_fill)
1. 总则                             (level=1, 容器节点)
  1.1 编制目的                      (level=2, ai_generatable)
  1.2 编制依据                      (level=2, ai_generatable)
  1.3 适用范围                      (level=2, ai_generatable)
  1.4 应急预案体系                  (level=2, ai_generatable)
  1.5 应急工作原则                  (level=2, ai_generatable)
2. 事故风险描述                      (level=1, ai_generatable)
3. 应急组织机构及职责                (level=1, 容器节点)
  3.1 应急组织机构                  (level=2, auto_fill: org_structure)
  3.2 应急组织机构职责              (level=2, ai_generatable)
4. 预警与信息报告                    (level=1, 容器节点)
  4.1 预警                          (level=2, ai_generatable)
  4.2 信息报告                      (level=2, ai_generatable)
5. 应急响应                          (level=1, 容器节点)
  5.1 响应分级                      (level=2, ai_generatable)
  5.2 响应程序                      (level=2, ai_generatable)
  5.3 处置措施                      (level=2, ai_generatable)
  5.4 应急结束                      (level=2, ai_generatable)
6. 信息公开                          (level=1, ai_generatable)
7. 后期处置                          (level=1, ai_generatable)
8. 应急保障                          (level=1, 容器节点)
  8.1 通信与信息保障                (level=2, ai_generatable)
  8.2 应急队伍保障                  (level=2, ai_generatable)
  8.3 物资装备保障                  (level=2, ai_generatable)
  8.4 其他保障                      (level=2, ai_generatable)
9. 应急预案管理                      (level=1, 容器节点)
  9.1 培训                          (level=2, ai_generatable)
  9.2 演练                          (level=2, ai_generatable)
  9.3 修订                          (level=2, ai_generatable)
  9.4 备案                          (level=2, ai_generatable)
10. 附件                             (level=1, 容器节点)
  10.1 应急资源清单                 (level=2, auto_fill: emergency_resources)
  10.2 规范化格式文本               (level=2, user_editable)
  10.3 关键的路线标识和图纸         (level=2, user_editable)
  10.4 有关协议或备忘录             (level=2, user_editable)
```

**总计**：1 个 0 级 + 10 个 1 级 + 约 25 个 2 级章节

### 3.2 专项应急预案（special）

```
1. 适用范围                          (level=1, ai_generatable)
2. 应急组织机构及职责                (level=1, ai_generatable)
3. 响应启动                          (level=1, 容器节点)
  3.1 响应启动条件                  (level=2, ai_generatable)
  3.2 响应启动程序                  (level=2, ai_generatable)
4. 处置措施                          (level=1, ai_generatable)
5. 应急保障                          (level=1, ai_generatable)
```

**总计**：5 个 1 级 + 2 个 2 级章节。创建专项预案时需绑定具体事故类型。

### 3.3 现场处置方案（onsite）

```
1. 事故风险描述                      (level=1, ai_generatable)
2. 应急工作职责                      (level=1, ai_generatable)
3. 应急处置                          (level=1, 容器节点)
  3.1 应急处置程序                  (level=2, ai_generatable)
  3.2 应急处置措施                  (level=2, ai_generatable)
4. 注意事项                          (level=1, ai_generatable)
```

**总计**：4 个 1 级 + 2 个 2 级章节。

---

## 4. 数据模型

### 4.1 plan_templates 表

```sql
CREATE TABLE plan_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_type VARCHAR(20) NOT NULL CHECK (plan_type IN (''comprehensive'', ''special'', ''onsite'')),
    name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT ''1.0.0'',
    structure JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_templates_type_version ON plan_templates(plan_type, version);
```

### 4.2 模板与提示词的存储策略

- **模板结构**：存储在 `plan_templates.structure` (JSONB)
- **提示词内容**：存储在 `plan_templates.structure` 内各章节的 `prompt_template` 字段
- 系统预置模板在 `backend/data/templates/` 下以 JSON 文件维护，通过 seed 脚本导入数据库
- 提示词模板中的变量使用 `{{ enterprise.xxx }}`、`{{ risk_sources }}` 等 Jinja2 语法

### 4.3 Pydantic Schema

```python
class SectionTemplate(BaseModel):
    key: str
    title: str
    level: int
    sort_order: int
    ai_generatable: bool = False
    user_editable: bool = True
    required: bool = True
    auto_fill: bool = False
    auto_fill_source: str | None = None
    gb_requirement: str = ""
    prompt_template: str | None = None
    data_dependencies: list[str] = []
    subsections: list[''SectionTemplate''] = []

class PlanTemplateResponse(BaseModel):
    id: UUID
    plan_type: str
    name: str
    version: str
    structure: list[SectionTemplate]
    is_active: bool
```

---

## 5. API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/templates` | 模板列表 |
| GET | `/api/v1/templates/{id}` | 模板详情（含完整章节结构） |
| GET | `/api/v1/templates?plan_type=comprehensive` | 按类型筛选 |

**GET /templates 响应**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "plan_type": "comprehensive",
        "name": "生产安全事故综合应急预案",
        "version": "1.0.0",
        "is_active": true
      }
    ],
    "total": 3
  }
}
```

**GET /templates/{id} 响应**：
```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "plan_type": "comprehensive",
    "name": "生产安全事故综合应急预案",
    "version": "1.0.0",
    "structure": [
      {
        "key": "approval_page",
        "title": "批准页",
        "level": 0,
        ...
      },
      {
        "key": "general_principles",
        "title": "1. 总则",
        "level": 1,
        "subsections": [...]
      }
    ]
  }
}
```

**注意**：模板为系统预置数据，不提供用户创建/修改/删除接口（Phase 1）。Phase 2 可选支持用户自定义模板。

---

## 6. 提示词模板系统

### 6.1 系统级提示词

每次 AI 生成时自动前置注入，定义 AI 角色和行为规范：

```
你是一位持有国家注册安全工程师资格的专业应急预案编制专家，
熟悉GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》的全部要求。
你的任务是根据企业提供的实际信息，撰写符合国家标准、内容专业详实的应急预案章节。

写作要求：
1. 语言规范、专业，使用正式的公文体
2. 内容结合企业实际情况，不编造不存在的信息
3. 严格按照GB/T 29639-2020对应章节的要求撰写
4. 如企业某项信息缺失，使用占位符"【待补充】"标记
5. 直接输出章节正文，不要输出标题，不要附加说明
```

### 6.2 章节级提示词模板示例

**综合应急预案 — 1.1 编制目的**：

```
请撰写《生产安全事故综合应急预案》的"编制目的"章节。

企业基本信息：
- 企业名称：{{ enterprise.name }}
- 行业类型：{{ enterprise.industry }}
- 企业规模：{{ enterprise.employee_count }}人
- 经营范围：{{ enterprise.business_scope }}

GB/T 29639-2020 要求：
{{ section.gb_requirement }}

请输出"编制目的"章节正文（不含标题）：
```

**综合应急预案 — 5.3 处置措施**：

```
请撰写《生产安全事故综合应急预案》的"处置措施"章节。

企业基本信息：
{{ enterprise_context }}

企业主要风险源（按风险等级排序）：
{{ risk_sources_context }}

企业应急资源概况：
{{ resources_summary }}

组织架构：
{{ org_structure_summary }}

GB/T 29639-2020 要求：
针对可能发生的事故风险、事故危害程度和影响范围，制定相应的应急处置措施，
明确处置原则和具体要求。

要求：
1. 针对上述每个重大、较大风险源，分别说明处置措施
2. 处置措施要具体、可操作
3. 明确各应急小组在处置中的分工

请输出"处置措施"章节正文（不含标题）：
```

### 6.3 上下文构建方法

```python
class EnterpriseContextBuilder:
    """将企业数据构建为 AI 可读的 Markdown 上下文"""

    async def build_full_context(self, enterprise_id: UUID) -> str:
        """构建完整企业上下文"""
        enterprise = await self.get_enterprise(enterprise_id)
        risk_sources = await self.get_risk_sources(enterprise_id)
        resources = await self.get_resources(enterprise_id)

        context = f"""## 企业基本信息
- 名称：{enterprise.name}
- 地址：{enterprise.address}
- 行业：{enterprise.industry}
- 员工人数：{enterprise.employee_count}
- 建筑概况：{enterprise.building_overview}

## 风险源清单（共{len(risk_sources)}项）
{self._format_risk_sources(risk_sources)}

## 应急资源
{self._format_resources(resources)}

## 组织架构
{self._format_org_structure(enterprise.org_structure)}
"""
        return context
```

---

## 7. 模板种子数据导入

### 7.1 种子脚本

```python
# backend/app/data/seed_templates.py
import json
from pathlib import Path
from app.db.session import async_session
from app.models.plan_template import PlanTemplate

TEMPLATE_FILES = {
    "comprehensive": "comprehensive.json",
    "special": "special.json",
    "onsite": "onsite.json",
}

async def seed():
    async with async_session() as db:
        for plan_type, filename in TEMPLATE_FILES.items():
            path = Path(__file__).parent.parent.parent / "data" / "templates" / filename
            structure = json.loads(path.read_text(encoding="utf-8"))

            existing = await db.execute(
                select(PlanTemplate).where(
                    PlanTemplate.plan_type == plan_type,
                    PlanTemplate.is_system == True
                )
            )
            existing = existing.scalar_one_or_none()

            if existing:
                existing.structure = structure["sections"]
                existing.version = structure.get("version", "1.0.0")
            else:
                template = PlanTemplate(
                    plan_type=plan_type,
                    name=structure["name"],
                    version=structure.get("version", "1.0.0"),
                    structure=structure["sections"],
                    is_system=True,
                )
                db.add(template)

        await db.commit()
```

### 7.2 模板 JSON 文件示例片段

```json
{
  "name": "生产安全事故综合应急预案",
  "plan_type": "comprehensive",
  "standard": "GB/T 29639-2020",
  "version": "1.0.0",
  "sections": [
    {
      "key": "approval_page",
      "title": "批准页",
      "level": 0,
      ...
    }
  ]
}
```

---

## 8. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC21 | 获取三类模板列表 | 自动化：GET /templates → 返回 3 条 |
| AC22 | 模板详情含完整章节结构 | 自动化：GET /templates/{id} → structure 非空，含 subsections |
| AC23 | 按 plan_type 筛选模板 | 自动化：GET ?plan_type=comprehensive → 返回 1 条 |
| AC24 | 种子数据正确导入 | 自动化：检查数据库中三类模板的 structure 与 JSON 文件一致 |
| AC25 | 提示词模板变量替换正确 | 单元测试：传入 mock enterprise → prompt_template 渲染后含企业名 |
| AC26 | 创建预案时绑定模板 | 见 PRD-05 |
