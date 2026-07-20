with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\chat.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add asyncio and markdown to top level
content = content.replace(
    "import httpx",
    "import asyncio\nimport httpx"
)

# Remove lazy imports from function bodies
removed = 0
for lazy in ["import markdown as md_lib\n", "import asyncio\n"]:
    # Remove all 4-space indented occurrences (inside function bodies)
    occurrences = content.count("    " + lazy)
    if occurrences:
        content = content.replace("    " + lazy, "")
        removed += occurrences
        print(f"Removed {occurrences}x '    {lazy.strip()}'")

with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\chat.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Total {removed} lazy imports removed from chat.py")
