# Codex Custom Subagents task handoff v1

Task: task_08_control_list

## 目标

实现「风险分级管控增强（A 阶段）」任务 8：管控清单 API + Excel 导出 + 重大风险公示后端（企业内数据 + 公开脱敏端点），按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD 以实际为准，任务 7 复审后最新）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景

- 任务 1-7 已就绪：`data_dicts`（含 control_level_map 系统种子，value={"level","control_level"}）、`get_dict_map` 合并读取、`RiskEvent.inherent_*`/`control_level`、`Enterprise.public_risk_token`（迁移+模型已有）、`RiskZone`/`RiskObject`/`RiskUnit`/`RiskEvent`/`RiskMeasure` 关系；
- 计划原文有两处需修正（已核实）：①`flatten_rows` 行需带 `zone_id`（筛选用）；②`control_level_map` 映射应按键 `value["level"]` 而非 label；
- 测试约定：无 db fixture，服务用纯函数、端点用 dependency_overrides + mock。

## 文件

- 创建：`backend/app/services/risk_control_list_service.py`
- 修改：`backend/app/routers/risk_management.py`（control-list / export / risk-publicity / token）
- 创建：`backend/app/routers/public_risk.py`
- 修改：`backend/app/main.py`（注册 public_risk）
- 测试：`backend/tests/test_risk_control_list.py`

## 步骤（TDD）

- [ ] **步骤 1：失败测试**（`backend/tests/test_risk_control_list.py`）

```python
from app.services.risk_control_list_service import flatten_rows, default_control_level, build_ledger_workbook

def test_default_control_level_from_dict():
    mapping = {"重大": "企业", "较大": "部门", "一般": "班组", "低": "岗位"}
    assert default_control_level(mapping, "重大") == "企业"
    assert default_control_level(mapping, None) == "岗位"

def test_build_ledger_workbook():
    rows = [{"zone": "储罐区", "object": "1#储罐", "unit": "阀门组",
             "accident": "泄漏", "inherent": "重大", "current": "一般",
             "control_level": "班组", "measures": "报警器年检", "unit_name": "生产部", "person": "李四"}]
    wb = build_ledger_workbook(rows)
    ws = wb.active
    assert ws["A1"].value == "分区"
    assert ws.max_row == 2

def test_flatten_rows_includes_zone_id():
    from app.models.risk_management import RiskZone, RiskObject, RiskEvent
    zone = RiskZone(id="z1", enterprise_id="e1", floor_id="f1", name="储罐区")
    obj = RiskObject(id="o1", enterprise_id="e1", zone_id="z1", name="1#储罐")
    obj.events = [RiskEvent(accident_type="泄漏", risk_level="重大", inherent_risk_level="重大")]
    zone.objects = [obj]
    rows = flatten_rows([zone], {"重大": "企业"})
    assert rows[0]["zone_id"] == "z1"
```

另加端点测试（同文件）：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import get_db
from app.dependencies import get_current_user
from app.routers import risk_management, public_risk
from app.models.enterprise import Enterprise
from app.services import data_dict_service

def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司")
    for k, v in kw.items(): setattr(e, k, v)
    return e

def test_public_risk_404_and_desensitized(monkeypatch):
    # 无效 token → 404「链接已失效」
    app = FastAPI(); app.include_router(public_risk.router, prefix="/api/v1")
    async def _db():
        db = MagicMock()
        async def execute(stmt, *a, **k):
            res = MagicMock(); res.scalar_one_or_none.return_value = None
            return res
        db.execute = AsyncMock(side_effect=execute)
        return db
    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    assert client.get("/api/v1/public/risk/bad").status_code == 404
