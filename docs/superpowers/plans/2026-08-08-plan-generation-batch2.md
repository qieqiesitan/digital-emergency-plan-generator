# 预案生成增强 第 2 批（导出与版本）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现导出编号真实化（`plan_number`/`version_number` 落库、创建时自动生成、导出与签署页使用真实数据）与版本快照补全（纳入 `mermaid_svgs` 与风格参数、回滚一并恢复）。

**架构：** `PlanProject` 增加 `plan_number`/`version_number` 两列；`plans.py::create_plan` 调用 `_generate_plan_number` 自动生成；`export.py` 删除硬编码兜底并接入真实值与组织架构签署人；`versions.py` 快照结构扩展并在回滚时恢复图表与风格。

**技术栈：** FastAPI + SQLAlchemy async + PostgreSQL；python-docx（导出）；React + TypeScript。

**规格：** `docs/superpowers/specs/2026-08-08-plan-generation-enhancement-design.md` 第 3.3、3.4 节

---

## 文件结构

**后端：**
- 修改 `backend/app/models/enterprise.py` — PlanProject 加 2 字段
- 新增 `backend/db_migration_plan_number.sql` — 预案编号列迁移
- 修改 `backend/app/routers/plans.py` — `_generate_plan_number`、create_plan 自动编号
- 修改 `backend/app/schemas/plan.py` — PlanCreate/PlanResponse 加编号字段
- 修改 `backend/app/routers/export.py` — 真实编号、signers、删除硬编码兜底
- 修改 `backend/app/routers/versions.py` — 快照扩展、回滚恢复
- 修改 `backend/app/routers/generation.py` — 自动快照扩展（与 versions 一致）
- 新增 `backend/tests/test_plan_number.py`
- 新增 `backend/tests/test_plan_version_snapshot.py`

**前端：**
- 修改 `frontend/src/types/plan.ts` — PlanProject/PlanCreate 加编号字段
- 修改 `frontend/src/pages/Plan/PlanCreatePage.tsx` — 编号/版本号输入
- 修改 `frontend/src/services/planService.ts` — createPlan 参数

---

### 任务 1：PlanProject 模型加编号字段 + 迁移 SQL

**文件：**
- 修改：`backend/app/models/enterprise.py:137-155`（PlanProject 类）
- 新增：`backend/db_migration_plan_number.sql`
- 测试：`backend/tests/test_plan_number.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_number.py
from app.models.enterprise import PlanProject


def test_plan_project_has_number_columns():
    cols = {c.name for c in PlanProject.__table__.columns}
    assert {"plan_number", "version_number"} <= cols


def test_plan_number_generator():
    from app.routers.plans import _generate_plan_number
    assert _generate_plan_number("陕西宝岳科技有限公司", "comprehensive", 1) == "陕西宝岳-ZH-001"
    assert _generate_plan_number("甲公司", "special", 12) == "甲公司-ZX-012"
    assert _generate_plan_number("", "onsite", 3) == "企业-XC-003"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_number.py -v`
预期：FAIL，`KeyError: 'plan_number'` 或 `ImportError`（`_generate_plan_number` 未定义）

- [ ] **步骤 3：实现模型字段**

```python
# backend/app/models/enterprise.py  PlanProject 类内追加：
    plan_number: Mapped[Optional[str]] = mapped_column(String(100))
    version_number: Mapped[Optional[str]] = mapped_column(String(50))
```

- [ ] **步骤 4：新增迁移 SQL**

```sql
-- backend/db_migration_plan_number.sql
ALTER TABLE plan_projects
  ADD COLUMN IF NOT EXISTS plan_number VARCHAR(100),
  ADD COLUMN IF NOT EXISTS version_number VARCHAR(50);
```

- [ ] **步骤 5：实现编号生成函数**

```python
# backend/app/routers/plans.py  模块级新增：
PLAN_TYPE_CODE = {"comprehensive": "ZH", "special": "ZX", "onsite": "XC"}


def _generate_plan_number(enterprise_name: str, plan_type: str, seq: int) -> str:
    """生成预案编号：{企业前缀}-{类型码}-{三位序号}。"""
    prefix = (enterprise_name or "").replace(" ", "")[:4] or "企业"
    code = PLAN_TYPE_CODE.get(plan_type, "YA")
    return f"{prefix}-{code}-{seq:03d}"
```

