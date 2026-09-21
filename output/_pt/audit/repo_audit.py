"""仓库体检（只读）：BUG 模式 + 冗余/过度设计候选，按"能删多少/多危险"排序输出。

跑法（仓库根目录）：python output/_pt/audit/repo_audit.py
"""
import ast
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(".").resolve()
BACK = ROOT / "backend" / "app"
FRONT = ROOT / "frontend" / "src"
TESTS = ROOT / "backend" / "tests"
SCRIPTS = ROOT / "backend" / "scripts"

py_files = sorted(BACK.rglob("*.py"))
ts_files = sorted([p for p in FRONT.rglob("*") if p.suffix in (".ts", ".tsx")])


def line_of(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


print("=" * 78)
print("A. BUG 模式扫描")
print("=" * 78)

# A1 静默吞异常：except 块里只有 pass / continue / return None
silent: list[tuple[str, str]] = []
for p in py_files:
    src = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            body = list(handler.body)
            trivial = all(
                isinstance(n, ast.Pass)
                or (isinstance(n, ast.Return) and (n.value is None or
                                                   isinstance(n.value, ast.Constant)))
                for n in body
            )
            if trivial and body:
                exc_name = ast.unparse(handler.type) if handler.type else "裸"
                silent.append((f"{p.relative_to(ROOT)}:{handler.lineno}", exc_name))
by_dir = collections.Counter(str(pathlib.Path(loc).parent) for loc, _ in silent)
print(f"[A1] 静默吞异常 {len(silent)} 处，按目录聚集：")
for d, n in by_dir.most_common(8):
    print(f"     {n:3d}  {d}")
print("     样例（含捕获类型）：")
for loc, exc in silent[:8]:
    print(f"     {loc}  except {exc}")

# A2 裸 except
bare = [f"{p.relative_to(ROOT)}:{i + 1}" for p in py_files
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines())
        if re.match(r"\s*except\s*:", line)]
print(f"[A2] 裸 except {len(bare)} 处：{bare[:8]}")

# A3 asyncio.create_task 直接裸用（未走 spawn/registry，异常会静默丢失）
tasks = []
for p in py_files:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if "create_task(" in line and "spawn" not in line:
            tasks.append(f"{p.relative_to(ROOT)}:{i}")
print(f"[A3] create_task 直接调用 {len(tasks)} 处：{tasks[:10]}")

# A4 async 函数里的同步阻塞 sleep
blocking = []
for p in py_files:
    src = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "sleep" and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "time"):
                    blocking.append(f"{p.relative_to(ROOT)}:{sub.lineno}")
print(f"[A4] async 里 time.sleep（阻塞事件循环） {len(blocking)} 处：{blocking[:8]}")

# A5 危险调用 / SQL 拼接
danger = collections.Counter()
danger_hits: dict[str, list[str]] = collections.defaultdict(list)
for p in py_files:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        for pat, tag in (
            (r"shell\s*=\s*True", "shell=True"),
            (r"\bos\.system\(", "os.system"),
            (r"(?<![\w.])eval\(", "eval"),
            (r"(?<![\w.])exec\(", "exec"),
            (r'execute\(\s*f"', "SQL-f-string"),
            (r"execute\(\s*f'", "SQL-f-string"),
            (r"text\(\s*f\"SELECT", "SQL-f-string"),
        ):
            if re.search(pat, line):
                danger[tag] += 1
                danger_hits[tag].append(f"{p.relative_to(ROOT)}:{i}")
print(f"[A5] 危险调用：{dict(danger) if danger else '无'}")
for tag, hits in danger_hits.items():
    for h in hits[:4]:
        print(f"     {tag}: {h}")

# A6 同模块内重复定义同名函数（后者覆盖前者，常是真 bug）
dupdefs = []
for p in py_files:
    src = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    seen: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in seen:
                dupdefs.append(f"{p.relative_to(ROOT)}: {node.name} 定义于 {seen[node.name]} 与 {node.lineno}")
            seen[node.name] = node.lineno
print(f"[A6] 模块内重复定义 {len(dupdefs)} 处：{dupdefs[:6]}")

# A7 TODO/FIXME/HACK 标记
marks = collections.Counter()
for p in list(py_files) + ts_files:
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line)
        if m:
            marks[m.group(1)] += 1
print(f"[A7] 待办标记：{dict(marks)}")

print()
print("=" * 78)
print("B. 冗余 / 过度设计扫描")
print("=" * 78)

