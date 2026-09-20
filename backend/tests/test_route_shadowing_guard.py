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


def test_risk_source_detail_routes_are_uuid_constrained():
    """同理：risk_id 详情路由不约束会把 /risk-sources/template 吞掉（实测 422）。"""
    src = ROUTER.read_text(encoding="utf-8")
    assert src.count("{risk_id:uuid}") == 3, "GET/PUT/DELETE 三条风险源详情路由都要约束为 uuid"
    assert '/risk-sources/{risk_id}"' not in src


def test_literal_risk_source_routes_exist():
    ext = (ROUTER.parent / "risk_sources_ext.py").read_text(encoding="utf-8")
    assert "/{enterprise_id}/risk-sources/template" in ext
    assert "/{enterprise_id}/risk-sources/import" in ext


def test_import_templates_mark_sample_rows_and_importers_skip_them():
    """模板示例行必须自标识【示例】并在导入时跳过（否则示例数据会被整批导进台账）。"""
    for name in ("resources_ext.py", "risk_sources_ext.py"):
        src = (ROUTER.parent / name).read_text(encoding="utf-8")
        assert "【示例】" in src, f"{name} 模板示例行未自标识"
        assert 'if "【示例】" in str(row[1] or "")' in src, f"{name} 未跳过示例行"
        assert "skipped_examples" in src, f"{name} 未返回示例行计数"


def test_plan_version_literal_route_precedes_parameterized_route():
    """`/plans/{id}/versions/compare` 必须在 `/versions/{version_id}` 之前，
    且后者必须约束为 uuid——否则 "compare" 会被当版本 id 查库（实测 422，对比功能不可用）。"""
    src = (ROUTER.parent / "versions.py").read_text(encoding="utf-8")
    assert src.index('"/{plan_id}/versions/compare"') < src.index('"/{plan_id}/versions/{version_id:uuid}"')
    assert '/versions/{version_id}"' not in src


def test_literal_resource_routes_exist_in_resources_ext():
    """模板下载这类字面量路由必须存在（防止被误删后静默 404/422）。"""
    ext = (ROUTER.parent / "resources_ext.py").read_text(encoding="utf-8")
    assert "/{enterprise_id}/resources/template" in ext
    assert "/{enterprise_id}/resources/import" in ext


# ── 通用检测器（2026-09-20 补）：不再依赖"人工列举"，扫全量路由 ──────────────

_TYPE_PATTERN = {
    "uuid": r"[0-9a-fA-F\-]{36}",
    "int": r"\d+",
    "float": r"\d+(?:\.\d+)?",
    "path": r".+",
}


def _route_regex(path: str) -> str:
    """把 FastAPI 路径模板转成正则：`{x:uuid}` 按类型约束，`{x}` 视为任意非斜杠段。"""
    import re

    def repl(match: "re.Match") -> str:
        body = match.group(1)
        if ":" in body:
            _, _, type_name = body.partition(":")
            return _TYPE_PATTERN.get(type_name.strip(), r"[^/]+")
        return r"[^/]+"

    return "^" + re.sub(r"\{([^}]+)\}", repl, path) + "$"


def test_no_literal_route_is_shadowed_by_earlier_parameterized_route():
    """全量路由扫描：注册在前的**无约束**参数路由不得吞掉后面的字面量路由。

    项目已经栽过 3 次（resources/template、risk-sources/template、versions/compare），
    每次都表现为"422 或 404，功能整体不可用"。这里按注册顺序做一次全量判定：
    若 `{x}` 未加类型约束且其正则可以匹配后来的字面量路径，则该字面量永不可达。
    """
    import re

    from app.main import app

    entries: list[tuple[str, str, str]] = []   # (method, path, raw_path)
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            entries.append((method, _route_regex(path), path))

    shadowed: list[str] = []
    for i, (m1, rx1, raw1) in enumerate(entries):
        if "{" not in raw1:
            continue
        for m2, _rx2, raw2 in entries[i + 1:]:
            if m1 != m2 or "{" in raw2:
                continue
            if re.match(rx1, raw2):
                shadowed.append(f"{m1} {raw2} 被更早注册的 {raw1} 吞掉")

    assert not shadowed, "发现路由遮蔽（字面量路径不可达）：\n  " + "\n  ".join(shadowed)


def test_no_duplicate_method_path_registration():
    """同一个 method+path 不得注册两次（后者永不生效，且容易改错一处）。"""
    from collections import Counter

    from app.main import app

    counter: Counter = Counter()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            counter[(method, path)] += 1
    dup = [f"{m} {p} ×{n}" for (m, p), n in counter.items() if n > 1]
    assert not dup, "重复注册的 method+path：\n  " + "\n  ".join(dup)


def test_detector_actually_detects_historical_case():
    """自我验证：检测器必须能报出历史上真实发生过的遮蔽（否则它是空转的绿灯）。

    历史案例：`/{enterprise_id}/resources/{resource_id}`（无约束）注册在前，
    把 `/{enterprise_id}/resources/template` 吞掉。
    """
    import re

    bad = _route_regex("/enterprises/{enterprise_id}/resources/{resource_id}")
    assert re.match(bad, "/enterprises/E1/resources/template"), "检测器没能识别未约束参数路由"

    good = _route_regex("/enterprises/{enterprise_id}/resources/{resource_id:uuid}")
    assert not re.match(good, "/enterprises/E1/resources/template"), ":uuid 约束后不该再吞字面量"
    assert re.match(good, "/enterprises/E1/resources/6792266d-cd5f-41fc-b591-648fcb64b435")
