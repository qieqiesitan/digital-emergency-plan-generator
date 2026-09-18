"""清理法规图谱中的「孤儿条文节点」（parent_regulation 指向已不存在的法规）。

背景：`ingest_regulation` 会为每条条文建 `art_{reg_id}_*` 子节点，而删除法规时
历史实现只删了法规节点本身 → 条文节点变成孤儿留在 graph.json 里。
孤儿不会被检索到（检索按 live 法规 id 过滤或跳过 article 节点），但会让图谱持续膨胀。
现网数据实测曾遗留 109 个孤儿节点。

用法：
    python scripts/purge_orphan_articles.py --dry-run     # 只报告，不改文件
    python scripts/purge_orphan_articles.py --apply       # 实际清理（自动备份）
"""

import argparse
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.regulations.graph import GRAPH_PATH, RegulationGraph  # noqa: E402


def find_orphans(graph: RegulationGraph) -> tuple[list[str], Counter]:
    g = graph._g
    ids = set(g.nodes)
    orphans = [
        nid for nid, data in g.nodes(data=True)
        if data.get("node_type") == "article"
        and data.get("parent_regulation")
        and data["parent_regulation"] not in ids
    ]
    return orphans, Counter(g.nodes[o].get("parent_regulation") for o in orphans)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际删除（默认只报告）")
    ap.add_argument("--dry-run", action="store_true", help="只报告（默认行为）")
    args = ap.parse_args()

    graph = RegulationGraph()
    graph.load()
    before = graph._g.number_of_nodes()
    orphans, by_parent = find_orphans(graph)
    print(f"graph: {GRAPH_PATH}")
    print(f"节点总数: {before}；孤儿条文节点: {len(orphans)}")
    for rid, n in by_parent.most_common(10):
        print(f"  {rid}: {n}")
    if not orphans:
        print("无需清理 ✅")
        return 0
    if not args.apply:
        print("（dry-run：未修改文件；加 --apply 执行清理）")
        return 0

    backup = f"{GRAPH_PATH}.bak"  # 已被 .gitignore 的 *.bak 覆盖，不会进版本库
    shutil.copy2(GRAPH_PATH, backup)
    for nid in orphans:
        graph._g.remove_node(nid)
    graph.save()
    after = graph._g.number_of_nodes()
    print(f"已删除 {len(orphans)} 个孤儿节点：{before} → {after}")
    print(f"备份：{backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
