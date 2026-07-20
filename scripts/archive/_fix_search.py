import re

with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py", "r", encoding="utf-8") as f:
    content = f.read()

old_discovery = """    from app.regulations import get_graph
    import re as _re

    graph = get_graph()
    keyword_result = graph.list_nodes(keyword=query, page_size=top_k)
    nodes = keyword_result.get("items", [])

    if not nodes:
        return {"articles": [], "count": 0, "message": "法规库中暂未找到与您问题直接相关的法规。"}"""

new_discovery = """    from app.regulations import get_graph
    import re as _re

    graph = get_graph()

    # ── 多策略节点发现（修复：支持"法规名 第X条"组合查询）──
    nodes = []
    seen_node_ids = set()

    def _collect_node(nid, data):
        if nid in seen_node_ids:
            return
        if data.get("status") == "abolished":
            return
        node = dict(data)
        node["id"] = nid
        seen_node_ids.add(nid)
        nodes.append(node)

    # 策略1：完整查询字符串匹配
    raw_result = graph.list_nodes(keyword=query, page_size=top_k)
    for n in raw_result.get("items", []):
        _collect_node(n.get("id", ""), {k: v for k, v in n.items() if k != "id"})

    # 策略2：拆分成单个关键词分别匹配图谱中的所有节点
    if not nodes:
        segments = _re.split(r"[\s\u3001]+|\u7684(?=\u7b2c)|(?<=\u6cd5)\u7684", query)
        individual_kw = [s.strip() for s in segments if len(s.strip()) >= 2]
        if not individual_kw:
            individual_kw = [kw.strip() for kw in query.split() if len(kw.strip()) >= 2]

        import os as _os
        tdir = _os.path.join(_os.path.dirname(__file__), "..", "regulations", "data", "texts")
        for nid, data in graph._g.nodes(data=True):
            if data.get("node_type") in ("topic", "article"):
                continue
            full = (data.get("full_name") or "").lower()
            label = (data.get("label") or "").lower()
            code = (data.get("code") or "").lower()
            for kw in individual_kw:
                if kw.lower() in full or kw.lower() in label or kw.lower() in code:
                    if _os.path.exists(_os.path.join(tdir, f"{nid}.md")):
                        _collect_node(nid, dict(data))
                        break

    if not nodes:
        return {"articles": [], "count": 0, "message": "法规库中暂未找到与您问题直接相关的法规。"}"""

old_scoring = """            score = 0
            query_lower = query.lower()
            text_lower = article_text.lower()
            for kw in keywords:
                count = text_lower.count(kw.lower())
                if count > 0:
                    score += count * 10
            if query_lower in text_lower:
                score += 50"""

new_scoring = """            score = 0
            query_lower = query.lower()
            # 条文编号也参与匹配（标题行如"第一条"）
            text_lower = (article_number + " " + article_text).lower()
            for kw in keywords:
                count = text_lower.count(kw.lower())
                if count > 0:
                    score += count * 10
                # 条文编号精确匹配大幅加分
                if kw.lower() == article_number.lower():
                    score += 100
            if query_lower in text_lower:
                score += 50"""

assert old_discovery in content, "Fix 1: Could not find old discovery section!"
content = content.replace(old_discovery, new_discovery, 1)
print("Fix 1 applied")

assert old_scoring in content, "Fix 2: Could not find old scoring section!"
content = content.replace(old_scoring, new_scoring, 1)
print("Fix 2 applied")

with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py", "w", encoding="utf-8") as f:
    f.write(content)

print("File written successfully")
