# 预案生成增强 第 1 批（内容可信度）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现数据防幻觉护栏（企业字段缺失标「（待补充）」+ system prompt 禁止推断）与模板元数据落地（章节元数据入库、前端按元数据控制、组织架构自动填充）。

**架构：** 后端在 `PlanSection` 增加 4 个元数据字段并随模板创建复制；`generation.py::_collect_enterprise_data` 增加缺失标注，`prompt_cache.py` 追加护栏；新增 `POST /plans/{id}/sections/{key}/autofill` 接口从 `org_structure` 生成表格。前端编辑页与移动端章节树改用真实元数据控制 AI 按钮与自动填充按钮。

**技术栈：** FastAPI + SQLAlchemy async + PostgreSQL JSONB；React + TypeScript + Antd（桌面）/ React 移动端；pytest / vitest。

**规格：** `docs/superpowers/specs/2026-08-08-plan-generation-enhancement-design.md` 第 3.1、3.2 节

---

## 文件结构

**后端：**
- 修改 `backend/app/models/enterprise.py` — PlanSection 加 4 字段
- 新增 `backend/db_migration_plan_section_metadata.sql` — 章节元数据列迁移
- 修改 `backend/app/routers/plans.py` — `_create_sections_from_template`/`duplicate_plan` 复制元数据
- 修改 `backend/app/schemas/plan.py` — SectionResponse 加 4 字段
- 修改 `backend/app/routers/generation.py` — `_collect_enterprise_data` 缺失标注
- 修改 `backend/app/services/prompt_cache.py` — 数据真实性护栏
- 修改 `backend/app/routers/sections.py` — 新增 autofill 端点
- 新增 `backend/tests/test_plan_section_metadata.py`
- 新增 `backend/tests/test_plan_autofill.py`
- 修改 `backend/tests/test_generation_enterprise_data.py`

**前端：**
- 修改 `frontend/src/types/plan.ts` — PlanSection 加 4 字段
- 修改 `frontend/src/pages/Plan/PlanEditorPage.tsx` — 真实元数据、自动填充按钮
- 修改 `frontend/src/components/plan/SectionTree.tsx` — 真实 ai_generatable
- 修改 `frontend/src/components/plan/AIGenerateButton.tsx` — 自动填充入口（本批仅后端就绪后前端调用）
- 修改 `frontend/src/mobile/screens/PlanEditorScreen.tsx` — 元数据 + 自动填充
- 修改 `frontend/src/mobile/components/plan/ChapterTree.tsx` — ChapterNode 类型扩展
- 修改 `frontend/src/mobile/components/plan/AIGenerationSheet.tsx` — 章节过滤

---

### 任务 1：PlanSection 模型加元数据字段 + 迁移 SQL

**文件：**
- 修改：`backend/app/models/enterprise.py:157-172`（PlanSection 类）
- 新增：`backend/db_migration_plan_section_metadata.sql`
- 测试：`backend/tests/test_plan_section_metadata.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_section_metadata.py
from app.models.enterprise import PlanSection


def test_plan_section_has_metadata_columns():
    cols = {c.name for c in PlanSection.__table__.columns}
    assert {"ai_generatable", "auto_fill", "auto_fill_source", "data_dependencies"} <= cols


def test_plan_section_metadata_defaults():
    s = PlanSection(
        id="test", plan_project_id="p", section_key="sec_1",
        title="总则", level=1, sort_order=0,
    )
    assert s.ai_generatable is True
    assert s.auto_fill is False
    assert s.auto_fill_source is None
    assert s.data_dependencies == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_section_metadata.py -v`
预期：FAIL，`AttributeError: 'PlanSection' object has no attribute 'ai_generatable'`

- [ ] **步骤 3：实现模型字段**

```python
# backend/app/models/enterprise.py  PlanSection 类内追加：
    ai_generatable: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_fill: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_fill_source: Mapped[Optional[str]] = mapped_column(String(50))
    data_dependencies: Mapped[list] = mapped_column(JSONB, default=list)
```

- [ ] **步骤 4：新增迁移 SQL**

