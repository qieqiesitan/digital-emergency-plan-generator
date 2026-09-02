"""chat_dispatch 收尾回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import (
    _delegate_generic,
    _ErrorDict,
    _list_resources,
    _update_enterprise,
    _delete_plan,
    dispatch,
)


@pytest.mark.asyncio
async def test_delegate_generic_returns_error_data_on_erroDict():
    async def op(db, user, args, cfg):
        raise _ErrorDict({"error": "企业不存在或无权访问", "verified": False})

    out = await _delegate_generic(op, AsyncMock(), MagicMock(), {}, {})
    assert out == {"error": "企业不存在或无权访问", "verified": False}


@pytest.mark.asyncio
async def test_delegate_generic_passthrough():
    async def op(db, user, args, cfg):
        return {"id": "1", "verified": True}

    assert await _delegate_generic(op, AsyncMock(), MagicMock(), {}, {}) == {"id": "1", "verified": True}


@pytest.mark.asyncio
async def test_list_resources_requires_enterprise_id():
    out = await _list_resources(AsyncMock(), MagicMock(id="u1"), {})
    assert out == {"error": "请提供 enterprise_id", "verified": False}


@pytest.mark.asyncio
async def test_update_enterprise_delegates_generic():
    db = AsyncMock()
    ent = MagicMock(id="e1", name="企业A")
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    out = await _update_enterprise(db, MagicMock(id="u1"), {"enterprise_id": "e1", "name": "企业B"})
    assert out["verified"] is True
    assert ent.name == "企业B"


@pytest.mark.asyncio
async def test_delete_plan_missing_id():
    out = await _delete_plan(AsyncMock(), MagicMock(id="u1"), {})
    assert out["error"] == "请提供 plan_id"


@pytest.mark.asyncio
async def test_dispatch_unknown_function():
    out = await dispatch(AsyncMock(), MagicMock(id="u1"), "no_such_fn", {})
    assert "未知操作" in out


@pytest.mark.asyncio
async def test_create_plan_maps_chinese_plan_type():
    """聊天工具传中文 plan_type（综合应急预案）应映射为模板表英文枚举。"""
    from app.services.chat_dispatch import _create_plan
    db = AsyncMock()
    ent = MagicMock(id="e1", name="企业A", user_id="u1")
    tmpl = MagicMock(plan_type="comprehensive",
                     structure=[{"key": "sec_1", "title": "总则"}])
    result = MagicMock()
    result.scalar_one_or_none.side_effect = [ent, tmpl]
    db.execute.return_value = result
    created = []
    db.add = MagicMock(side_effect=created.append)
    with patch("app.routers.plans._create_sections_from_template") as mock_create:
        out = await _create_plan(
            db, MagicMock(id="u1"),
            {"enterprise_id": "e1", "title": "综合预案", "plan_type": "综合应急预案"},
        )
    assert out["verified"] is True
    assert created[0].plan_type == "comprehensive"
    mock_create.assert_called_once()


def test_enterprise_response_dedup_fields():
    from app.schemas.enterprise import EnterpriseBase, EnterpriseResponse
    base = EnterpriseBase.model_fields
    resp = EnterpriseResponse.model_fields
    # 5 个同类型字段不再被 Response 重新声明：注解与 Base 完全一致
    for f in ["last_plan_filing_authority", "building_overview", "floor_plan_url", "gis_lat", "gis_lng"]:
        assert f in resp
        assert resp[f].annotation is base[f].annotation
    # 3 个日期字段保留覆盖：类型不同（输出序列化格式）
    for f in ["established_date", "fire_approval_date", "last_plan_filing_date"]:
        assert resp[f].annotation is not base[f].annotation


@pytest.mark.asyncio
async def test_list_enterprises_keyword_search():
    from app.services.chat_dispatch import _list_enterprises
    db = AsyncMock()
    ent = MagicMock(id="e1")
    ent.name = "宝岳"
    ent.industry = "科技"
    ent.address = "西安"
    ent.plans = []
    result = MagicMock()
    result.scalars.return_value.all.return_value = [ent]
    db.execute.return_value = result
    out = await _list_enterprises(db, MagicMock(id="u1"), {"keyword": "宝岳"})
    assert out["enterprises"][0]["name"] == "宝岳"


@pytest.mark.asyncio
async def test_create_enterprise_dedup():
    from app.services.chat_dispatch import _create_enterprise
    db = AsyncMock()
    existing = MagicMock(id="e1")
    existing.name = "宝岳"
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute.return_value = result
    out = await _create_enterprise(db, MagicMock(id="u1"), {"name": "宝岳"})
    assert out == {"id": "e1", "name": "宝岳", "message": "企业已存在，无需重复创建", "verified": True}


@pytest.mark.asyncio
async def test_create_plan_with_template(monkeypatch):
    from app.services.chat_dispatch import _create_plan
    db = AsyncMock()
    ent = MagicMock(id="e1")
    tmpl = MagicMock(structure=[{"section_key": "sec_1", "title": "总则"}])
    results = [
        MagicMock(scalar_one_or_none=lambda: ent),     # Enterprise
        MagicMock(scalar_one_or_none=lambda: tmpl),    # PlanTemplate
    ]
    db.execute = AsyncMock(side_effect=results)
    added = {}

    def fake_add(obj):
        added["obj"] = obj

    db.add = fake_add
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    created = {}

    def fake_create_sections(db, plan_id, structure):
        created["plan_id"] = plan_id
        created["structure"] = structure

    monkeypatch.setattr("app.routers.plans._create_sections_from_template", fake_create_sections)
    out = await _create_plan(db, MagicMock(id="u1"), {
        "enterprise_id": "e1", "title": "预案A", "plan_type": "comprehensive",
    })
    assert out["id"] == added["obj"].id
    assert created["plan_id"] == out["id"]
    assert created["structure"] == tmpl.structure


# ── IDOR 回归测试（体检报告 S6/S7）──


@pytest.mark.asyncio
async def test_res_cfg_enforces_enterprise_ownership():
    """应急资源表无 user_id 列，_RES_CFG 必须通过 enterprise_ownership 做归属校验。"""
    from app.services.chat_dispatch import _RES_CFG

    assert _RES_CFG.get("enterprise_ownership") is True


@pytest.mark.asyncio
async def test_update_resource_checks_ownership_via_enterprise():
    """他人应急资源的 update 必须走 enterprise→user 归属校验并返回 error。"""
    from app.services.chat_dispatch import _update_resource

    db = AsyncMock()
    captured = {}

    async def fake_execute(stmt, *a, **kw):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = fake_execute
    out = await _update_resource(db, MagicMock(id="u1"), {"resource_id": "r1", "name": "越权改名"})
    assert out == {"error": "应急资源不存在", "verified": False}
    sql = str(captured["stmt"])
    assert "emergency_resources" in sql
    assert "enterprises" in sql
    assert "user_id" in sql
    assert "u1" in captured["stmt"].compile().params.values()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_resource_checks_ownership_via_enterprise():
    """他人应急资源的 delete 必须走 enterprise→user 归属校验并返回 error。"""
    from app.services.chat_dispatch import _delete_resource

    db = AsyncMock()
    captured = {}

    async def fake_execute(stmt, *a, **kw):
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = fake_execute
    out = await _delete_resource(db, MagicMock(id="u1"), {"resource_id": "r1"})
    assert out == {"error": "应急资源不存在", "verified": False}
    sql = str(captured["stmt"])
    assert "emergency_resources" in sql
    assert "enterprises" in sql
    assert "user_id" in sql
    assert "u1" in captured["stmt"].compile().params.values()
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_risk_assessment_rejects_other_users_report():
    """读取他人企业评估报告必须按 enterprise→user 校验并返回 error。"""
    from app.services.chat_dispatch import _get_risk_assessment

    db = AsyncMock()
    report = MagicMock(id="r1", enterprise_id="e1", status="draft",
                       content="涉密正文", created_at="2026-09-02")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: report),  # report 查询
        MagicMock(scalar_one_or_none=lambda: None),    # enterprise 归属查询
    ])
    out = await _get_risk_assessment(db, MagicMock(id="u1"), {"report_id": "r1"})
    assert out == {"error": "报告不存在或无权访问"}


@pytest.mark.asyncio
async def test_get_risk_assessment_returns_when_owned():
    """本人企业下的评估报告可正常读取。"""
    from app.services.chat_dispatch import _get_risk_assessment

    db = AsyncMock()
    report = MagicMock(id="r1", enterprise_id="e1", status="draft",
                       content="正文", created_at="2026-09-02")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: report),  # report 查询
        MagicMock(scalar_one_or_none=lambda: "e1"),    # enterprise 归属查询命中
    ])
    out = await _get_risk_assessment(db, MagicMock(id="u1"), {"report_id": "r1"})
    assert out["id"] == "r1"
    assert out["content"] == "正文"


@pytest.mark.asyncio
async def test_get_resource_investigation_rejects_other_users_report():
    """读取他人企业调查报告必须按 enterprise→user 校验并返回 error。"""
    from app.services.chat_dispatch import _get_resource_investigation

    db = AsyncMock()
    report = MagicMock(id="r1", enterprise_id="e1", status="draft",
                       content="涉密正文", created_at="2026-09-02")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: report),  # report 查询
        MagicMock(scalar_one_or_none=lambda: None),    # enterprise 归属查询
    ])
    out = await _get_resource_investigation(db, MagicMock(id="u1"), {"report_id": "r1"})
    assert out == {"error": "报告不存在或无权访问"}


@pytest.mark.asyncio
async def test_get_resource_investigation_returns_when_owned():
    """本人企业下的调查报告可正常读取。"""
    from app.services.chat_dispatch import _get_resource_investigation

    db = AsyncMock()
    report = MagicMock(id="r1", enterprise_id="e1", status="draft",
                       content="正文", created_at="2026-09-02")
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: report),  # report 查询
        MagicMock(scalar_one_or_none=lambda: "e1"),    # enterprise 归属查询命中
    ])
    out = await _get_resource_investigation(db, MagicMock(id="u1"), {"report_id": "r1"})
    assert out["id"] == "r1"
    assert out["content"] == "正文"


@pytest.mark.asyncio
async def test_list_risk_assessments_rejects_unowned_enterprise():
    """list 接口传他人 enterprise_id 必须返回 error。"""
    from app.services.chat_dispatch import _list_risk_assessments

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _list_risk_assessments(db, MagicMock(id="u1"), {"enterprise_id": "e1"})
    assert out == {"error": "企业不存在或无权访问", "verified": False}


@pytest.mark.asyncio
async def test_list_risk_assessments_allows_owned_enterprise():
    """list 接口传本人 enterprise_id 正常返回列表。"""
    from app.services.chat_dispatch import _list_risk_assessments

    db = AsyncMock()
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: "e1"),  # enterprise 归属查询命中
        rows_result,                                  # 报告列表查询
    ])
    out = await _list_risk_assessments(db, MagicMock(id="u1"), {"enterprise_id": "e1"})
    assert out == {"assessments": []}


@pytest.mark.asyncio
async def test_list_resource_investigations_rejects_unowned_enterprise():
    """list 接口传他人 enterprise_id 必须返回 error。"""
    from app.services.chat_dispatch import _list_resource_investigations

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _list_resource_investigations(db, MagicMock(id="u1"), {"enterprise_id": "e1"})
    assert out == {"error": "企业不存在或无权访问", "verified": False}


@pytest.mark.asyncio
async def test_list_resource_investigations_allows_owned_enterprise():
    """list 接口传本人 enterprise_id 正常返回列表。"""
    from app.services.chat_dispatch import _list_resource_investigations

    db = AsyncMock()
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=lambda: "e1"),  # enterprise 归属查询命中
        rows_result,                                  # 报告列表查询
    ])
    out = await _list_resource_investigations(db, MagicMock(id="u1"), {"enterprise_id": "e1"})
    assert out == {"investigations": []}
