"""W0 安全止血回归测试：鉴权依赖断言 + 关键行为验证（先失败后修复）。"""

import importlib.util
import os
import socket
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.routers import export_tasks, extraction, generation, ingest, major_hazard, platform, regulations, work_ticket


def _routes_for(path: str):
    return [r for r in app.routes if getattr(r, "path", "") == path]


def _dep_names(route) -> set[str]:
    names: set[str] = set()

    def walk(dep):
        call = getattr(dep, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", str(call)))
        for sub in getattr(dep, "dependencies", []) or []:
            walk(sub)

    for dep in route.dependant.dependencies:
        walk(dep)
    return names


def _assert_routes_have(path: str, dep: str, methods=("GET",)):
    found = False
    for route in _routes_for(path):
        if getattr(route, "methods", set()) & set(methods):
            found = True
            assert dep in _dep_names(route), f"{path} {methods} 缺少 {dep}，实际：{_dep_names(route)}"
    assert found, f"未找到路由 {path}"


# ── 1. 老 P0：导出下载 / 停止生成 / 法规写操作 ──

def test_export_download_requires_auth():
    _assert_routes_have("/api/v1/export/download/{file_key}", "get_current_user")


def test_export_task_status_requires_auth():
    _assert_routes_have("/api/v1/export/tasks/{task_id}", "get_current_user")


def test_stop_generation_requires_auth():
    _assert_routes_have("/api/v1/plans/{plan_id}/generate/stop", "get_current_user", methods=("POST",))


@pytest.mark.parametrize("path,methods", [
    ("/api/v1/regulations", ("POST",)),
    ("/api/v1/regulations/{regulation_id}", ("PUT", "DELETE")),
    ("/api/v1/regulations/batch/abolish", ("POST",)),
    ("/api/v1/regulations/{regulation_id}/abolish", ("POST",)),
    ("/api/v1/regulations/rebuild-index", ("POST",)),
])
def test_regulation_writes_require_admin(path, methods):
    _assert_routes_have(path, "require_admin", methods=methods)


# ── 2. 新模块：平台 / 数据接入 / 抽取 ──

@pytest.mark.parametrize("path,methods", [
    ("/api/v1/platform/capabilities", ("GET",)),
    ("/api/v1/platform/capabilities/{code}", ("PUT",)),
    ("/api/v1/platform/ai-usage", ("GET",)),
    ("/api/v1/platform/overview", ("GET",)),
])
def test_platform_requires_admin(path, methods):
    _assert_routes_have(path, "require_admin", methods=methods)


@pytest.mark.parametrize("path,methods", [
    ("/api/v1/ingest/sources", ("GET", "POST")),
    ("/api/v1/ingest/jobs", ("GET",)),
    ("/api/v1/ingest/items", ("GET",)),
])
def test_ingest_requires_admin(path, methods):
    _assert_routes_have(path, "require_admin", methods=methods)


@pytest.mark.parametrize("path,methods", [
    ("/api/v1/extraction/parse-file", ("POST",)),
    ("/api/v1/extraction/run", ("POST",)),
    ("/api/v1/extraction/suggest-mapping", ("POST",)),
])
def test_extraction_requires_admin(path, methods):
    _assert_routes_have(path, "require_admin", methods=methods)


# ── 3. 新模块：作业票 / 重大危险源 ──

@pytest.mark.parametrize("path,methods", [
    ("/api/v1/work-ticket/templates", ("GET",)),
    ("/api/v1/work-ticket/tickets", ("GET",)),
    ("/api/v1/work-ticket/tickets/{ticket_id}", ("GET",)),
    ("/api/v1/work-ticket/tickets/{ticket_id}/gas-tests", ("POST",)),
])
def test_work_ticket_reads_and_gas_tests_require_auth(path, methods):
    _assert_routes_have(path, "get_current_user", methods=methods)


def test_major_hazard_router_level_auth():
    dep_names = set()
    for dep in major_hazard.router.dependencies:
        call = getattr(dep, "dependency", None) or getattr(dep, "call", None)
        dep_names.add(getattr(call, "__name__", str(call)))
    assert "get_current_user" in dep_names, f"major_hazard router 缺少 get_current_user：{dep_names}"


# ── 4. 行为：下载接口不再泄漏任意导出文件 ──

def _client_for(router, user_role: str = "user"):
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock()
        yield db

    async def _user():
        user = MagicMock()
        user.id = "u1"
        user.role = user_role
        return user

    test_app.dependency_overrides[get_db] = _db
    test_app.dependency_overrides[get_current_user] = _user
    return TestClient(test_app)


def test_export_download_rejects_unmapped_file_key(tmp_path, monkeypatch):
    """历史开发产物（如下划线脚本/PDF）不属于任何业务实体，必须 404。"""
    monkeypatch.setattr(export_tasks.settings, "EXPORT_DIR", str(tmp_path))
    (tmp_path / "_regen_real.pdf").write_bytes(b"%PDF-1.4 secret")
    client = _client_for(export_tasks.router, user_role="admin")
    resp = client.get("/api/v1/export/download/_regen_real.pdf")
    assert resp.status_code == 404


# ── 5. 8082 自托管前端：路径穿越必须被拒绝 ──

def _load_frontend_server():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("frontend_server", root / "frontend" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _raw_get(port: int, target: str) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(f"GET {target} HTTP/1.0\r\nHost: x\r\n\r\n".encode())
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks)


def test_frontend_static_server_rejects_path_traversal(tmp_path):
    mod = _load_frontend_server()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-VALUE", encoding="utf-8")
    mod.DIST_DIR = str(dist)
    server = ThreadingHTTPServer(("127.0.0.1", 0), mod.ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        ok = _raw_get(port, "/index.html")
        assert b"200" in ok.split(b"\r\n", 1)[0] or b"200" in ok.split(b"\n", 1)[0]
        bad = _raw_get(port, "/../secret.txt")
        assert b"TOP-SECRET-VALUE" not in bad
        assert b"404" in bad.split(b"\n", 1)[0]
    finally:
        server.shutdown()


# ── 6. 作业票：操作人资格（W0-2） ──

@pytest.mark.anyio
async def test_eligible_users_role_name_matches_org_position():
    """岗位名（如「主管领导」）应按企业组织树的岗位名称匹配成员，而非系统角色。"""
    from app.services.work_ticket_service import eligible_users_for_node

    node = MagicMock()
    node.countersign_units = None
    node.role_code = "主管领导"

    org = [
        {"id": "root", "name": "公司", "parent_id": None},
        {"id": "pos1", "name": "主管领导", "parent_id": "root"},
        {"id": "pos2", "name": "安全管理", "parent_id": "root"},
    ]
    calls = {"n": 0}

    async def execute(stmt, *a, **k):
        calls["n"] += 1
        res = MagicMock()
        if calls["n"] == 1:  # 成员查询
            res.all.return_value = [("u-boss", "pos1"), ("u-safety", "pos2")]
        else:  # 组织树查询
            res.scalar_one_or_none.return_value = org
        return res

    db = MagicMock()
    db.execute = execute
    users = await eligible_users_for_node(db, node, enterprise_id="e1")
    assert users == ["u-boss"]


def test_node_action_returns_403_when_operator_not_eligible(monkeypatch):
    """非会签资格人执行审批 → 403（原实现会记录其签名并放行）。"""
    from app.services.work_ticket_service import WorkTicketPermissionError

    async def deny(*a, **k):
        raise WorkTicketPermissionError("当前用户不是该节点的会签人")

    async def allow_owned(*a, **k):
        return MagicMock(id="t1", enterprise_id="e1")

    monkeypatch.setattr(work_ticket, "act_on_node", deny)
    monkeypatch.setattr(work_ticket, "ensure_ticket_owned", allow_owned)
    client = _client_for(work_ticket.router, user_role="user")
    resp = client.post(
        "/api/v1/work-ticket/tickets/t1/node-action",
        json={"action": "approve", "opinion": "ok"},
    )
    assert resp.status_code == 403
