import os
os.chdir(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend")
d = open("app/services/chat_dispatch.py", "rb").read()
t = b'      enterprises = await _list_enterprises(db, user, {})\n\n    data_context = json.dumps({\n'
i = b'      enterprises = await _list_enterprises(db, user, {})\n\n    regulation_data = None\n    if "\xe6\xb3\x95\xe8\xa7\x84" in topic or "\xe6\xb3\x95\xe5\xbe\x8b" in topic:\n        try:\n            from app.regulations import get_graph\n            graph = get_graph()\n            stats = graph.stats()\n            reg_list = graph.list_nodes(page_size=20)\n            regulation_data = {"stats": stats, "regulations": [{"id": n.get("id"), "full_name": n.get("full_name", n.get("title", "")), "code": n.get("code", ""), "node_type": n.get("node_type"), "status": n.get("status")} for n in reg_list.get("items", [])]}\n        except Exception:\n            pass\n\n    data_context = json.dumps({\n'
print("target found:", t in d)
d = d.replace(t, i)
open("app/services/chat_dispatch.py", "wb").write(d)
import py_compile
py_compile.compile("app/services/chat_dispatch.py", doraise=True)
print("OK")