- [ ] **步骤 6：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_number.py -v`
预期：PASS（3 passed）

- [ ] **步骤 7：Commit**

```bash
git add backend/app/models/enterprise.py backend/db_migration_plan_number.sql backend/tests/test_plan_number.py backend/app/routers/plans.py
git commit -m "feat(plan): add plan number columns and generator (batch2)"
```

---

### 任务 2：创建预案自动生成编号

**文件：**
- 修改：`backend/app/routers/plans.py:127-158`（create_plan）
- 修改：`backend/app/schemas/plan.py`（PlanCreate/PlanResponse）
- 测试：`backend/tests/test_plan_number.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_number.py 追加
def test_create_plan_schema_accepts_numbers():
    from app.schemas.plan import PlanCreate
    p = PlanCreate(
        enterprise_id="e1", plan_type="special", title="测试",
        accident_type="火灾", plan_number="自定义-001", version_number="A-2026-08",
    )
    assert p.plan_number == "自定义-001"
    assert p.version_number == "A-2026-08"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_number.py::test_create_plan_schema_accepts_numbers -v`
预期：FAIL，`TypeError: PlanCreate.__init__() got an unexpected keyword argument 'plan_number'`

- [ ] **步骤 3：schema 加字段**

```python
# backend/app/schemas/plan.py  PlanCreate 追加：
    plan_number: str | None = None
    version_number: str | None = None

# PlanResponse 追加：
    plan_number: str | None = None
    version_number: str | None = None
