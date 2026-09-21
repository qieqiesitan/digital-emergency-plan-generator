"""按 AST 边界删除"被取代的旧入口"（只删指定函数/方法，含其上方装饰器与下方空行）。"""
import ast
import pathlib

TARGETS = {
    "backend/app/regulations/retriever.py": {"retrieve", "retrieve_by_topics", "_build_semantic_query"},
    "backend/app/regulations/graph.py": {"set_article_status", "get_effective_articles",
                                         "query_articles_by_plan_type"},
    "backend/app/regulations/context_builder.py": {"build_for_plan", "_format_context"},
    "backend/app/regulations/__init__.py": {"get_scorer"},
}


def remove(path: str, names: set[str]) -> list[str]:
    p = pathlib.Path(path)
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            spans.append((start, node.end_lineno, node.name))
    lines = src.splitlines(keepends=True)
    removed = []
    for start, end, name in sorted(spans, key=lambda s: -s[0]):
        while end < len(lines) and lines[end].strip() == "":
            end += 1
        del lines[start - 1:end]
        removed.append(name)
    p.write_text("".join(lines), encoding="utf-8")
    return removed


for path, names in TARGETS.items():
    print(f"{path}: 删除 {sorted(remove(path, names))}")
