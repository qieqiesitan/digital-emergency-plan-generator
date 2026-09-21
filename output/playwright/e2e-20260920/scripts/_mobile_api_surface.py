"""移动端「功能面」量化（只读，一次性）。

1) 移动端 Screen/组件 import 了哪些 service，这些 service 调了哪些后端端点；
2) 桌面 pages/components 用了哪些 service，其中哪些移动端完全没碰；
3) 与 backend/app/routers 的端点总数对照，给出覆盖率。
"""
import os
import re
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SRC = os.path.join(ROOT, "frontend", "src")
SERVICES = os.path.join(SRC, "services")

svc_import = re.compile(r'from\s+"@/services/([A-Za-z0-9_]+)"')
endpoint = re.compile(r'api\.(get|post|put|delete|patch)(?:<[^>]*>)?\(\s*[`"]([^`"]+)[`"]')


def walk(*dirs):
    for d in dirs:
        for base, _, files in os.walk(d):
            for f in files:
                if f.endswith((".ts", ".tsx")):
                    yield os.path.join(base, f)


def services_used(paths):
    used = set()
    for p in paths:
        try:
            txt = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        used |= set(svc_import.findall(txt))
    return used


def endpoints_of(svc_names):
    eps = set()
    missing = []
    for name in sorted(svc_names):
        fp = os.path.join(SERVICES, f"{name}.ts")
        if not os.path.exists(fp):
            missing.append(name)
            continue
        txt = open(fp, encoding="utf-8").read()
        for _, path in endpoint.findall(txt):
            eps.add(path if path.startswith("/") else "/" + path)
    return eps, missing


def main() -> None:
    mobile_files = list(walk(os.path.join(SRC, "mobile")))
    desktop_files = [
        p
        for p in walk(os.path.join(SRC, "pages"), os.path.join(SRC, "components"), os.path.join(SRC, "layouts"))
    ]

    m_svcs = services_used(mobile_files)
    d_svcs = services_used(desktop_files)
    m_eps, m_missing = endpoints_of(m_svcs)
    d_eps, d_missing = endpoints_of(d_svcs)

    all_service_files = {
        f[:-3] for f in os.listdir(SERVICES) if f.endswith(".ts") and not f.endswith(".test.ts")
    }

    print(f"service 文件总数            : {len(all_service_files)}")
    print(f"移动端引用的 service         : {len(m_svcs)}")
    print(f"桌面端引用的 service         : {len(d_svcs)}")
    print(f"移动端缺失 import 的 service : {sorted(all_service_files - m_svcs)}")
    print(f"service 名对不上文件（移动端）: {sorted(m_missing)}")
    print(f"service 名对不上文件（桌面端）: {sorted(d_missing)}")
    print()
    print(f"移动端触达端点（去重）        : {len(m_eps)}")
    print(f"桌面端触达端点（去重）        : {len(d_eps)}")
    print(f"桌面有、移动端没有的端点      : {len(d_eps - m_eps)}")
    print()
    print("== 桌面有、移动端完全没有的功能前缀（按 2 段聚合计数）==")
    bucket = defaultdict(int)
    for ep in d_eps - m_eps:
        parts = [x for x in ep.strip("/").split("/") if x and not x.startswith("${")]
        key = "/".join(parts[:2]) or ep
        bucket[key] += 1
    for k, v in sorted(bucket.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>3}  /{k}")
    print()
    print("== 移动端触达端点明细 ==")
    for ep in sorted(m_eps):
        print("  " + ep)


if __name__ == "__main__":
    main()
