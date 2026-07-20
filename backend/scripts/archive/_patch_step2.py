import os
path = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

marker = "\n\n# \u2500\u2500 AI \u914d\u7f6e \u2500\u2500"
indent = "\n"

# Read handler from separate file
handler_path = os.path.join(os.path.dirname(__file__), "_handler_snippet.txt")
with open(handler_path, "r", encoding="utf-8") as f:
    handler = f.read()

content = content.replace(marker, handler + marker)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Handler inserted")