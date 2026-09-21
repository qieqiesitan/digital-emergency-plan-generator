"""移动端「service 函数级」使用率（只读，一次性）。

对每个 service，抽出其 export 的函数名，再统计移动端代码里实际出现的函数名，
给出「函数级覆盖率」与「桌面在用、移动端没用」的清单（比端点级更接近真实功能面）。
"""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SRC = os.path.join(ROOT, "frontend", "src")
SERVICES = os.path.join(SRC, "services")

fn_def = re.compile(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)")
fn_def2 = re.compile(r"export\s+const\s+([A-Za-z0-9_]+)\s*[:=]")
svc_import = re.compile(r'from\s+"@/services/([A-Za-z0-9_]+)"')


def read(path):
    try:
        return open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return ""


def collect(paths):
    text = "\n".join(read(p) for p in paths)
    return text, set(svc_import.findall(text))


def walk(d):
    for base, _, files in os.walk(d):
        for f in files:
            if f.endswith((".ts", ".tsx")):
                yield os.path.join(base, f)


def main() -> None:
    mobile_text, _ = collect(list(walk(os.path.join(SRC, "mobile"))))
    desktop_text, _ = collect(
        list(walk(os.path.join(SRC, "pages")))
        + list(walk(os.path.join(SRC, "components")))
        + list(walk(os.path.join(SRC, "layouts")))
    )

    svc_files = sorted(
        f for f in os.listdir(SERVICES) if f.endswith(".ts") and not f.endswith(".test.ts")
    )
    tot = m_used = d_used = 0
    rows = []
    for f in svc_files:
        name = f[:-3]
        if name in ("api",):
            continue
        src = read(os.path.join(SERVICES, f))
        fns = sorted(set(fn_def.findall(src)) | set(fn_def2.findall(src)))
        if not fns:
            continue
        in_mobile = re.search(rf'@/services/{re.escape(name)}"', mobile_text) is not None
        in_desktop = re.search(rf'@/services/{re.escape(name)}"', desktop_text) is not None
        used_by_m = [x for x in fns if re.search(rf"\b{re.escape(x)}\b", mobile_text)]
        used_by_d = [x for x in fns if re.search(rf"\b{re.escape(x)}\b", desktop_text)]
        tot += len(fns)
        m_used += len(used_by_m)
        d_used += len(used_by_d)
        rows.append((name, len(fns), len(used_by_m), len(used_by_d), in_mobile, in_desktop))

    print(f"service 文件（有导出函数的）: {len(rows)}   导出函数总数: {tot}")
    print(f"移动端引用到的函数            : {m_used} ({m_used * 100 // max(tot, 1)}%)")
    print(f"桌面端引用到的函数            : {d_used} ({d_used * 100 // max(tot, 1)}%)")
    print()
    print(f"{'service':<34}{'导出':>5}{'移动用':>7}{'桌面用':>7}  移动端 import")
    for name, n, um, ud, in_m, in_d in sorted(rows, key=lambda r: (r[2], r[1])):
        print(f"{name:<34}{n:>5}{um:>7}{ud:>7}  {'yes' if in_m else 'NO'}")


if __name__ == "__main__":
    main()
