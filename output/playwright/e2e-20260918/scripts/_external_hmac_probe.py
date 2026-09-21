"""外部对接（/api/external/*）HMAC 边界校验：零模型额度、零业务写入。

覆盖：
  ①未配置密钥 → 503（拒绝而不是放行）；
  ②缺头/错签名/过期时间戳 → 401；
  ③**有效签名** → 通过中间件进到业务层（这里故意查一个不存在的任务，期望 404，不触发任何生成）；
  ④同一签名重复发送：中间件不拦（仅有 ±5 分钟窗口），因此创建接口用 external_order_id 做幂等
    （该逻辑见 backend/tests/test_external_idempotency.py）。

探针会临时写入再删除 `third_party.protego.hmac_secret` 配置（本机原本未配置，删除即还原）。
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"
EXT = "http://localhost:8000/api/external"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
CONTAINER = "emergency-plan-backend"
STAMP = str(int(time.time()))[-6:]
SECRET = f"probe-hmac-secret-{STAMP}"
TASK = "00000000-0000-0000-0000-0000000000ff"

results = []


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


def ext_call(method, path, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(EXT + path, method=method, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()[:120]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:120]


def sign(method, path, ts, body_str, secret):
    payload = f"{method}\n{path}\n{ts}\n{body_str}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        # ① 未配置密钥
        sql("delete from third_party_config where config_key='third_party.protego.hmac_secret';")
        status, _ = ext_call("GET", f"/plans/{TASK}/status")
        check("未配置密钥 → 503（拒绝外部请求）", status == 503, f"status={status}")

        # 配置临时密钥（走应用服务，密文入库）
        setter = (
            "import asyncio;from app.services.third_party_config import set_third_party_config;"
            f"asyncio.run(set_third_party_config('third_party.protego.hmac_secret','{SECRET}'))"
        )
        subprocess.run(["docker", "exec", CONTAINER, "sh", "-c",
                        f"cd /app && PYTHONPATH=/app python -c \"{setter}\""],
                       capture_output=True, text=True, check=True)
        check("临时写入 HMAC 密钥", sql(
            "select count(*) from third_party_config "
            "where config_key='third_party.protego.hmac_secret';") == "1")

        path = f"/api/external/plans/{TASK}/status"
        ts = str(int(time.time()))
        body_str = ""
        good_sig = sign("GET", path, ts, body_str, SECRET)

        # ② 边界
        status, _ = ext_call("GET", f"/plans/{TASK}/status")
        check("缺签名头 → 401", status == 401, f"status={status}")
        status, _ = ext_call("GET", f"/plans/{TASK}/status",
                             {"X-Signature": "deadbeef", "X-Timestamp": ts})
        check("错签名 → 401", status == 401, f"status={status}")
        old_ts = str(int(time.time()) - 3600)
        status, _ = ext_call("GET", f"/plans/{TASK}/status",
                             {"X-Signature": sign("GET", path, old_ts, body_str, SECRET),
                              "X-Timestamp": old_ts})
        check("过期时间戳（1 小时前）→ 401", status == 401, f"status={status}")
        status, _ = ext_call("GET", f"/plans/{TASK}/status",
                             {"X-Signature": good_sig, "X-Timestamp": "abc"})
        check("非数字时间戳 → 401", status == 401, f"status={status}")

        # ③ 有效签名 → 中间件放行（业务层 404，不触发任何生成）
        status, body = ext_call("GET", f"/plans/{TASK}/status",
                                {"X-Signature": good_sig, "X-Timestamp": ts})
        check("有效签名通过中间件（业务层 404）", status == 404, f"status={status} {body[:60]}")

        # ④ 同一签名重发：中间件允许（时间窗内），创建接口靠订单幂等兜底
        status, _ = ext_call("GET", f"/plans/{TASK}/status",
                             {"X-Signature": good_sig, "X-Timestamp": ts})
        check("同签名重发仍被中间件接受（重放由业务幂等兜底）", status == 404,
              f"status={status}")
    finally:
        sql("delete from third_party_config where config_key='third_party.protego.hmac_secret';")
        status, _ = ext_call("GET", f"/plans/{TASK}/status")
        print(f"cleanup done: 密钥配置已删除（还原后状态 {status}，应为 503）")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-external-hmac.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
