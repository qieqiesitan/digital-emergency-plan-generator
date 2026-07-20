import subprocess, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

r = subprocess.run(["git", "show", "HEAD:backend/app/routers/chat.py"], capture_output=True)
data = r.stdout

# 1. Replace tool definition
old_tool_start = b'    {"type": "function", "function": {"name": "generate_report", "description": "'
with open(os.path.join(os.path.dirname(__file__), "_new_tool_bytes.bin"), "rb") as f:
    new_tool_block = f.read()
data = data.replace(old_tool_start, new_tool_block)

# 2. Replace prompt ending
old_end = b'\xe9\xaa\x8c\xe8\xaf\x81\xe7\x8a\xb6\xe6\x80\x81\xe3\x80\x82"'
with open(os.path.join(os.path.dirname(__file__), "_new_prompt_bytes.bin"), "rb") as f:
    new_end = f.read()
data = data.replace(old_end, new_end)

out = os.path.join(os.getcwd(), "app", "routers", "chat.py")
with open(out, "wb") as f:
    f.write(data)

import py_compile
py_compile.compile(out, doraise=True)
print("OK size:", len(data))