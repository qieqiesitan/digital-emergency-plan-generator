"""清掉探针残留成员，并看清 DELETE 的真实返回（验证我的探针为何没删掉）。"""
import asyncio
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
MID = "8836dda5-7132-4cf9-a616-67861f3b3b7b"


async def main() -> int:
    async with httpx.AsyncClient(timeout=60) as c:
        token = (await c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                         "password": "test123456"})).json()
        h = {"Authorization": f"Bearer {(token.get('data') or {}).get('access_token')}"}
        r = await c.delete(f"{BASE}/enterprises/{ENT}/org/members/{MID}", headers=h)
        print(f"DELETE 成员：HTTP {r.status_code} {r.text[:120]}")
        r2 = await c.get(f"{BASE}/enterprises/{ENT}/org/members", headers=h)
        left = [m.get("name") for m in (r2.json().get("data") or [])]
        print(f"剩余成员：{left}")
        return 0 if r.status_code == 200 and not left else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
