"""报告版本路由（风险评估/资源调查共用工厂）端点测试。"""
from unittest.mock import AsyncMock, MagicMock
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.report_version import RiskAssessmentVersion
from app.models.risk_assessment import RiskAssessmentReport
from app.models.user import User
from app.routers.report_versions import build_report_versions_router


def _ent():
    return Enterprise(id="e1", user_id="u1", name="甲公司")


def _report(**kw):
    r = RiskAssessmentReport(
        id="r1", enterprise_id="e1", title="风险评估报告",
        content="markdown 内容", summary={"ch1": "x"}, status="completed",
        current_version=2,
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _version(**kw):
    v = RiskAssessmentVersion(
        id="v1", report_id="r1", version_number=2,
        content="markdown 旧内容", summary={"ch1": "旧"}, created_by="manual",
    )
    for k, val in kw.items():
        setattr(v, k, val)
    return v


def _scalar(value):
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


@contextmanager
def _make_client(report, version=None, versions=None):
    app = FastAPI()
    app.include_router(build_report_versions_router("risk-assessment", RiskAssessmentReport, RiskAssessmentVersion))

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="admin")

    app.dependency_overrides[get_current_user] = _override_user
    db = AsyncMock()

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(_ent())
        if "FROM risk_assessment_reports" in text:
            return _scalar(report)
        if "FROM risk_assessment_versions" in text:
            if "risk_assessment_versions.id =" in text:
                return _scalar(version or _version())
            res = MagicMock()
            res.scalars.return_value.all.return_value = versions if versions is not None else [_version()]
            return res
        return _scalar(None)

    db.execute.side_effect = fake_execute
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        test_client.app.state.db = db
        yield test_client


def test_create_version_snapshots_content_and_bumps_version():
    report = _report()
    with _make_client(report) as client:
        resp = client.post("/enterprises/e1/risk-assessment/versions")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["version_number"] == 3
    assert report.current_version == 3
    added = client.app.state.db.add.call_args[0][0]
    assert isinstance(added, RiskAssessmentVersion)
    assert added.version_number == 3
    assert added.content == "markdown 内容"
    assert added.summary == {"ch1": "x"}


def test_list_versions_desc():
    with _make_client(_report(), versions=[_version(version_number=2)]) as client:
        resp = client.get("/enterprises/e1/risk-assessment/versions")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["version_number"] == 2
    assert items[0]["id"] == "v1"


def test_rollback_restores_content_and_current_version():
    report = _report()
    with _make_client(report, version=_version()) as client:
        resp = client.post("/enterprises/e1/risk-assessment/versions/v1/rollback")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "V2" in body["message"]
    assert body["current_version"] == 2
    assert report.content == "markdown 旧内容"
    assert report.summary == {"ch1": "旧"}
    assert report.current_version == 2


def test_save_content_persists_markdown():
    report = _report()
    with _make_client(report) as client:
        resp = client.put("/enterprises/e1/risk-assessment/content", json={"content": "新 markdown 正文"})
    assert resp.status_code == 200
    assert report.content == "新 markdown 正文"
    assert resp.json()["data"]["content_length"] == len("新 markdown 正文")
