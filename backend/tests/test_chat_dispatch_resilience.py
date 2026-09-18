"""聊天工具层：坏工具不得毒化同轮其它工具 + list_templates 字段契约（2026-09-18 修）。

实测：`list_templates` 访问了 PlanTemplate 上不存在的 `description`，必然抛
AttributeError；而 `dispatch` 对所有异常一律 `await db.rollback()`，回滚把会话里
已加载对象置为过期态 → 之后任何访问关系属性的工具都会报
`greenlet_spawn has not been called; can't call await_only() here`。
结果是：用户问一句触发该工具，**同一轮里后续工具全废**。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.services import chat_dispatch


@pytest.mark.asyncio
async def test_plain_exception_does_not_rollback_session():
    """普通 Python 异常不回滚（回滚会让后续工具连锁失败）。"""
    db = MagicMock()
    db.rollback = AsyncMock()
    db.expunge_all = MagicMock()

    async def boom(_db, _user, _args):
        raise AttributeError("'PlanTemplate' object has no attribute 'description'")

    chat_dispatch._FUNCTIONS["_probe_boom"] = boom
    try:
        out = await chat_dispatch.dispatch(db, MagicMock(), "_probe_boom", {})
    finally:
        chat_dispatch._FUNCTIONS.pop("_probe_boom", None)

    assert "description" in json.loads(out)["error"]
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_db_error_rolls_back_and_clears_identity_map():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.expunge_all = MagicMock()

    async def db_boom(_db, _user, _args):
        raise OperationalError("SELECT 1", {}, Exception("connection lost"))

    chat_dispatch._FUNCTIONS["_probe_db_boom"] = db_boom
    try:
        out = await chat_dispatch.dispatch(db, MagicMock(), "_probe_db_boom", {})
    finally:
        chat_dispatch._FUNCTIONS.pop("_probe_db_boom", None)

    assert "error" in json.loads(out)
    db.rollback.assert_awaited()
    db.expunge_all.assert_called_once()


@pytest.mark.asyncio
async def test_list_templates_returns_existing_fields_only():
    """返回字段必须都存在于 PlanTemplate 模型上（避免再次写错列名）。"""
    from app.models.enterprise import PlanTemplate

    tpl = PlanTemplate(plan_type="comprehensive", name="综合应急预案模板",
                       version="1.0", structure=[{"key": "sec_1"}], is_active=True)
    tpl.id = "tpl-1"
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [tpl]
    db.execute = AsyncMock(return_value=result)

    out = await chat_dispatch._list_templates(db, MagicMock(), {})
    item = out["templates"][0]
    assert set(item) == {"id", "name", "plan_type", "version", "section_count"}
    assert item["section_count"] == 1
    for key in item:
        assert key in PlanTemplate.__table__.columns or key == "section_count"


@pytest.mark.asyncio
async def test_delete_plan_message_uses_title_not_name():
    """删除预案的提示必须带上真实标题（PlanProject 字段是 title，不是 name）。"""
    from app.models.enterprise import PlanProject

    plan = MagicMock(spec=PlanProject)
    plan.id = "p1"
    plan.title = "巡检-预案"
    del plan.name  # 模型上根本没有 name 属性
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    out = await chat_dispatch._delete_plan(db, MagicMock(id="u1"), {"plan_id": "p1"})
    assert "巡检-预案" in out["message"], out
