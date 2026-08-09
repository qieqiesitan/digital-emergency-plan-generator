"""Onboarding 路由端点级测试（独立应用挂载 router，覆盖依赖与文件上传路径）。"""
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import onboarding
from app.routers.onboarding import MAX_IMPORT_BYTES


@pytest.fixture()
def client(monkeypatch):
    app = FastAPI()
    app.include_router(onboarding.router)

    from app.models.user import User

    current_user = User(id="u1", email="a@b.c", name="A", role="admin")

    def _override_user():
        return current_user

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db

    # 单文件上传测试中文件大小上限按常量读取，这里固定为小值便于断言
    monkeypatch.setattr(onboarding, "MAX_IMPORT_BYTES", 64)

    with TestClient(app) as test_client:
        yield test_client, current_user


def _override_db():
    from unittest.mock import AsyncMock

    return AsyncMock()


def _enterprise(**overrides):
    from unittest.mock import MagicMock

    ent = MagicMock()
    ent.id = "e1"
    ent.user_id = "u1"
    ent.name = "甲公司"
    ent.address = "地址"
    ent.industry = "化工"
    ent.business_scope = "化工生产"
    ent.employee_count = 100
    ent.org_structure = [{"group_key": "cmd", "group_name": "指挥部",
                          "members": [{"name": "张三", "role": "chief"}]}]
    ent.surrounding_info = {"nearby_units": [{"name": "加油站"}], "sensitive_targets": []}
    for key, value in overrides.items():
        setattr(ent, key, value)
    return ent


def _rows_result(rows):
    from unittest.mock import Mock

    res = Mock()
    res.scalars.return_value.all.return_value = rows
    return res


def _completion_db(ent):
    from unittest.mock import AsyncMock, MagicMock

    db = AsyncMock()

    def fake_execute(stmt):
        text = str(stmt)
        if "FROM enterprises" in text:
            res = MagicMock()
            res.scalar_one_or_none.return_value = ent
            return res
        if "risk_events" in text:
            return _rows_result([MagicMock(id="e1", chemical_id="c1")])
        if "hazardous_chemicals" in text:
            return _rows_result([MagicMock(id="c1")])
        if "emergency_resources" in text:
            return _rows_result([MagicMock(id="r1")])
        if "risk_assessment_reports" in text:
            return _rows_result([MagicMock(status="completed")])
        if "resource_investigation_reports" in text:
            return _rows_result([MagicMock(status="completed")])
        return _rows_result([])

    db.execute.side_effect = fake_execute
    return db


def test_completion_owner_200(client):
    test_client, current_user = client
    app = test_client.app
    ent = _enterprise()
    app.dependency_overrides[get_db] = lambda: _completion_db(ent)
    resp = test_client.get("/enterprises/e1/completion")
    assert resp.status_code == 200
    assert resp.json()["data"]["percent"] == 100


def test_completion_not_owner_404(client):
    test_client, _ = client
    app = test_client.app
    app.dependency_overrides[get_db] = lambda: _completion_db(None)
    resp = test_client.get("/enterprises/e1/completion")
    assert resp.status_code == 404


def test_candidates_org_200(client, monkeypatch):
    test_client, _ = client
    app = test_client.app
    app.dependency_overrides[get_db] = lambda: _completion_db(_enterprise())

    async def fake_generate(enterprise_info, db):
        return [{"group_key": "cmd", "group_name": "应急救援指挥部", "members": []}]

    monkeypatch.setattr(onboarding, "generate_org_candidates", fake_generate)
    resp = test_client.post("/onboarding/candidates", json={"enterprise_id": "e1", "module": "org"})
    assert resp.status_code == 200
    assert resp.json()["data"]["items"][0]["group_key"] == "cmd"


def test_candidates_not_owner_404(client, monkeypatch):
    test_client, _ = client
    app = test_client.app
    app.dependency_overrides[get_db] = lambda: _completion_db(None)

    async def fake_generate(enterprise_info, db):
        raise AssertionError("不应调用生成函数")

    monkeypatch.setattr(onboarding, "generate_org_candidates", fake_generate)
    resp = test_client.post("/onboarding/candidates", json={"enterprise_id": "e1", "module": "org"})
    assert resp.status_code == 404


