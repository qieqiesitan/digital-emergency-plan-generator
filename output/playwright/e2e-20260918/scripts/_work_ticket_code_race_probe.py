"""作业票编号并发探针：同一企业/同一天并发开票，验证编号唯一性。
背景：work_ticket_service.open_ticket 的 docstring 声称"编号冲突时重试，最终由数据库唯一约束兜底"，
但实现是「读 MAX(seq) -> 插入」的单次 flush/commit，既没有重试也没有加锁。
本探针用 8 个并发请求压同一编号空间，观察是否出现 500（唯一约束 uq_wti_ent_code 冲突）。
"""
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

API = "http://localhost:8000/api/v1"
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
TEMPLATE_ID = "99f530de-2586-5f03-9751-b9db1bbb3777"  # DHZY 动火
ENTERPRISE_CODE = "RACE"
CONCURRENCY = 8


def call(method, path, token=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:
        return -1, str(exc).encode()


def main():
    status, raw = call("POST", "/auth/login", body={"email": U, "password": P})
    assert status == 200, (status, raw[:200])
    token = json.loads(raw)["data"]["access_token"]
    print("login 200")
    payload = {
        "enterprise_id": ENT,
        "enterprise_code": ENTERPRISE_CODE,
        "ticket_type": "DHZY",
        "template_id": TEMPLATE_ID,
        "level": None,
        "values": {"probe": "code-race"},
    }

    def open_one(_):
        code, body = call("POST", "/work-ticket/tickets", token=token, body=payload)
        parsed = None
        if code == 200:
            try:
                parsed = json.loads(body)["data"]["code"]
            except Exception:
                parsed = None
        return code, parsed, body[:160].decode("utf-8", "replace")

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(open_one, range(CONCURRENCY)))

    codes = Counter(r[1] for r in results if r[1])
    statuses = Counter(r[0] for r in results)
    dup = {c: n for c, n in codes.items() if n > 1}
    print("status distribution:", dict(statuses))
    print("distinct codes:", len(codes), "duplicates:", dup or "none")
    for code, parsed, head in results:
        if code != 200:
            print(f"  non-200 sample: status={code} body={head}")
    ok = statuses.get(200, 0) == CONCURRENCY and not dup
    print(("PASS" if ok else "FAIL") + f": {statuses.get(200, 0)}/{CONCURRENCY} ok, dup={len(dup)}")
    out = {
        "concurrency": CONCURRENCY,
        "statuses": dict(statuses),
        "distinct_codes": len(codes),
        "duplicates": dup,
        "pass": ok,
        "codes": sorted(codes),
    }
    with open(
        "backend/exports/e2e-20260918/summary-work-ticket-code-race.json", "w", encoding="utf-8"
    ) as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
