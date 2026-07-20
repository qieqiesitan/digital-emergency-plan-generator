"""数据迁移脚本: 将现有法规回填 article 子节点到图谱。

用法:
  cd backend && python scripts/migrate_to_article_level.py
"""

import os
import re
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate")

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.regulations.graph import RegulationGraph


def migrate():
    graph = RegulationGraph()
    graph.load()
    logger.info("Graph loaded: %d nodes, %d edges",
                graph._g.number_of_nodes(), graph._g.number_of_edges())

    texts_dir = os.path.join(os.path.dirname(__file__), "..", "app", "regulations", "data", "texts")
    texts_dir = os.path.abspath(texts_dir)

    if not os.path.isdir(texts_dir):
        logger.error("texts dir missing: %s", texts_dir)
        return

    stats = {"created": 0, "updated": 0, "errors": 0}

    for fname in sorted(os.listdir(texts_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(texts_dir, fname)
        reg_id = fname.replace(".md", "")

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            logger.error("Read fail %s: %s", fname, e)
            stats["errors"] += 1
            continue

        blocks = re.split(r"\n(?=##\s)", raw)
        count = 0
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            title = lines[0].lstrip("#").strip() if lines else ""
            text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if not text or len(text) < 10:
                continue
            try:
                graph.add_article_node(reg_id, {"number": title, "text": text})
                count += 1
                stats["created"] += 1
            except Exception:
                stats["updated"] += 1

        logger.info("  %s: %d articles", fname, count)

    graph.save()
    logger.info("Done: %s", stats)
    return stats


if __name__ == "__main__":
    migrate()