```

（公开端点脱敏与 control-list 端点的路由级用例，由实现者按同样模式补充，覆盖：有效 token 返回脱敏 items（无 person/phone 键）、control-list 筛选/分页、export 返回 xlsx、publicity token 生成/重置。）

- [ ] **步骤 2：运行测试验证失败**

在 `backend` 目录 `python -m pytest tests/test_risk_control_list.py -v`，预期 FAIL（模块不存在）。

- [ ] **步骤 3：实现清单服务**（`backend/app/services/risk_control_list_service.py`）

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

def default_control_level(mapping: dict, current_level: str | None) -> str:
    return mapping.get(current_level or "", "岗位")

def flatten_rows(zones: list, mapping: dict) -> list[dict]:
    rows = []
    for z in zones:
        for obj in z.objects or []:
            for unit in obj.units or []:
                for ev in unit.events or []:
                    rows.append(_row(z, obj, unit, ev, mapping))
            for ev in obj.events or []:
                rows.append(_row(z, obj, None, ev, mapping))
    return rows

def _row(z, obj, unit, ev, mapping) -> dict:
    measures = "；".join(
        f"{m.measure_category}:{m.description}" for m in (ev.measures or [])) or "-"
    return {
        "zone_id": z.id, "object_id": obj.id,
        "zone": z.name, "object": obj.name, "unit": unit.name if unit else "-",
        "accident": ev.accident_type, "inherent": ev.inherent_risk_level or ev.risk_level or "-",
        "current": ev.risk_level or "-", "control_level": ev.control_level or default_control_level(mapping, ev.risk_level),
        "measures": measures, "unit_name": obj.responsible_unit or "-",
        "person": obj.responsible_person or "-", "phone": obj.contact_phone or "-",
    }

def build_ledger_workbook(rows: list[dict]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "风险管控清单"
    headers = ["分区", "风险点", "单元", "事故类型", "固有等级", "现有等级",
               "管控层级", "管控措施", "责任单位", "责任人", "联系电话"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="EEF2F7")
    for r in rows:
        ws.append([r[h] for h in headers])
    return wb

PUBLIC_FIELDS = ["zone", "object", "unit", "accident", "inherent", "current",
                 "control_level", "measures", "unit_name"]

def desensitize(rows: list[dict]) -> list[dict]:
    """公开脱敏：仅保留 PUBLIC_FIELDS，不含 person/phone。"""
    return [{k: r.get(k) for k in PUBLIC_FIELDS} for r in rows]
```

- [ ] **步骤 4：实现端点**

`backend/app/routers/risk_management.py` 追加（查询 zone 树用 `select(RiskZone).where(RiskZone.floor_id == floor_id).options(selectinload(RiskZone.objects).selectinload(RiskObject.units).selectinload(RiskUnit.events).selectinload(RiskEvent.measures), selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures))`，floor_id 缺省用默认楼层；mapping 用 `get_dict_map(db, enterprise_id, "control_level_map")`，构建 `{entry["value"].get("level"): entry["value"].get("control_level") for entry in ...values() if isinstance(entry.get("value"), dict)}`）：

- `GET /control-list`：筛选（zone_id / level 匹配 current 或 inherent / control_level / keyword 匹配 object 或 zone）+ 分页，返回 `{items, total}`；items 去掉 zone_id/object_id 内部键（或保留，不敏感，但建议去除）；
- `GET /control-list/export`：全量 rows → `build_ledger_workbook` → `StreamingResponse` xlsx（Content-Disposition `risk_control_list.xlsx`）；
- `GET /risk-publicity`：企业公示数据——token 不存在则生成（`secrets.token_hex(32)` 并 commit）；rows 筛 `current == "重大" or control_level == "企业"`；返回 `{token, enterprise_name, items}`；
- `POST /risk-publicity/token`：重置 token 返回新值。

`backend/app/routers/public_risk.py`（新）：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent
from app.schemas.common import ApiResponse
from app.services.risk_control_list_service import flatten_rows, desensitize, default_control_level

router = APIRouter(prefix="/public/risk", tags=["Public Risk"])

@router.get("/{token}", response_model=ApiResponse[dict])
async def public_risk(token: str, db: AsyncSession = Depends(get_db)):
    ent = (await db.execute(select(Enterprise).where(Enterprise.public_risk_token == token))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "链接已失效")
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == ent.id)
        .options(selectinload(RiskZone.objects).selectinload(RiskObject.events).selectinload(RiskEvent.measures))
    )).scalars().all()
    rows = [r for r in flatten_rows(zones, {}) if r["current"] == "重大" or r["control_level"] == "企业"]
    return ApiResponse(data={"enterprise_name": ent.name, "items": desensitize(rows)})
```

`backend/app/main.py`：import 加 `public_risk`，`app.include_router(public_risk.router, prefix="/api/v1")`。

- [ ] **步骤 5：运行测试验证通过**

在 `backend` 目录 `python -m pytest tests/test_risk_control_list.py -v`，预期全部 PASS；`python -m pytest tests/ -q` 无回归。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/risk_control_list_service.py backend/app/routers/risk_management.py backend/app/routers/public_risk.py backend/app/main.py backend/tests/test_risk_control_list.py
git commit -m "feat(risk): control list with xlsx export and desensitized public risk page"
```

不要提交 TASKS.md；消息精确匹配；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_08_control_list --claim-id <claim_id> --exit-code 0 --summary "管控清单+公示后端完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、自审结论。

## 规则

- 严格 TDD；用 `apply_patch` 编辑；只改列出的 5 个文件；阻塞时停下汇报。
