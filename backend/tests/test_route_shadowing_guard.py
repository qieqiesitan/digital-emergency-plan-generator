"""路由遮蔽守护：字面量路径不得被参数化路径抢先匹配（2026-09-18 修）。

踩过的坑：`enterprise_sub.router` 注册在 `resources_ext.router` 之前，且详情路由写成
`/{enterprise_id}/resources/{resource_id}`（无类型约束）——于是
`GET /enterprises/{id}/resources/template` 被它抢先匹配，"template" 当 UUID 解析失败返回 422，
**资源导入模板下载直接不可用**（前端「第一步：下载模板」必失败）。
约束成 `:uuid` 后字面量路径不再被吞。
"""

from pathlib import Path

ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "enterprise_sub.py"


def test_resource_detail_routes_are_uuid_constrained():
    src = ROUTER.read_text(encoding="utf-8")
    assert src.count("{resource_id:uuid}") == 3, "GET/PUT/DELETE 三条详情路由都要约束为 uuid"
    assert '/resources/{resource_id}"' not in src, "不得再出现未约束的 resource_id 路径"


def test_literal_resource_routes_exist_in_resources_ext():
    """模板下载这类字面量路由必须存在（防止被误删后静默 404/422）。"""
    ext = (ROUTER.parent / "resources_ext.py").read_text(encoding="utf-8")
    assert "/{enterprise_id}/resources/template" in ext
    assert "/{enterprise_id}/resources/import" in ext
