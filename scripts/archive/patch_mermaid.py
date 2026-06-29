import re

# Read mermaid_renderer.py
with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\mermaid_renderer.py", "r", encoding="utf-8") as f:
    content = f.read()

# Read cleaner function
with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\mermaid_cleaner.py", "r", encoding="utf-8") as f:
    cleaner = f.read()

# Find the extract_mermaid_from_markdown function and insert cleaner after it
old_func = 'def extract_mermaid_from_markdown(md_text: str) -> list[str]:'
idx = content.index(old_func)
# Find end of function (next def or end of file)
next_def = content.find('\ndef ', idx + len(old_func))
if next_def == -1:
    next_def = len(content)
content = content[:next_def] + '\n\n' + cleaner + content[next_def:]

# Add cleaning call in render_mermaid_svg
content = content.replace(
    'async def render_mermaid_svg(code: str, retries: int = 3) -> str:',
    'async def render_mermaid_svg(code: str, retries: int = 3) -> str:\n    code = _clean_mermaid_syntax(code)'
)
content = content.replace(
    'async def render_mermaid_png(code: str, retries: int = 3) -> bytes:',
    'async def render_mermaid_png(code: str, retries: int = 3) -> bytes:\n    code = _clean_mermaid_syntax(code)'
)

# Write back
with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\mermaid_renderer.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
