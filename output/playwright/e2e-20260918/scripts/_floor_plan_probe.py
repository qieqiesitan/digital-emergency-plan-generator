"""楼层平面图上传/替换/删除端到端校验（B4 加固过的存储链路，此前无真实验证）。

顺带验证：类型白名单（422）、像素/尺寸读取、替换时清理旧文件、删除后底图置空。
跑完删除探针楼层（连同底图）。
"""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import zlib
import struct

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
FLOOR = "上传探针楼层"
BASE = f"/enterprises/{ENT}/risk-management"

results = []


def png_bytes(w: int = 4, h: int = 3) -> bytes:
    """生成一张纯色 PNG（不引第三方库，便于断言宽高解析）。"""
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


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
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {}


def upload(path, token, filename, content: bytes, content_type: str):
    boundary = "----probe" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        API + path, method="POST", data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {}


def main():
    floor_id = None
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        status, created = call("POST", f"{BASE}/floors", token,
                               {"name": FLOOR, "sort_order": 99})
        check("创建探针楼层", status == 201, f"status={status}")
        floor_id = created.get("data", {}).get("id")

        status, up = upload(f"{BASE}/floors/{floor_id}/plan?enterprise_id={ENT}", token,
                            "plan.png", png_bytes(4, 3), "image/png")
        url1 = (up.get("data") or {}).get("floor_plan_url")
        check("上传平面图返回 200", status == 200, f"status={status}")
        check("底图 URL 已写入", bool(url1 and url1.startswith("/uploads/")), url1)
        check("画布尺寸按图片解析", (up.get("data") or {}).get("canvas_width") == 4
              and (up.get("data") or {}).get("canvas_height") == 3, up.get("data"))
        check("文件确实落盘",
              sql(f"select count(*) from enterprise_floors where id='{floor_id}' "
                  f"and floor_plan_url is not null;") == "1")

        status, up2 = upload(f"{BASE}/floors/{floor_id}/plan?enterprise_id={ENT}", token,
                             "plan2.png", png_bytes(6, 5), "image/png")
        url2 = (up2.get("data") or {}).get("floor_plan_url")
        check("替换底图生成新 URL 且尺寸更新",
              status == 200 and url2 and url2 != url1
              and (up2.get("data") or {}).get("canvas_width") == 6, f"{url1} → {url2}")

        status, bad = upload(f"{BASE}/floors/{floor_id}/plan?enterprise_id={ENT}", token,
                             "not-image.txt", b"hello", "text/plain")
        check("非图片类型被拒（422）", status == 422, f"status={status} {bad}")

        status, repo = call("GET", f"{BASE}/floors", token)
        row = next((f for f in (repo.get("data") or []) if f["id"] == floor_id), None)
        check("楼层列表返回最新底图", bool(row) and row.get("floor_plan_url") == url2,
              row.get("floor_plan_url") if row else None)

        status, deleted = call("DELETE", f"{BASE}/floors/{floor_id}/plan?enterprise_id={ENT}", token)
        check("删除底图返回 200 且 URL 清空",
              status == 200 and not (deleted.get("data") or {}).get("floor_plan_url"),
              f"status={status}")
    finally:
        if floor_id:
            call("DELETE", f"{BASE}/floors/{floor_id}?enterprise_id={ENT}", token)
            print("cleanup done: 探针楼层已删除")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-floor-plan.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
