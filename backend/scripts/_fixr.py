import os
root = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend"
os.chdir(root)
d = open("app/services/chat_dispatch.py", "rb").read()

target = b'      enterprises = await _list_enterprises(db, user, {})\r\n\r\n      data_context = json.dumps({'
insert = b'      enterprises = await _list_enterprises(db, user, {})\r\n\r\n      regulation_data = None\r\n      if "\xe6\xb3\x95\xe8\xa7\x84" in topic or "\xe6\xb3\x95\xe5\xbe\x8b" in topic:\r\n          try:\r\n              from app.regulations import get_graph\r\n              graph = get_graph()\r\n              stats = graph.stats()\r\n              reg_list = graph.list_nodes(page_size=20)\r\n              regulation_data = {"stats": stats, "regulations": [{"id": n.get("id"), "full_name": n.get("full_name", n.get("title", "")), "code": n.get("code", ""), "node_type": n.get("node_type"), "status": n.get("status")} for n in reg_list.get("items", [])]}\r\n          except Exception:\r\n              pass\r\n\r\n      data_context = json.dumps({'
d = d.replace(target, insert)
d = d.replace(b'"enterprises": enterprises.get("enterprises", [])[:5],', b'"enterprises": enterprises.get("enterprises", [])[:5],\r\n          "regulation_data": regulation_data,')
open("app/services/chat_dispatch.py", "wb").write(d)
import py_compile
py_compile.compile("app/services/chat_dispatch.py", doraise=True)
print("OK")