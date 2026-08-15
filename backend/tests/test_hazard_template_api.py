"""隐患排查治理任务 4 测试：检查表模板 CRUD/复制/AI 生成。

测试风格与 tests/test_hazard_plan_api.py / test_enterprise_org.py 一致：
无 db fixture，端点用 FastAPI TestClient + dependency_overrides +
SQL 文本分发 mock；async 服务函数用 @pytest.mark.asyncio。

覆盖：
- 列表：系统+企业合并，企业条目按（名称,类别）覆盖系统模板；读归属 404
- 创建：字段校验（name/category/items）/ 企业内同名同类 409 / 写权限 403
- 更新：企业模板更新 / 系统模板 422 / 非本企业 404 / 冲突 409
- 复制：系统模板深拷贝为企业模板 / 冲突 409 / 非本企业 404
- 删除：企业模板删除 / 系统模板 422 / 非本企业 404
- AI 生成：成功 items 结构 / 输入均空 422 / 未配置与异常降级 available:false
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import HazardChecklistTemplate
from app.models.user import User
from app.routers import hazard_management
from app.services.hazard_ai_service import generate_checklist_template


# ── mock 工具 ──

def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _scalars(values):
    res = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = list(values)
    res.scalars.return_value = scalars_mock
    return res


def _first(value):
    res = MagicMock()
    res.first.return_value = value
    return res


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="standard")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _template(**kw):
    t = HazardChecklistTemplate(
        id=kw.pop("id", "tpl1"),
        enterprise_id=kw.pop("enterprise_id", None),
        name=kw.pop("name", "日常检查表"),
        category=kw.pop("category", "daily"),
        items=kw.pop("items", [{"content": "检查通道", "expected_note": "畅通"}]),
        is_system=kw.pop("is_system", False),
    )
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def _tpl_db(ent, *, member=None, admin_member=None, system_templates=None,
            ent_templates=None, template=None, templates=None, conflict=None):
    """按 SQL 文本特征分发（参照 tests/test_hazard_plan_api.py 的 _hazard_db）。"""
    db = AsyncMock()
    db.added = []

    def fake_add(obj):
        if isinstance(obj, HazardChecklistTemplate) and not getattr(obj, "id", None):
            obj.id = f"nt{len([x for x in db.added if isinstance(x, HazardChecklistTemplate)]) + 1}"
        db.added.append(obj)

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM enterprise_members" in text:
            if "enterprise_members.role" in text:
                return _first(admin_member if admin_member and getattr(admin_member, "enabled", True) else None)
            return _first(member if member and getattr(member, "enabled", True) else None)
        if "FROM hazard_checklist_templates" in text:
            if "enterprise_id IS NULL" in text:
                return _scalars(system_templates or [])
            if "hazard_checklist_templates.name =" in text:
                return _first(conflict)
            if "hazard_checklist_templates.id =" in text:
                return _scalar(template)
            if "hazard_checklist_templates.enterprise_id =" in text:
                return _scalars(ent_templates or [])
            return _scalars(templates or [])
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(hazard_management.router)

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="user")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _tpl_db(_ent())
    with TestClient(app) as test_client:
        yield test_client


_TEMPLATE_BODY = {
    "name": "车间日常检查",
    "category": "daily",
    "items": [{"content": "检查通道", "expected_note": "畅通"}],
}


# ── 模板列表：系统+企业合并 ──

def test_templates_list_merges_with_enterprise_override(client):
    system = [
        _template(id="s1", name="日常检查表", category="daily", is_system=True),
        _template(id="s2", name="综合检查表", category="comprehensive", is_system=True),
    ]
    ent_rows = [
        _template(id="e1", enterprise_id="e1", name="日常检查表", category="daily",
                  items=[{"content": "企业自定义日常项", "expected_note": "按企业标准"}], is_system=False),
    ]
    db = _tpl_db(_ent(), system_templates=system, ent_templates=ent_rows)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/templates")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2  # 日常被企业条目覆盖，综合保留系统模板
    by_name = {d["name"]: d for d in data}
    daily = by_name["日常检查表"]
    assert daily["id"] == "e1"
    assert daily["is_system"] is False
    assert daily["source"] == "enterprise"
    assert daily["items"] == [{"content": "企业自定义日常项", "expected_note": "按企业标准"}]
    comprehensive = by_name["综合检查表"]
    assert comprehensive["id"] == "s2"
    assert comprehensive["is_system"] is True
    assert comprehensive["source"] == "system"
    assert comprehensive["items"] == [{"content": "检查通道", "expected_note": "畅通"}]


def test_templates_list_read_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _tpl_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/templates")
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]


# ── 模板创建 ──

def test_template_create_success(client):
    db = _tpl_db(_ent(), admin_member=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"name": " 车间日常检查 ", "category": "daily",
            "items": [{"content": "检查通道", "expected_note": "畅通"},
                      {"content": "灭火器完好", "expected_note": None}]}
    resp = client.post("/enterprises/e1/hazard-inspection/templates", json=body)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "车间日常检查"
    assert data["category"] == "daily"
    assert data["is_system"] is False
    assert data["source"] == "enterprise"
    assert data["items"][0] == {"content": "检查通道", "expected_note": "畅通"}
    assert data["items"][1] == {"content": "灭火器完好", "expected_note": None}
    added = db.added[0]
    assert isinstance(added, HazardChecklistTemplate)
    assert added.enterprise_id == "e1"
    assert added.is_system is False
    db.commit.assert_awaited()


def test_template_create_rejects_blank_name(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates",
                       json={**_TEMPLATE_BODY, "name": "   "})
    assert resp.status_code == 422
    assert "name 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_create_rejects_invalid_category(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates",
                       json={**_TEMPLATE_BODY, "category": "boss"})
    assert resp.status_code == 422
    assert "category 非法" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_create_rejects_empty_items(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates",
                       json={**_TEMPLATE_BODY, "items": []})
    assert resp.status_code == 422
    assert "items 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_create_rejects_blank_content(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates",
                       json={**_TEMPLATE_BODY, "items": [{"content": "   ", "expected_note": "x"}]})
    assert resp.status_code == 422
    assert "content 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_create_same_name_category_conflict_409(client):
    db = _tpl_db(_ent(), conflict=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates", json=_TEMPLATE_BODY)
    assert resp.status_code == 409
    assert "已存在同名同类别" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_create_non_admin_writer_403(client):
    ent = _ent(user_id="u2")
    db = _tpl_db(ent, admin_member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates", json=_TEMPLATE_BODY)
    assert resp.status_code == 403
    db.commit.assert_not_awaited()


def test_template_create_admin_member_allowed(client):
    ent = _ent(user_id="u2")
    admin = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1", role="enterprise_admin", enabled=True)
    db = _tpl_db(ent, admin_member=admin)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates", json=_TEMPLATE_BODY)
    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "车间日常检查"


# ── 模板更新 ──

def test_template_update_enterprise_template(client):
    tpl = _template(id="e1", enterprise_id="e1", name="车间检查", category="daily")
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/templates/e1",
                      json={"name": "车间综合检查", "category": "comprehensive",
                            "items": [{"content": "更新项", "expected_note": "标准"}]})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "车间综合检查"
    assert data["category"] == "comprehensive"
    assert data["items"] == [{"content": "更新项", "expected_note": "标准"}]
    assert tpl.name == "车间综合检查"
    assert tpl.items == [{"content": "更新项", "expected_note": "标准"}]
    db.commit.assert_awaited()


def test_template_update_system_template_422(client):
    tpl = _template(id="s1", name="日常检查表", category="daily", is_system=True)
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/templates/s1", json={"name": "改系统"})
    assert resp.status_code == 422
    assert "系统模板请复制后编辑" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_update_foreign_enterprise_404(client):
    tpl = _template(id="e9", enterprise_id="e9", name="他企业模板")
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/templates/e9", json={"name": "改名"})
    assert resp.status_code == 404
    assert "检查表模板不存在" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_update_same_name_category_conflict_409(client):
    tpl = _template(id="e1", enterprise_id="e1", name="车间检查", category="daily")
    db = _tpl_db(_ent(), template=tpl, conflict=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/templates/e1", json={"name": "综合检查"})
    assert resp.status_code == 409
    assert "已存在同名同类别" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_update_items_only_skips_conflict_check(client):
    tpl = _template(id="e1", enterprise_id="e1", name="车间检查", category="daily")
    db = _tpl_db(_ent(), template=tpl, conflict=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/templates/e1",
                      json={"items": [{"content": "仅改项", "expected_note": "新标准"}]})
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == [{"content": "仅改项", "expected_note": "新标准"}]


# ── 模板复制 ──

def test_template_copy_system_to_enterprise_deep_copies_items(client):
    items = [{"content": "系统检查项", "expected_note": "系统标准"}]
    src = _template(id="s1", name="日常检查表", category="daily", items=items, is_system=True)
    db = _tpl_db(_ent(), template=src)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates/s1/copy")
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "日常检查表"
    assert data["category"] == "daily"
    assert data["is_system"] is False
    assert data["items"] == items
    added = db.added[0]
    assert isinstance(added, HazardChecklistTemplate)
    assert added.enterprise_id == "e1"
    assert added.is_system is False
    assert added.items == items
    assert added.items is not items  # 深拷贝，副本与源互不影响
    db.commit.assert_awaited()


def test_template_copy_conflict_409(client):
    src = _template(id="s1", name="日常检查表", category="daily", is_system=True)
    db = _tpl_db(_ent(), template=src, conflict=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates/s1/copy")
    assert resp.status_code == 409
    assert "已存在同名同类别" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_template_copy_foreign_enterprise_404(client):
    tpl = _template(id="e9", enterprise_id="e9", name="他企业模板")
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/templates/e9/copy")
    assert resp.status_code == 404
    db.commit.assert_not_awaited()


# ── 模板删除 ──

def test_template_delete_enterprise_template(client):
    tpl = _template(id="e1", enterprise_id="e1")
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.delete("/enterprises/e1/hazard-inspection/templates/e1")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert resp.json()["message"] == "已删除"
    db.delete.assert_awaited_once_with(tpl)
    db.commit.assert_awaited()


def test_template_delete_system_template_422(client):
    tpl = _template(id="s1", name="日常检查表", category="daily", is_system=True)
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.delete("/enterprises/e1/hazard-inspection/templates/s1")
    assert resp.status_code == 422
    assert "系统模板" in resp.json()["detail"]
    db.delete.assert_not_awaited()


def test_template_delete_foreign_enterprise_404(client):
    tpl = _template(id="e9", enterprise_id="e9", name="他企业模板")
    db = _tpl_db(_ent(), template=tpl)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.delete("/enterprises/e1/hazard-inspection/templates/e9")
    assert resp.status_code == 404
    db.delete.assert_not_awaited()


# ── AI 检查表生成：端点 ──

def test_ai_endpoint_success_returns_items(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fake = {"available": True, "items": [{"content": "检查灭火器", "expected_note": "压力正常"}], "note": ""}
    with patch("app.routers.hazard_management._get_ai_config", AsyncMock(return_value=MagicMock())), \
         patch("app.routers.hazard_management.generate_checklist_template",
               AsyncMock(return_value=fake)) as mock_gen:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist-template",
                           json={"industry": "化工", "risk_points": "储罐区泄漏风险"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["available"] is True
    assert data["items"] == [{"content": "检查灭火器", "expected_note": "压力正常"}]
    assert mock_gen.await_count == 1
    assert mock_gen.await_args.args[:2] == ("化工", "储罐区泄漏风险")


def test_ai_endpoint_empty_input_422(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist-template",
                       json={"industry": "   ", "risk_points": ""})
    assert resp.status_code == 422
    assert "至少填写一项" in resp.json()["detail"]


def test_ai_endpoint_no_config_degrades_200(client):
    db = _tpl_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    fallback = {"available": False, "items": [], "note": "AI 不可用，请手动编辑检查表模板"}
    with patch("app.routers.hazard_management._get_ai_config",
               AsyncMock(side_effect=HTTPException(400, "系统未配置 AI 模型，请联系管理员"))), \
         patch("app.routers.hazard_management.generate_checklist_template",
               AsyncMock(return_value=fallback)) as mock_gen:
        resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist-template",
                           json={"industry": "化工"})
    assert resp.status_code == 200
    assert resp.json()["data"] == fallback
    assert mock_gen.await_count == 1
    assert mock_gen.await_args.args[2] is None  # 未配置 → ai_config=None 走服务兜底


def test_ai_endpoint_requires_read_membership(client):
    ent = _ent(user_id="u2")
    db = _tpl_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/ai/checklist-template",
                       json={"industry": "化工"})
    assert resp.status_code == 404


# ── AI 检查表生成：服务层 ──

@pytest.mark.asyncio
async def test_generate_checklist_template_success_parses_fence_and_normalizes():
    items = [{"content": f"检查项{i}", "expected_note": f"标准{i}"} for i in range(1, 10)]
    items.append({"content": "无标准项"})
    raw = "```json\n" + json.dumps({"items": items}, ensure_ascii=False) + "\n```"
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock(return_value=raw)):
        out = await generate_checklist_template("化工行业", "储罐区泄漏", MagicMock())
    assert out["available"] is True
    assert len(out["items"]) == 10
    assert all(isinstance(i, dict) and i["content"] and "expected_note" in i for i in out["items"])
    assert out["items"][9]["expected_note"] is None


@pytest.mark.asyncio
async def test_generate_checklist_template_caps_at_15():
    payload = {"items": [{"content": f"检查项{i}", "expected_note": ""} for i in range(20)]}
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))):
        out = await generate_checklist_template("化工", "", MagicMock())
    assert out["available"] is True
    assert len(out["items"]) == 15


@pytest.mark.asyncio
async def test_generate_checklist_template_empty_items_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value='{"items": []}')):
        out = await generate_checklist_template("化工", "风险", MagicMock())
    assert out["available"] is False
    assert out["items"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_generate_checklist_template_failure_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await generate_checklist_template("化工", "风险", MagicMock())
    assert out["available"] is False
    assert out["items"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_generate_checklist_template_invalid_json_degrades():
    with patch("app.services.hazard_ai_service.llm_text_completion",
               AsyncMock(return_value="not a json")):
        out = await generate_checklist_template("化工", "风险", MagicMock())
    assert out["available"] is False
    assert out["items"] == []


@pytest.mark.asyncio
async def test_generate_checklist_template_no_config_skips_llm():
    with patch("app.services.hazard_ai_service.llm_text_completion", AsyncMock()) as mock_llm:
        out = await generate_checklist_template("化工", "风险", None)
    assert out["available"] is False
    assert out["items"] == []
    mock_llm.assert_not_awaited()
