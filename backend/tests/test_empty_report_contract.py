"""报告「尚未生成」的空态契约：读报告正文返回 200 + data=None，而不是 404。

背景：企业还没生成报告时，报告工作台首屏（桌面/移动端）都会读这份报告。
原来用 404 表达「还没有」：浏览器必然在控制台留一条红字 404，前端还得把
「预期空态」当异常兜底（全局拦截器顺手弹一个错误提示）。

契约（本次修复）：
  - 企业存在、但没有可读报告 → 200 + data=None（空态）
  - 企业不存在 / 无权访问   → 仍 404（两者必须可区分）
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.user import User
from app.routers import resource_investigation, risk_assessment


def _ent():
    return Enterprise(id="e1", user_id="u1", name="甲公司")


def _scalar(value):
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


@contextmanager
def _client(mod, report, enterprise=_ent):
    """挂载单个路由模块；db.execute 按 SQL 文本分发企业 / 报告两次查询。"""
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="a@b.c", name="A", role="admin"
    )

    db = AsyncMock()

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(enterprise())
        return _scalar(report)

    db.execute.side_effect = fake_execute
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client


def test_risk_assessment_without_report_returns_empty_state():
    with _client(risk_assessment, report=None) as client:
        resp = client.get("/enterprises/e1/risk-assessment")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"] is None


def test_resource_investigation_without_report_returns_empty_state():
    with _client(resource_investigation, report=None) as client:
        resp = client.get("/enterprises/e1/resource-investigation")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] is None


def test_missing_enterprise_still_404():
    """空态改用 200 后，越权/企业不存在必须仍能被识别为 404。"""
    with _client(risk_assessment, report=None, enterprise=lambda: None) as client:
        resp = client.get("/enterprises/e1/risk-assessment")
    assert resp.status_code == 404
