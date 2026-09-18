"""外部对接 POST /api/external/plans 的订单幂等（2026-09-18 补）。

中间件只校验签名与 ±5 分钟时间窗，**不做重放防护**；而创建接口此前每次调用都新建
PlanProject 并启动一次 AI 生成 —— 外部商城超时重试（或签名被重放）就会重复开单、
重复消耗模型额度。现按 `external_order_id` 做幂等：
  - 抢到订单租约 → 正常创建，把 plan_id 写进 `external_order:{id}`；
  - 没抢到且已有 plan_id → 返回同一个 task_id（真正的幂等）；
  - 没抢到且还没有 plan_id（首单进行中）→ 409。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers import external as ext


def _payload(order_id="ORDER-1"):
    return ext.ExternalPlanCreate(
        external_order_id=order_id,
        external_user_id="ext-user-1",
        plan_type="comprehensive",
        enterprise=ext.ExternalEnterpriseData(name="探针企业"),
        documents=[],
        callback_url="",
    )


@pytest.mark.asyncio
async def test_repeated_order_returns_same_task_without_creating_plan():
    """第二次调用直接返回既有 task_id，不再进入创建分支。"""
    created = MagicMock()
    created.id = "plan-existing"

    with patch.object(ext, "try_acquire_lease", AsyncMock(return_value=False)), \
         patch.object(ext, "get_state", AsyncMock(return_value={"plan_id": "plan-existing"})), \
         patch.object(ext, "async_session") as session_factory, \
         patch.object(ext, "spawn") as spawn_mock:
        out = await ext.external_create_plan(_payload(), MagicMock())

    assert out.data.task_id == "plan-existing"
    assert out.data.status == "accepted"
    session_factory.assert_not_called()
    spawn_mock.assert_not_called()


@pytest.mark.asyncio
async def test_order_in_progress_returns_409():
    with patch.object(ext, "try_acquire_lease", AsyncMock(return_value=False)), \
         patch.object(ext, "get_state", AsyncMock(return_value={"owner": "external_api"})):
        with pytest.raises(HTTPException) as ei:
            await ext.external_create_plan(_payload(), MagicMock())
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_failure_releases_order_lease(monkeypatch):
    """创建过程失败要放掉租约，否则订单号被毒化 24h。"""
    release = AsyncMock()

    async def _boom(_db, _uid, _ent):
        raise RuntimeError("db down")

    monkeypatch.setattr(ext, "try_acquire_lease", AsyncMock(return_value=True))
    monkeypatch.setattr(ext, "_ensure_user_and_enterprise", _boom)

    with patch("app.services.runtime_state.release_lease", release):
        with pytest.raises(RuntimeError):
            await ext.external_create_plan(_payload(), MagicMock())
    release.assert_awaited()