```sql
-- backend/db_migration_plan_section_metadata.sql
ALTER TABLE plan_sections
  ADD COLUMN IF NOT EXISTS ai_generatable BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS auto_fill BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS auto_fill_source VARCHAR(50),
  ADD COLUMN IF NOT EXISTS data_dependencies JSONB NOT NULL DEFAULT '[]';
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_section_metadata.py -v`
预期：PASS（2 passed）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/enterprise.py backend/db_migration_plan_section_metadata.sql backend/tests/test_plan_section_metadata.py
git commit -m "feat(plan): add section metadata columns (batch1)"
```

---

### 任务 2：模板元数据复制到章节

**文件：**
- 修改：`backend/app/routers/plans.py:39-57`（`_create_sections_from_template`）、`:177-192`（`duplicate_plan`）
- 测试：`backend/tests/test_plan_section_metadata.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_section_metadata.py 追加
from unittest.mock import MagicMock
from app.routers.plans import _create_sections_from_template


def test_create_sections_copies_metadata_recursively():
    db = MagicMock()
    structure = [{
        "key": "sec_3", "title": "应急组织", "level": 1, "sort_order": 0,
        "ai_generatable": True, "auto_fill": False, "auto_fill_source": None,
        "data_dependencies": [],
        "subsections": [{
            "key": "sec_3_4", "title": "紧急联系电话", "level": 2, "sort_order": 0,
            "ai_generatable": False, "auto_fill": True,
            "auto_fill_source": "org_structure", "data_dependencies": ["org_structure"],
            "subsections": [],
        }],
    }]
    _create_sections_from_template(db, "plan-1", structure)
    added = [c.args[0] for c in db.add.call_args_list]
    contact = next(s for s in added if s.section_key == "sec_3_4")
    assert contact.ai_generatable is False
    assert contact.auto_fill is True
    assert contact.auto_fill_source == "org_structure"
    assert contact.data_dependencies == ["org_structure"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_section_metadata.py::test_create_sections_copies_metadata_recursively -v`
预期：FAIL，`assert contact.ai_generatable is False` 处失败（当前默认 True）

- [ ] **步骤 3：实现元数据复制**

```python
# backend/app/routers/plans.py  _create_sections_from_template 内 section 构造：
        section = PlanSection(
            id=str(uuid4()),
            plan_project_id=plan_id,
            section_key=key,
            title=title,
            level=level,
            sort_order=sort_order,
            content=None,
            ai_generated=False,
            ai_generatable=item.get("ai_generatable", True),
            auto_fill=item.get("auto_fill", False),
            auto_fill_source=item.get("auto_fill_source"),
            data_dependencies=item.get("data_dependencies", []),
        )
```

- [ ] **步骤 4：duplicate_plan 复制元数据**

```python
# backend/app/routers/plans.py  duplicate_plan 内 ns 构造追加：
        ns = PlanSection(
            plan_project_id=dup.id, section_key=s.section_key,
            title=s.title, level=s.level, sort_order=s.sort_order,
            content=s.content, ai_generated=s.ai_generated,
            ai_generatable=s.ai_generatable, auto_fill=s.auto_fill,
            auto_fill_source=s.auto_fill_source,
            data_dependencies=s.data_dependencies,
        )
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_section_metadata.py -v`
预期：PASS（3 passed）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/plans.py backend/tests/test_plan_section_metadata.py
git commit -m "feat(plan): copy template metadata into sections (batch1)"
```

---

### 任务 3：SectionResponse schema 加字段

**文件：**
- 修改：`backend/app/schemas/plan.py:21-26`（SectionResponse）
- 测试：`backend/tests/test_plan_section_metadata.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_section_metadata.py 追加
from app.schemas.plan import SectionResponse


def test_section_response_has_metadata_fields():
    resp = SectionResponse(
        id="s1", section_key="sec_3_4", title="紧急联系电话", level=2,
        sort_order=0, content="", ai_generated=False,
        updated_at="2026-08-08T00:00:00",
        ai_generatable=False, auto_fill=True,
        auto_fill_source="org_structure", data_dependencies=["org_structure"],
    )
    assert resp.ai_generatable is False
    assert resp.auto_fill is True
    assert resp.auto_fill_source == "org_structure"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_section_metadata.py::test_section_response_has_metadata_fields -v`
预期：FAIL，`TypeError: SectionResponse.__init__() got an unexpected keyword argument 'ai_generatable'`

- [ ] **步骤 3：实现 schema 字段**

```python
# backend/app/schemas/plan.py  SectionResponse 追加：
    ai_generatable: bool = True
    auto_fill: bool = False
    auto_fill_source: str | None = None
    data_dependencies: list = []
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_section_metadata.py -v`
预期：PASS（4 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/schemas/plan.py backend/tests/test_plan_section_metadata.py
git commit -m "feat(plan): expose section metadata in API schema (batch1)"
```

---

### 任务 4：数据防幻觉护栏

**文件：**
- 修改：`backend/app/routers/generation.py:180-216`（`_collect_enterprise_data`）
- 修改：`backend/app/services/prompt_cache.py`（COMPLIANCE_BLOCK 追加护栏）
- 修改：`backend/tests/test_generation_enterprise_data.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_generation_enterprise_data.py 追加
def test_collect_enterprise_data_marks_missing_fields():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = None
    ent.industry = ""
    ent.business_scope = "生产"
    ent.employee_count = 100
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = None
    ent.legal_representative = ""
    ent.credit_code = None
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = ""
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""

    data = _collect_enterprise_data(ent, {"risk_sources": []}, [])
    assert data["address"] == "（待补充）"
    assert data["industry"] == "（待补充）"
    assert data["legal_representative"] == "（待补充）"
    assert data["business_scope"] == "生产"  # 非空值保持原样


def test_compliance_block_contains_truth_guard():
    from app.services.prompt_cache import COMPLIANCE_BLOCK
    assert "数据真实性护栏" in COMPLIANCE_BLOCK
    assert "禁止推断" in COMPLIANCE_BLOCK
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_generation_enterprise_data.py -v`
预期：FAIL，`assert data["address"] == "（待补充）"` 处失败（当前为 None）

- [ ] **步骤 3：实现缺失标注**

```python
# backend/app/routers/generation.py  _collect_enterprise_data 前新增辅助函数：
def _missing(v):
    """缺失字段统一标注，防止 LLM 编造。"""
    return v if v not in (None, "") else "（待补充）"


def _collect_enterprise_data(enterprise: Enterprise, risk_context: dict, resources: list) -> dict:
    return {
        "name": _missing(enterprise.name), "address": _missing(enterprise.address),
        "industry": _missing(enterprise.industry),
        "business_scope": _missing(enterprise.business_scope),
        "employee_count": enterprise.employee_count,
        "building_overview": _missing(enterprise.building_overview),
        "org_structure": enterprise.org_structure,
        "surrounding_info": _missing(enterprise.surrounding_info),
        "legal_representative": _missing(enterprise.legal_representative),
        "credit_code": _missing(enterprise.credit_code),
        "economic_type": _missing(enterprise.economic_type),
        "established_date": str(enterprise.established_date) if enterprise.established_date else None,
        "registered_capital": enterprise.registered_capital,
        "phone": _missing(enterprise.phone),
        "land_area": enterprise.land_area,
        "building_area": enterprise.building_area,
        "safety_officer": _missing(enterprise.safety_officer),
        "safety_standardization": _missing(enterprise.safety_standardization),
        "fire_approval": _missing(enterprise.fire_approval),
        "main_products": _missing(enterprise.main_products),
        "hazardous_chemicals": _missing(enterprise.hazardous_chemicals),
        "special_equipment": _missing(enterprise.special_equipment),
        "risk_sources": [
            {
                "categories": rs.get("categories", ""),
                "name": rs.get("name", ""),
                "location": rs.get("location", ""),
                "description": rs.get("description", ""),
                "risk_level": rs.get("risk_level", ""),
                "control_measures": rs.get("control_measures", ""),
                "zone": rs.get("zone", ""),
                "object": rs.get("object", ""),
                "unit": rs.get("unit", ""),
                "accident_type": rs.get("accident_type", ""),
                "triggers": rs.get("triggers", ""),
                "consequences": rs.get("consequences", ""),
            }
            for rs in risk_context.get("risk_sources", [])
        ],
        "emergency_resources": [
            {
                "category": r.category,
                "name": r.name,
                "specification": r.specification,
                "quantity": r.quantity,
                "unit": r.unit,
                "location": r.location,
            }
            for r in resources
        ],
    }
```

注意：`established_date`/`registered_capital`/`land_area`/`building_area`/`employee_count` 为数值/日期类型，不做字符串缺失标注（保持现有行为，JSON 序列化时 None 自然呈现），规格中已明确仅字符串/文本字段标注。

- [ ] **步骤 4：追加 system prompt 护栏**

```python
# backend/app/services/prompt_cache.py  COMPLIANCE_BLOCK 末尾追加：
COMPLIANCE_BLOCK = (
    "【术语标准与结构底线——必须严格遵守】\n"
    "1. 应急组织统一使用：应急救援指挥部、总指挥、副总指挥、应急救援小组、抢险救援组、疏散引导组、医疗救护组、通讯联络组、后勤保障组、警戒疏散组。\n"
    "2. 响应级别统一表述为III级/II级/I级响应。\n"
    "3. 信息报告必须包含七要素：事故发生时间、地点、单位名称、事故类型、伤亡人数、影响范围、已采取措施。\n"
    "4. 请直接输出章节正文内容，不要重复章节标题作为正文第一行。\n"
    "5. 【数据真实性护栏——必须严格遵守】\n"
    "   5.1 企业档案中以\"（待补充）\"标注的信息一律视为缺失，禁止推断、禁止编造。\n"
    "   5.2 严禁编造地址、法定代表人、联系电话、统一社会信用代码、注册资本等企业基本信息。\n"
    "   5.3 正文涉及缺失信息时，直接书写\"（待补充）\"，不得用其他文字替代。\n"
    "   5.4 全部正文内容必须以企业档案数据为唯一事实来源，不得引入档案之外的企业信息。"
)
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_generation_enterprise_data.py -v`
预期：PASS

- [ ] **步骤 6：全量回归**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过（无新增失败）

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/generation.py backend/app/services/prompt_cache.py backend/tests/test_generation_enterprise_data.py
git commit -m "feat(plan): add data hallucination guard rails (batch1)"
```

---

### 任务 5：autofill 接口

**文件：**
- 修改：`backend/app/routers/sections.py`
- 新增：`backend/tests/test_plan_autofill.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_autofill.py
from unittest.mock import MagicMock, AsyncMock
import pytest
from app.routers.sections import _render_org_structure_html


def test_render_org_structure_html_creates_tables():
    org = [{
        "group_name": "应急救援指挥部",
        "members": [
            {"name": "张三", "position": "总指挥", "phone": "13800000000", "responsibilities": "全面指挥"},
            {"name": "李四", "position": "副总指挥", "phone": "13900000000", "responsibilities": "协助指挥"},
        ],
    }]
    html = _render_org_structure_html(org)
    assert "应急救援指挥部" in html
    assert "张三" in html and "13800000000" in html
    assert "总指挥" in html
    assert "<table" in html


def test_render_org_structure_html_empty_members_skipped():
    org = [{"group_name": "空组", "members": []}]
    assert _render_org_structure_html(org) == ""
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_autofill.py -v`
预期：FAIL，`ImportError: cannot import name '_render_org_structure_html'`

- [ ] **步骤 3：实现渲染函数与端点**

```python
# backend/app/routers/sections.py 顶部导入 Enterprise：
from app.models.enterprise import PlanProject, PlanSection, Enterprise


def _render_org_structure_html(org_structure: list) -> str:
    """组织架构 → HTML 表格（每组一张表）。"""
    parts = []
    for g in org_structure or []:
        members = [m for m in g.get("members", []) if m.get("name")]
        if not members:
            continue
        rows = "".join(
            f"<tr><td>{i+1}</td><td>{m.get('name','')}</td><td>{m.get('position','')}</td>"
            f"<td>{m.get('phone','')}</td><td>{m.get('responsibilities','')}</td></tr>"
            for i, m in enumerate(members)
        )
        parts.append(
            f"<h4>{g.get('group_name','')}</h4>"
            f"<table><thead><tr><th>序号</th><th>姓名</th><th>职务</th>"
            f"<th>联系电话</th><th>职责</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return "\n".join(parts)


@router.post("/{plan_id}/sections/{section_key}/autofill", response_model=ApiResponse[SectionResponse])
async def autofill_section(plan_id: str, section_key: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "章节不存在")
    if not s.auto_fill:
        raise HTTPException(400, "该章节不支持自动填充")
    if s.auto_fill_source != "org_structure":
        raise HTTPException(400, "不支持的自动填充来源")

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    org = (ent.org_structure or []) if ent else []
    html = _render_org_structure_html(org)
    if not html:
        raise HTTPException(400, "请先维护企业组织架构")

    s.content = html
    s.ai_generated = False
    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=SectionResponse.model_validate(s))
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_autofill.py -v`
预期：PASS（2 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/sections.py backend/tests/test_plan_autofill.py
git commit -m "feat(plan): add org-structure autofill endpoint (batch1)"
```

---

### 任务 6：桌面端前端接入真实元数据 + 自动填充

**文件：**
- 修改：`frontend/src/types/plan.ts`（PlanSection）
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`
- 修改：`frontend/src/components/plan/SectionTree.tsx`
- 修改：`frontend/src/services/planService.ts`（新增 autofillSection）

- [ ] **步骤 1：类型与 API 扩展**

```typescript
// frontend/src/types/plan.ts  PlanSection 追加：
  ai_generatable: boolean;
  auto_fill: boolean;
  auto_fill_source: string | null;
  data_dependencies: string[];

// frontend/src/services/planService.ts 追加：
export async function autofillSection(planId: string, sectionKey: string): Promise<PlanSection> {
  const res = await api.post<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}/autofill`);
  return res.data.data;
}
```

- [ ] **步骤 2：PlanEditorPage 使用真实元数据**

```typescript
// frontend/src/pages/Plan/PlanEditorPage.tsx  删除硬编码 templateSections，改为：
  const templateSections: SectionTemplate[] = (sections || []).map((s) => ({
    key: s.section_key,
    title: s.title,
    level: s.level,
    sort_order: s.sort_order,
    ai_generatable: s.ai_generatable,
    user_editable: true,
    required: s.level <= 1,
    auto_fill: s.auto_fill,
    auto_fill_source: s.auto_fill_source,
    gb_requirement: "",
    prompt_template: null,
    data_dependencies: s.data_dependencies,
    subsections: [],
  }));
