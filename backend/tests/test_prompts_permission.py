"""prompts 路由权限测试：全局提示词模板增删改必须管理员（体检报告 S8）。"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.routers import prompts


class _FakeSession:
    """极简内存会话：覆盖 prompts 路由用到的 execute/add/commit/refresh。"""

    def __init__(self, existing=None, rows=None):
        self._existing = existing
        self._rows = rows if rows is not None else []

    async def execute(self, stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = self._existing
        result.scalars.return_value.all.return_value = self._rows
        return result

    def add(self, obj):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


def _make_client(role, existing=None, rows=None):
    def _override_user():
        return User(id="u1", email="user@example.com", name="用户", role=role)

    app = FastAPI()
    app.include_router(prompts.router)
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _FakeSession(existing=existing, rows=rows)
    return TestClient(app)


def _create_payload():
    return {
        "template_code": "demo_code",
        "template_name": "演示模板",
        "category": "demo",
    }


def test_create_prompt_requires_admin():
    client = _make_client(role="user")
    resp = client.post("/prompts", json=_create_payload())
    assert resp.status_code == 403


def test_update_prompt_requires_admin():
    client = _make_client(role="user")
    resp = client.put("/prompts/1", json={"template_name": "越权改名"})
    assert resp.status_code == 403


def test_create_prompt_allowed_for_admin():
    client = _make_client(role="admin")
    resp = client.post("/prompts", json=_create_payload())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["template_code"] == "demo_code"
    assert data["templateName"] == "演示模板"


def test_update_prompt_allowed_for_admin():
    existing = MagicMock()
    existing.id = 1
    existing.template_code = "demo_code"
    existing.template_name = "旧名"
    existing.category = "demo"
    client = _make_client(role="super_admin", existing=existing)
    resp = client.put("/prompts/1", json={"template_name": "新名"})
    assert resp.status_code == 200
    assert resp.json()["data"]["templateName"] == "新名"


def test_list_prompts_allowed_for_regular_user():
    """只读列表不设管理员门禁，普通用户可访问。"""
    row = MagicMock()
    row.id = 1
    row.template_code = "demo_code"
    row.template_name = "演示模板"
    row.category = "demo"
    row.system_prompt = ""
    row.user_prompt_template = ""
    row.model_id = None
    row.temperature = 0.7
    row.max_tokens = 4096
    row.description = None
    row.variables = None
    row.status = "active"
    client = _make_client(role="user", rows=[row])
    resp = client.get("/prompts")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["template_code"] == "demo_code"
