"""法规库只读家族校验：路由顺序（/graph-data、/stats/data、/history/global 不被 /{id} 吞掉）
+ 详情/影响/来源版本等读路径。零写入、零 AI。
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
U, P = "qa_e2e_test@test.com", "test123456"
REG_ID = os.environ.get("E2E_REG", "gb30077_2023")

results = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw[:200].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:200].decode("utf-8", "replace")


def main():
    os.makedirs(OUT, exist_ok=True)
    _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
    token = pr["data"]["access_token"]

    status, listing = call("GET", "/regulations?page=1&page_size=5", token)
    check("法规列表可读", status == 200, f"status={status}")
    items = (listing.get("data") or {}).get("items") if isinstance(listing, dict) else None
    check("列表返回结构正常", isinstance(items, list) and len(items) > 0,
          f"items={len(items) if isinstance(items, list) else items}")
    if isinstance(items, list) and items:
        check("列表项含编号与名称",
              all((i.get("code") or i.get("full_name")) for i in items[:3]),
              json.dumps(items[0], ensure_ascii=False)[:120])

    # 路由顺序：这几个字面量 GET 不能被 /{regulation_id} 吞掉（否则 422/404）
    for path, label in (("/regulations/graph-data", "法规图谱数据"),):
        status, body = call("GET", path, token)
        ok = status == 200
        detail = f"status={status}"
        if ok and isinstance(body, dict):
            data = body.get("data") or {}
            detail += f" nodes={len(data.get('nodes') or [])} edges={len(data.get('edges') or [])}"
        check(f"{label}（字面量路由不被吞）", ok, detail)

    status, stats = call("GET", "/regulations/stats/data", token)
    check("法规统计接口（/stats/data 不被 /{id} 吞）", status == 200, f"status={status}")

    status, hist = call("GET", "/regulations/history/global", token)
    check("全局历史接口（/history/global 不被 /{id}/history 吞）", status == 200, f"status={status}")

    status, detail = call("GET", f"/regulations/{REG_ID}", token)
    check("法规详情可读", status == 200, f"status={status} id={REG_ID}")
    name = (detail.get("data") or {}).get("full_name") if isinstance(detail, dict) else None
    check("详情含名称", bool(name), name)

    status, impact = call("GET", f"/regulations/{REG_ID}/impact", token)
    check("废止影响接口可读", status == 200, f"status={status}")

    status, versions = call("GET", f"/regulations/{REG_ID}/source/versions", token)
    check("来源版本接口可读", status == 200, f"status={status}")

    status, history = call("GET", f"/regulations/{REG_ID}/history", token)
    check("单条历史接口可读", status == 200, f"status={status}")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-regulations-read.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