```

并在章节编辑区根据 `currentSection.auto_fill` 渲染自动填充按钮：

```typescript
// PlanEditorPage.tsx  章节操作区（AIGenerateButton 旁）：
          {currentSection.auto_fill && (
            <Button
              icon={<FileSyncOutlined />}
              loading={autofillMut.isPending}
              onClick={() => autofillMut.mutate(currentSection.section_key)}
            >
              自动填充
            </Button>
          )}
```

新增 mutation（`FileSyncOutlined` 需从 `@ant-design/icons` 导入）：

```typescript
  const autofillMut = useMutation({
    mutationFn: (key: string) => autofillSection(id!, key),
    onSuccess: () => {
      message.success("自动填充完成");
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
    },
    onError: (e: any) => message.error(e?.message || "自动填充失败"),
  });
```

- [ ] **步骤 3：AI 按钮按 ai_generatable 控制**

```typescript
// PlanEditorPage.tsx  AIGenerateButton 渲染条件：
          {currentSection.ai_generatable && (
            <AIGenerateButton ... />
          )}
```

- [ ] **步骤 4：SectionTree 使用真实 ai_generatable**

`SectionTree.tsx` 已从 props 读取 `tpl.ai_generatable`（🤖 标记），父级传入真实元数据后自动生效，无需改动组件内部。

- [ ] **步骤 5：类型检查与测试**

运行：`cd frontend && npx tsc -b`
预期：PASS，无类型错误

运行：`cd frontend && npx vitest run`
预期：现有用例全部通过

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/plan.ts frontend/src/pages/Plan/PlanEditorPage.tsx frontend/src/services/planService.ts
git commit -m "feat(plan): wire section metadata and autofill in web editor (batch1)"
```

