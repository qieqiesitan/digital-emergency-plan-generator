"""一次性鉴权审计：AST 解析所有路由的依赖，输出每端点鉴权级别（只读）。"""

import ast
import json
import pathlib
from collections import Counter, defaultdict

ROUTERS = pathlib.Path("app/routers")
AUTH_LEVELS = {
    "require_admin": "admin",
    "require_super_admin": "super",
    "get_current_user": "user",
}


def dep_arg(call):
    """从 Depends(get_current_user) 里取被依赖的函数名。"""
    if not isinstance(call, ast.Call):
        return None
    fn = call.func
    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
    if name != "Depends" or not call.args:
        return None
    inner = call.args[0]
    if isinstance(inner, ast.Call):
        inner = inner.func
    return inner.attr if isinstance(inner, ast.Attribute) else getattr(inner, "id", None)


def scan(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    prefix = ""
    router_level = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if fname == "APIRouter":
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = kw.value.value
                    if kw.arg == "dependencies" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        for elt in kw.value.elts:
                            name = dep_arg(elt)
                            if name:
                                router_level.append(name)
    routes = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr in ("get", "post", "put", "patch", "delete")):
                continue
            sub = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else ""
            level, deps = None, []
            defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d]
            for d in defaults:
                name = dep_arg(d)
                if name:
                    deps.append(name)
                    level = AUTH_LEVELS.get(name, level)
            for name in router_level:
                if name not in deps:
                    deps.append(name)
                level = level or AUTH_LEVELS.get(name)
            manual = [
                n.func.id for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in ("_require_admin", "_require_super_admin", "_require_admin_user")
            ]
            if manual:
                level = level or "admin(manual)"
            routes.append({
                "method": dec.func.attr.upper(), "path": prefix + sub,
                "handler": node.name, "auth": level or "NONE",
                "deps": deps, "manual": manual, "line": node.lineno,
                "router_level": list(router_level),
            })
    return routes


all_routes, per_file = [], {}
for path in sorted(ROUTERS.glob("*.py")):
    if path.name == "__init__.py":
        continue
    try:
        routes = scan(path)
    except Exception as exc:  # noqa: BLE001
        per_file[path.name] = {"error": str(exc)[:120]}
        continue
    per_file[path.name] = routes
    all_routes.extend(routes)

counts = Counter(r["auth"] for r in all_routes)
noauth = [r for r in all_routes if r["auth"] == "NONE"]
NEW = ("/work-tickets", "/major-hazard", "/platform", "/ingest", "/extraction")
new_routes = [r for r in all_routes if any(r["path"].startswith(p) for p in NEW)]

print(f"路由总数: {len(all_routes)}  鉴权分布: {dict(counts)}")
print(f"无鉴权端点: {len(noauth)}")
print("\n==== 新模块端点（前缀 {work-tickets,major-hazard,platform,ingest,extraction}） ====")
for r in sorted(new_routes, key=lambda x: (x["path"], x["method"])):
    flag = "NOAUTH" if r["auth"] == "NONE" else r["auth"]
    print(f"{flag:12s} {r['method']:6s} {r['path']:60s} {r['handler']}")
print("\n==== 无鉴权端点按路由文件统计 ====")
by_file = defaultdict(list)
for r in noauth:
    for fname, routes in per_file.items():
        if isinstance(routes, list) and r in routes:
            by_file[fname].append(r)
for fname, rs in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
    print(f"  {fname:28s} {len(rs):3d}  {', '.join(sorted({r['path'] for r in rs}))[:110]}")

out = pathlib.Path("exports/e2e-20260917")
out.mkdir(parents=True, exist_ok=True)
(out / "auth-audit.json").write_text(
    json.dumps({"counts": counts, "total": len(all_routes), "noauth": noauth,
                "per_file": per_file}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n明细已写入 {out/'auth-audit.json'}")
