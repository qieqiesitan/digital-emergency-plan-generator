import os
os.chdir(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend")
lines = open("app/services/chat_dispatch.py", "r", encoding="utf-8").readlines()
out = []
found = False
for line in lines:
    if not found and "enterprises = await _list_enterprises(db, user, {})" in line:
        out.append(line)
        out.append('    regulation_data = None\n')
        out.append('    if "\u6cd5\u89c4" in topic or "\u6cd5\u5f8b" in topic:\n')
        out.append('        try:\n')
        out.append('            from app.regulations import get_graph\n')
        out.append('            graph = get_graph()\n')
        out.append('            stats = graph.stats()\n')
        out.append('            reg_list = graph.list_nodes(page_size=20)\n')
        out.append('            regulation_data = {"stats": stats, "regulations": [{"id": n.get("id"), "full_name": n.get("full_name", n.get("title", "")), "code": n.get("code", ""), "node_type": n.get("node_type"), "status": n.get("status")} for n in reg_list.get("items", [])]}\n')
        out.append('        except Exception:\n')
        out.append('            pass\n')
        out.append('\n')
        found = True
    else:
        out.append(line)
open("app/services/chat_dispatch.py", "w", encoding="utf-8").writelines(out)
import py_compile
py_compile.compile("app/services/chat_dispatch.py", doraise=True)
print("OK")