def test_candidates_non_org_module_400(client):
    test_client, _ = client
    resp = test_client.post(
        "/onboarding/candidates",
        json={"enterprise_id": "e1", "module": "risk_chemical"},
    )
    assert resp.status_code == 400


def test_import_auto_classifies_200(client, monkeypatch):
    test_client, _ = client

    async def fake_classify(text, db):
        return ["risk_chemical"]

    async def fake_extract(module, text, db):
        return [{"name": "甲醇", "cas_no": "67-56-1"}]

    monkeypatch.setattr(onboarding, "classify_modules", fake_classify)
    monkeypatch.setattr(onboarding, "extract_candidates", fake_extract)
    resp = test_client.post(
        "/onboarding/import",
        files={
            "file": ("risk.txt", io.BytesIO("含甲醇的台账".encode("utf-8")), "text/plain")
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["module"] == "risk_chemical"
    assert data["candidates"] == [{"name": "甲醇", "cas_no": "67-56-1"}]
    assert data["source"] == "risk.txt"


def test_import_unknown_module_400(client, monkeypatch):
    test_client, _ = client

    async def fake_extract(module, text, db):
        raise AssertionError("不应调用提取函数")

    monkeypatch.setattr(onboarding, "extract_candidates", fake_extract)
    resp = test_client.post(
        "/onboarding/import",
        params={"module": "unknown_module"},
        files={"file": ("a.txt", io.BytesIO(b"some text"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "未知模块" in resp.json()["detail"]


def test_import_corrupt_file_400(client):
    test_client, _ = client
    resp = test_client.post(
        "/onboarding/import",
        files={
            "file": (
                "bad.xlsx",
                io.BytesIO(b"\x00\x01\x02not-a-real-xlsx"),
                "application/octet-stream",
            )
        },
    )
    assert resp.status_code == 400


def test_import_oversize_413(client):
    test_client, _ = client
    resp = test_client.post(
        "/onboarding/import",
        files={"file": ("big.txt", io.BytesIO(b"x" * (MAX_IMPORT_BYTES + 1)), "text/plain")},
    )
    assert resp.status_code == 413
    assert "20MB" in resp.json()["detail"]


def test_import_batch_two_files_two_results(client, monkeypatch):
    test_client, _ = client
    call_log = []

    async def fake_classify(text, db):
        call_log.append(text)
        if "企业信息" in text:
            return ["enterprise_info"]
        return ["resources"]

    async def fake_extract(module, text, db):
        return []

    monkeypatch.setattr(onboarding, "classify_modules", fake_classify)
    monkeypatch.setattr(onboarding, "extract_candidates", fake_extract)
    resp = test_client.post(
        "/onboarding/import/batch",
        files=[
            ("files", ("f1.txt", io.BytesIO("企业信息文档".encode("utf-8")), "text/plain")),
            ("files", ("f2.txt", io.BytesIO("应急资源文档".encode("utf-8")), "text/plain")),
        ],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [item["module"] for item in data] == ["enterprise_info", "resources"]
    assert len(call_log) == 2


def test_import_batch_empty_classification_skips(client, monkeypatch):
    test_client, _ = client

    async def fake_classify(text, db):
        return []

    async def fake_extract(module, text, db):
        raise AssertionError("分类为空不应调用提取函数")

    monkeypatch.setattr(onboarding, "classify_modules", fake_classify)
    monkeypatch.setattr(onboarding, "extract_candidates", fake_extract)
    resp = test_client.post(
        "/onboarding/import/batch",
        files=[("files", ("f1.txt", io.BytesIO(b"unknown content"), "text/plain"))],
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_import_batch_oversize_413(client):
    test_client, _ = client
    resp = test_client.post(
        "/onboarding/import/batch",
        files=[("files", ("big.txt", io.BytesIO(b"x" * (MAX_IMPORT_BYTES + 1)), "text/plain"))],
    )
    assert resp.status_code == 413
    assert "20MB" in resp.json()["detail"]