# B1 后端定义但全仓（app+tests+scripts）无引用（排除装饰器函数与字符串注册名）
back_sources = {p: p.read_text(encoding="utf-8", errors="ignore")
                for p in list(py_files) + list(TESTS.rglob("*.py")) + list(SCRIPTS.rglob("*.py"))}
all_back_text = "\n".join(back_sources.values())
dead_funcs = []
for p in py_files:
    src = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("__") or node.name in ("main", "lifespan"):
            continue
        if node.decorator_list:
            continue          # 路由器/中间件/依赖注入：由框架按装饰器引用
        name = node.name
        plain = len(re.findall(rf"\b{re.escape(name)}\b", all_back_text))
        as_string = len(re.findall(rf"""["']{re.escape(name)}["']""", all_back_text))
        # 出现次数 1 = 只有 def 自己；字符串形式出现也算被注册引用
        if plain <= 1 and as_string == 0:
            dead_funcs.append(f"{p.relative_to(ROOT)}:{node.lineno} {node.name}()")
print(f"[B1] 后端疑似无引用函数 {len(dead_funcs)} 个：")
for item in dead_funcs[:14]:
    print(f"     {item}")

# B2 前端 export 但其它文件从不 import
front_texts = {p: p.read_text(encoding="utf-8", errors="ignore") for p in ts_files}
dead_exports = []
for p, src in front_texts.items():
    for m in re.finditer(r"^export\s+(?:async\s+)?(?:const|function|class|interface|type)\s+(\w+)",
                         src, re.M):
        name = m.group(1)
        # 同文件内（除声明行本身）用过也算"在用"
        own_uses = len(re.findall(rf"\b{re.escape(name)}\b", src))
        if own_uses > 1:
            continue
        used_elsewhere = any(name in text for q, text in front_texts.items() if q != p)
        if not used_elsewhere:
            dead_exports.append(f"{p.relative_to(ROOT)}:{line_of(src, m.start())} {name}")
print(f"[B2] 前端疑似无引用导出 {len(dead_exports)} 个：")
for item in dead_exports[:14]:
    print(f"     {item}")

# B3 只做转发的薄包装（函数体只有一次调用，参数原样透传）
thin = []
for p in py_files:
    src = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [n for n in node.body if not isinstance(n, ast.Expr)]
        if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Call):
            call = body[0].value
            arg_names = {a.arg for a in node.args.args}
            passed = {a.id for a in call.args if isinstance(a, ast.Name)}
            if passed and passed <= arg_names and len(passed) == len(call.args):
                thin.append(f"{p.relative_to(ROOT)}:{node.lineno} {node.name}() → {ast.unparse(call.func)}")
print(f"[B3] 纯转发薄包装 {len(thin)} 个：")
for item in thin[:10]:
    print(f"     {item}")

# B4 跨文件重复代码块（≥10 行非平凡代码原样出现两次以上 = 复制粘贴）
_SKIP = re.compile(r"^\s*(#|$|\"\"\"|'''|\}|\)|\]|else:|try:|except|finally:|return|pass)")
blocks: dict[str, list[str]] = collections.defaultdict(list)
for p in list(py_files) + ts_files:
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    window = 10
    for i in range(len(lines) - window):
        chunk = [ln.strip() for ln in lines[i:i + window]]
        if sum(1 for ln in chunk if not _SKIP.match(ln)) < 8:
            continue
        key = "\n".join(chunk)
        blocks[key].append(f"{p.relative_to(ROOT)}:{i + 1}")
dups = {k: sorted(set(v)) for k, v in blocks.items() if len(set(v)) > 1}
# 同一文件内相邻窗口会重复计数：只保留"首个位置各不相同"的组
seen_roots: set[str] = set()
print(f"[B4] 跨文件重复代码块 {len(dups)} 组（前 6 组）：")
shown = 0
for key, locs in sorted(dups.items(), key=lambda kv: -len(kv[1])):
    root = locs[0].split(":")[0]
    if root in seen_roots:
        continue
    seen_roots.add(root)
    print(f"     {len(locs)} 处： " + " | ".join(locs[:4]))
    shown += 1
    if shown >= 6:
        break

print()
print("=" * 78)
print("C. 规模参考")
print("=" * 78)
print(f"后端 {len(py_files)} 个 py / {sum(len(p.read_text(encoding='utf-8').splitlines()) for p in py_files)} 行")
print(f"前端 {len(ts_files)} 个 ts(x) / {sum(len(t.splitlines()) for t in front_texts.values())} 行")
sys.exit(0)
