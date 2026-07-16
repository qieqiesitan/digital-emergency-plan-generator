import os

path = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: _search_regulations bug
old = '            results = vs.similarity_search(query, k=5)\n            return {"results": [{"content": doc.page_content[:500], "metadata": doc.metadata} for doc in results]}'
new = '            results = vs.search(query, top_k=5)\n            return {"results": [{"content": item["text"][:500], "metadata": item["metadata"]} for item in results], "source": "vector_search"}'
content = content.replace(old, new)

# Fix 2: Register new function in _FUNCTIONS
old3 = '    "search_regulations": _search_regulations,'
new3 = '    "search_regulations": _search_regulations,\n    "search_regulation_articles": _search_regulation_articles,'
content = content.replace(old3, new3)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fix 1 + registration done")
