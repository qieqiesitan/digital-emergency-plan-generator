import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Remove BOM and add path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from app.services.chat_dispatch import _search_regulation_articles
from app.routers.chat import CHAT_SYSTEM_PROMPT, CHAT_TOOLS
import asyncio

# Verify imports
tool_names = [t["function"]["name"] for t in CHAT_TOOLS]
assert "search_regulation_articles" in tool_names, "Tool not found in CHAT_TOOLS!"
print("OK: tool definition present")

# Verify prompt
assert "????" in CHAT_SYSTEM_PROMPT, "Regulation rules not in prompt!"
print("OK: system prompt has citation rules")

# Test search
result = asyncio.run(_search_regulation_articles(None, None, {"query": "???????????"}))
print("Search count:", result.get("count", 0))
for a in result.get("articles", [])[:2]:
    print("  -", a["regulation_full_name"], "/", a["article_number"], ":", a["article_text"][:60])
print("All tests passed!")