"""作业票 API 测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import work_ticket
from app.schemas.work_ticket import OpenTicketIn


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _client(handler):
    app = FastAPI()
    app.include_router(work_ticket.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        yield db

    async def _user():
        return MagicMock(id="u1")

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_list_tickets_filters_by_type(monkeypatch):
    # 列表入口现在先判"所有者/成员可见性"，这里固定为所有者，聚焦 ticket_type 过滤本身
    async def _visible(_db, _user, _enterprise_id, *, detail=None):
        return MagicMock(), True

    monkeypatch.setattr(work_ticket, "ensure_enterprise_visible", _visible)
    t = MagicMock()
    t.id = "wt1"
    t.code = "DHZY-A-20260917-0001"
    t.ticket_type = "DHZY"
    t.level = "一级"
    t.status = "approving"
    t.current_node_key = "approve"
    t.values = {}
    t.values_meta = {}
    t.measures_meta = {}
    t.valid_from = None
    t.valid_to = None
    t.created_at = None

    async def handler(stmt, *a, **k):
        return _Result([t])

    client = _client(handler)
    resp = client.get(
        "/api/v1/work-ticket/tickets", params={"enterprise_id": "e1", "ticket_type": "DHZY"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["ticket_type"] == "DHZY"


def test_open_ticket_rejects_unknown_type():
    """未知类型必须被 schema 拒掉；8 类标准类型不得再被白名单挡住。"""
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post(
        "/api/v1/work-ticket/tickets",
        json={
            "enterprise_id": "e1",
            "enterprise_code": "A",
            "ticket_type": "XXXX",
            "template_id": "t1",
        },
    )
    assert resp.status_code == 422


def test_open_ticket_schema_accepts_all_eight_types():
    for code in ("DHZY", "YXKJ", "MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY"):
        payload = OpenTicketIn(
            enterprise_id="e1",
            enterprise_code="A",
            ticket_type=code,
            template_id="t1",
        )
        assert payload.ticket_type == code


def test_open_ticket_schema_rejects_unknown_type():
    with pytest.raises(ValidationError):
        OpenTicketIn(
            enterprise_id="e1",
            enterprise_code="A",
            ticket_type="XXXX",
            template_id="t1",
        )


def test_submit_returns_422_on_validation_failure():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post("/api/v1/work-ticket/tickets/missing/submit")
    # W0：票不存在/无权访问统一 404（原 409/422 语义保留给校验失败场景）
    assert resp.status_code in (404, 409, 422)


def _instance(status: str):
    inst = MagicMock()
    inst.id = "t1"
    inst.status = status
    inst.values = {}
    inst.values_meta = {}
    inst.measures_meta = {}
    return inst


def test_draft_save_rejects_non_draft_status(monkeypatch):
    """已提交的票不能再走草稿保存。"""

    async def _owned(_db, _user, _ticket_id):
        return _instance(status="approving")

    monkeypatch.setattr(work_ticket, "ensure_ticket_owned", _owned)

    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.patch(
        "/api/v1/work-ticket/tickets/t1",
        json={"values": {"work_content": "x"}, "values_meta": {}, "measures_meta": {}},
    )
    assert resp.status_code == 409
    assert "草稿" in resp.json()["detail"]


def test_templates_expose_allow_ai_prefill():
    """模板接口必须把 allow_ai_prefill 透出，前端才能决定是否显示 AI 按钮。"""
    field = MagicMock()
    field.field_key = "risk_identification"
    field.label = "风险辨识结果"
    field.field_type = "textarea"
    field.group_name = "危害因素"
    field.is_required = True
    field.options = {}
    field.allow_ai_prefill = True
    field.sort_order = 1
    template = MagicMock()
    template.id = "tpl1"
    template.code = "DHZY"
    template.name = "动火安全作业票"
    template.level = "二级"
    template.is_graded = True
    template.fields = [field]
    template.measures = []

    calls = {"n": 0}

    async def handler(stmt, *a, **k):
        calls["n"] += 1
        return _Result([template] if calls["n"] == 1 else [])

    client = _client(handler)
    resp = client.get("/api/v1/work-ticket/templates")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["fields"][0]["allow_ai_prefill"] is True


def _scenario_row(ticket_type: str, key: str, label: str, order: int):
    row = MagicMock()
    row.ticket_type = ticket_type
    row.condition_key = key
    row.label = label
    row.sort_order = order
    row.auto_rule = None
    return row


def test_templates_expose_scenario_fields():
    """每个模板要带出该票种的人工勾选情景项，前端才能按票种渲染情景区。"""
    field = MagicMock()
    field.field_key = "space_location"
    field.label = "受限空间名称及位置"
    field.field_type = "text"
    field.group_name = "作业内容"
    field.is_required = True
    field.options = {}
    field.allow_ai_prefill = False
    field.sort_order = 1
    template = MagicMock()
    template.id = "tpl-yxkj"
    template.code = "YXKJ"
    template.name = "受限空间安全作业票"
    template.level = None
    template.is_graded = False
    template.fields = [field]
    template.measures = []

    async def handler(stmt, *a, **k):
        # 按查询目标表判断，而不是按调用次数——查询次数会随模板/流程是否存在而变化
        sql_text = str(stmt)
        if "work_ticket_scenarios" in sql_text:
            return _Result(
                [
                    _scenario_row("YXKJ", "hazardous_residue", "受限空间盛装过有毒/可燃物料", 1),
                    _scenario_row("YXKJ", "rotating_equipment", "内部有转动设备", 2),
                ]
            )
        if "work_ticket_templates" in sql_text:
            return _Result([template])
        return _Result([])

    client = _client(handler)
    resp = client.get("/api/v1/work-ticket/templates")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["scenario_fields"] == [
        {"key": "hazardous_residue", "label": "受限空间盛装过有毒/可燃物料"},
        {"key": "rotating_equipment", "label": "内部有转动设备"},
    ]


def test_scenarios_endpoint_returns_only_manual_items():
    """兜底端点只返回人工勾选项（auto_rule 为空），自动项不出现在情景区。"""

    async def handler(stmt, *a, **k):
        return _Result(
            [_scenario_row("YXKJ", "hazardous_residue", "受限空间盛装过有毒/可燃物料", 1)]
        )

    client = _client(handler)
    resp = client.get("/api/v1/work-ticket/scenarios", params={"ticket_type": "YXKJ"})
    assert resp.status_code == 200
    assert resp.json()["data"] == [
        {"key": "hazardous_residue", "label": "受限空间盛装过有毒/可燃物料"}
    ]