```

- [ ] **步骤 4：create_plan 自动生成编号**

```python
# backend/app/routers/plans.py  create_plan 整体改为：
@router.post("", response_model=ApiResponse[PlanResponse], status_code=201)
async def create_plan(data: PlanCreate, current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == data.enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent: raise HTTPException(404, "企业不存在")

    # 自动生成预案编号（前端未传时）
    plan_data = data.model_dump(exclude_none=True)
    if not plan_data.get("plan_number"):
        existing_count = (
            await db.execute(
                select(func.count()).select_from(PlanProject).where(
                    PlanProject.enterprise_id == data.enterprise_id,
                    PlanProject.plan_type == data.plan_type,
                )
            )
        ).scalar() or 0
        plan_data["plan_number"] = _generate_plan_number(ent.name, data.plan_type, existing_count + 1)
    if not plan_data.get("version_number"):
        plan_data["version_number"] = f"A-{datetime.now().year}-{datetime.now().month:02d}"

    # 继承用户默认风格（前端未传时，从DB直接获取）
    if plan_data.get("style_preference") is None:
        user_row = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
        if user_row and user_row.default_style_preference:
            plan_data["style_preference"] = user_row.default_style_preference
    p = PlanProject(user_id=current_user.id, **plan_data)
    db.add(p)
    await db.flush()

    # Initialize sections from active template
    tpl_result = await db.execute(
        select(PlanTemplate)
        .where(PlanTemplate.plan_type == data.plan_type, PlanTemplate.is_active == True)
        .order_by(PlanTemplate.version.desc())
        .limit(1)
    )
    template = tpl_result.scalar_one_or_none()
    if template and template.structure:
        _create_sections_from_template(db, p.id, template.structure)

    await db.commit()
    await db.refresh(p)
    return ApiResponse(data=_build_plan(p, ent.name))
```

注意：现有 create_plan 中有两处 PlanProject 构造分支（继承用户默认风格 / 直接构造），上述改造将其合并为一份 `plan_data` 后再构造，行为不变。需在 `plans.py` 顶部确认已导入 `from datetime import datetime`（`func` 与 `User` 已导入）。

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_number.py -v`
预期：PASS（4 passed）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/plans.py backend/app/schemas/plan.py backend/tests/test_plan_number.py
git commit -m "feat(plan): auto-generate plan number on create (batch2)"
```

---

### 任务 3：导出使用真实编号与签署页

**文件：**
- 修改：`backend/app/routers/export.py:214-305`（export_plan_docx）
- 测试：`backend/tests/test_plan_number.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_number.py 追加
def test_build_signers_from_org_structure():
    from app.routers.export import _build_signers_from_org
    org = [
        {"group_name": "指挥部", "members": [
            {"name": "张三", "position": "总指挥"},
            {"name": "", "position": "无姓名跳过"},
            {"name": "李四", "position": "副总指挥"},
        ]},
    ]
    signers = _build_signers_from_org(org)
    assert signers == [
        {"seq": 1, "name": "张三", "title": "总指挥"},
        {"seq": 2, "name": "李四", "title": "副总指挥"},
    ]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_number.py::test_build_signers_from_org_structure -v`
预期：FAIL，`ImportError: cannot import name '_build_signers_from_org'`

- [ ] **步骤 3：实现签署人构建函数**

```python
# backend/app/routers/export.py  模块级新增：
def _build_signers_from_org(org_structure: list | None) -> list[dict]:
    """组织架构 → 签署人列表（跳过无姓名成员）。"""
    signers = []
    for g in org_structure or []:
        for m in g.get("members", []):
            if m.get("name"):
                signers.append({"seq": len(signers) + 1, "name": m["name"], "title": m.get("position", "")})
    return signers
```

- [ ] **步骤 4：export_plan_docx 使用真实编号与签署页**

```python
# backend/app/routers/export.py  export_plan_docx 内，替换编号兜底：
    if not plan.plan_number or not plan.version_number:
        raise HTTPException(400, "请先设置预案编号与版本号")

    # 构建签署人
    signers = _build_signers_from_org(enterprise.org_structure or [])

    # 传入 generate_plan_docx：
        doc = await _asyncio_dbg.to_thread(
            generate_plan_docx,
            company_name=enterprise.name,
            plan_title=plan.title,
            plan_type=plan.plan_type,
            plan_number=plan.plan_number,
            version_number=plan.version_number,
            sections=sections_data,
            signers=signers or None,
        )
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_number.py -v`
预期：PASS

- [ ] **步骤 6：全量回归**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/export.py backend/tests/test_plan_number.py
git commit -m "feat(plan): use real plan number and signers in export (batch2)"
```

---

### 任务 4：版本快照补全与回滚恢复

**文件：**
- 修改：`backend/app/routers/versions.py:41-51`（create_version）、`:73-80`（rollback_version）
- 修改：`backend/app/routers/generation.py`（两处自动快照）
- 新增：`backend/tests/test_plan_version_snapshot.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_version_snapshot.py
from unittest.mock import MagicMock


def test_snapshot_includes_style_and_mermaid():
    from app.routers.versions import _build_snapshot
    plan = MagicMock()
    plan.title = "测试预案"
    plan.style_preference = {"formality": "formal"}
    plan.advanced_prompt_overrides = {"system_prompt_override": "x"}
    sec = MagicMock()
    sec.section_key = "sec_1"
    sec.title = "总则"
    sec.content = "<p>内容</p>"
    sec.ai_generated = True
    sec.mermaid_svgs = {"abc": "<svg/>"}
    snap = _build_snapshot(plan, [sec])
    assert snap["style_preference"] == {"formality": "formal"}
    assert snap["advanced_prompt_overrides"] == {"system_prompt_override": "x"}
    assert snap["sections"][0]["mermaid_svgs"] == {"abc": "<svg/>"}


def test_rollback_restores_style_and_mermaid():
    from app.routers.versions import _apply_snapshot
    plan = MagicMock()
    sec = MagicMock()
    sec.section_key = "sec_1"
    snap = {
        "style_preference": {"formality": "practical"},
        "advanced_prompt_overrides": None,
        "sections": [{"section_key": "sec_1", "content": "<p>旧</p>", "mermaid_svgs": {"h": "<svg/>"}}],
    }
    _apply_snapshot(plan, {"sec_1": sec}, snap)
    assert plan.style_preference == {"formality": "practical"}
    assert sec.content == "<p>旧</p>"
    assert sec.mermaid_svgs == {"h": "<svg/>"}


def test_rollback_legacy_snapshot_without_new_fields():
    from app.routers.versions import _apply_snapshot
    plan = MagicMock()
    sec = MagicMock()
    sec.section_key = "sec_1"
    snap = {"sections": [{"section_key": "sec_1", "content": "<p>旧</p>"}]}
    _apply_snapshot(plan, {"sec_1": sec}, snap)
    assert sec.content == "<p>旧</p>"
    # 旧快照无 style 键 → 不报错、不覆盖
    assert not hasattr(plan, "_style_was_set")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_version_snapshot.py -v`
预期：FAIL，`ImportError: cannot import name '_build_snapshot'`

- [ ] **步骤 3：实现快照构建与恢复辅助函数**

```python
# backend/app/routers/versions.py  模块级新增：
def _build_snapshot(plan, sections: list) -> dict:
    """构建含风格参数与 Mermaid 图表的完整快照。"""
    return {
        "title": plan.title,
        "style_preference": plan.style_preference,
        "advanced_prompt_overrides": plan.advanced_prompt_overrides,
        "sections": [
            {
                "section_key": s.section_key,
                "title": s.title,
                "content": s.content,
                "ai_generated": s.ai_generated,
                "mermaid_svgs": s.mermaid_svgs,
            }
            for s in sections
        ],
    }


def _apply_snapshot(plan, section_map: dict, snapshot: dict) -> None:
    """将快照恢复到 plan 与章节；旧快照缺字段时跳过对应项。"""
    if "style_preference" in snapshot:
        plan.style_preference = snapshot.get("style_preference")
    if "advanced_prompt_overrides" in snapshot:
        plan.advanced_prompt_overrides = snapshot.get("advanced_prompt_overrides")
    for s_data in snapshot.get("sections", []):
        s = section_map.get(s_data.get("section_key"))
        if not s:
            continue
        s.content = s_data.get("content")
        if "mermaid_svgs" in s_data:
            s.mermaid_svgs = s_data.get("mermaid_svgs")
```

- [ ] **步骤 4：create_version 使用 `_build_snapshot`**

```python
# backend/app/routers/versions.py  create_version 内替换快照构造：
    snapshot = _build_snapshot(p, sections)
```

- [ ] **步骤 5：rollback_version 使用 `_apply_snapshot`**

```python
# backend/app/routers/versions.py  rollback_version 内替换循环：
    section_map = {}
    for s_data in v.snapshot.get("sections", []):
        s = (await db.execute(select(PlanSection).where(
            PlanSection.plan_project_id == plan_id,
            PlanSection.section_key == s_data["section_key"],
        ))).scalar_one_or_none()
        if s:
            section_map[s.section_key] = s
    _apply_snapshot(p, section_map, v.snapshot or {})
    await db.commit()
```

- [ ] **步骤 6：generation.py 两处自动快照同步扩展**

```python
# backend/app/routers/generation.py  两处 ver_snapshot 构造替换为：
                    ver_snapshot = {
                        "title": p2.title,
                        "style_preference": p2.style_preference,
                        "advanced_prompt_overrides": p2.advanced_prompt_overrides,
                        "sections": [
                            {
                                "section_key": s.section_key,
                                "title": s.title,
                                "content": s.content,
                                "ai_generated": s.ai_generated,
                                "mermaid_svgs": s.mermaid_svgs,
                            }
                            for s in updated
                        ],
                    }
```

（两处均在 `generate_batch` 与 `generate_batch_background` 中，行号约 512 与 714）

- [ ] **步骤 7：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_version_snapshot.py -v`
预期：PASS（3 passed）

- [ ] **步骤 8：全量回归**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过

- [ ] **步骤 9：Commit**

```bash
git add backend/app/routers/versions.py backend/app/routers/generation.py backend/tests/test_plan_version_snapshot.py
git commit -m "feat(plan): include style and mermaid in version snapshots (batch2)"
```

---

### 任务 5：前端创建页编号输入

**文件：**
- 修改：`frontend/src/types/plan.ts`（PlanProject/PlanCreate）
- 修改：`frontend/src/pages/Plan/PlanCreatePage.tsx`

- [ ] **步骤 1：类型扩展**

```typescript
// frontend/src/types/plan.ts  PlanProject 追加：
  plan_number: string | null;
  version_number: string | null;

// PlanCreate 追加：
  plan_number?: string | null;
  version_number?: string | null;
```

- [ ] **步骤 2：创建页新增编号输入（确认步骤）**

```typescript
// frontend/src/pages/Plan/PlanCreatePage.tsx  新增 state：
  const [planNumber, setPlanNumber] = useState("");
  const [versionNumber, setVersionNumber] = useState("");

// 确认步骤 Descriptions 下方新增：
          <Input
            size="large"
            placeholder="预案编号（留空自动生成）"
            value={planNumber}
            onChange={(e) => setPlanNumber(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <Input
            size="large"
            placeholder="版本号（留空自动生成）"
            value={versionNumber}
            onChange={(e) => setVersionNumber(e.target.value)}
          />

// mutation.mutate 入参追加：
                  plan_number: planNumber || null,
                  version_number: versionNumber || null,
```

- [ ] **步骤 3：类型检查**

运行：`cd frontend && npx tsc -b`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/types/plan.ts frontend/src/pages/Plan/PlanCreatePage.tsx
git commit -m "feat(plan): add plan number inputs in create wizard (batch2)"
```

---

### 任务 6：第 2 批收尾验证

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过

- [ ] **步骤 2：前端构建与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：全部通过

- [ ] **步骤 3：迁移 SQL 语法检查（有 DB 时）**

运行：`psql -U postgres -d emergency_plan -f backend/db_migration_plan_number.sql`
预期：成功执行，幂等

- [ ] **步骤 4：规格对照自检**

- [x] 3.3 模型/迁移 → 任务 1
- [x] 3.3 自动编号/schema → 任务 2
- [x] 3.3 导出真实编号 + signers → 任务 3
- [x] 3.4 快照扩展/回滚 → 任务 4
- [x] 3.3 前端创建页 → 任务 5

- [ ] **步骤 5：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): batch2 final verification"
```