---

### 任务 7：移动端接入真实元数据

**文件：**
- 修改：`frontend/src/mobile/screens/PlanEditorScreen.tsx`
- 修改：`frontend/src/mobile/components/plan/ChapterTree.tsx`
- 修改：`frontend/src/mobile/components/plan/AIGenerationSheet.tsx`

- [ ] **步骤 1：ChapterNode 类型扩展**

```typescript
// frontend/src/mobile/components/plan/ChapterTree.tsx
export interface ChapterNode {
  key: string;
  title: string;
  level: number;
  aiGeneratable: boolean;
  autoFill: boolean;
  required: boolean;
  children?: ChapterNode[];
}
```

- [ ] **步骤 2：PlanEditorScreen 构建真实元数据**

```typescript
// frontend/src/mobile/screens/PlanEditorScreen.tsx  chapters 构建处：
      const node: ChapterNode = {
        key: sec.section_key,
        title: `${sec.title}`,
        level: sec.level,
        aiGeneratable: sec.ai_generatable,
        autoFill: sec.auto_fill,
        required: sec.level === 0,
      };
```

- [ ] **步骤 3：AI 入口按 aiGeneratable 控制 + 自动填充按钮**

```typescript
// PlanEditorScreen.tsx  编辑态 NavBar rightActions：
        rightActions={selectedChapter?.aiGeneratable ? [{
          icon: <Sparkles size={22} />,
          label: "AI生成",
          onPress: handleAIGenerate,
        }] : []}
```

并在编辑区（工具栏上方）为 `selectedChapter?.autoFill` 渲染自动填充按钮，调用 `autofillSection`（从 `@/services/planService` 导入）：

```typescript
      {selectedChapter?.autoFill && (
        <button
          className="w-full h-10 bg-indigo-600 text-white text-body-sm font-medium"
          onClick={async () => {
            try {
              const sec = await autofillSection(planId!, selectedChapter!.key);
              setLocalContent(sec.content || "");
              autoSave(sec.content || "");
              showToast?.({ type: "success", message: "自动填充完成" });
            } catch (e: any) {
              showToast?.({ type: "error", message: e?.message || "自动填充失败" });
            }
          }}
        >
          自动填充
        </button>
      )}
```

- [ ] **步骤 4：AIGenerationSheet 章节过滤**

```typescript
// frontend/src/mobile/components/plan/AIGenerationSheet.tsx  chapters prop 由调用方过滤；
// PlanEditorScreen 打开 sheet 前仅传入 aiGeneratable 章节，组件内默认选中逻辑不变。
```

- [ ] **步骤 5：类型检查**

运行：`cd frontend && npx tsc -b`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/mobile/screens/PlanEditorScreen.tsx frontend/src/mobile/components/plan/ChapterTree.tsx frontend/src/mobile/components/plan/AIGenerationSheet.tsx
git commit -m "feat(plan): wire section metadata and autofill in mobile editor (batch1)"
```

---

### 任务 8：第 1 批收尾验证

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过

- [ ] **步骤 2：前端构建与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：全部通过

- [ ] **步骤 3：迁移 SQL 语法检查（可选，有 DB 时）**

运行：`psql -U postgres -d emergency_plan -f backend/db_migration_plan_section_metadata.sql`
预期：成功执行，列已存在时幂等

- [ ] **步骤 4：规格对照自检**

- [x] 3.1 缺失标注 + 护栏 → 任务 4
- [x] 3.2 模型字段/迁移 → 任务 1
- [x] 3.2 模板复制/duplicate → 任务 2
- [x] 3.2 schema → 任务 3
- [x] 3.2 autofill 接口 → 任务 5
- [x] 3.2 桌面端 → 任务 6
- [x] 3.2 移动端 → 任务 7
- [x] 验收标准测试 → 任务 1-7 对应步骤

- [ ] **步骤 5：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): batch1 final verification"
```
