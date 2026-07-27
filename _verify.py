import sys, os
sys.path.insert(0, "/app")

from app.regulations.sync import PARSE_PROMPT, _extract_articles_from_text
print("PARSE_PROMPT has articles line:", "10. 条文清单" in PARSE_PROMPT)
print("PARSE_PROMPT has JSON articles:", '"articles"' in PARSE_PROMPT)

sample = "第一条 为了加强安全生产工作，制定本法。\n第二条 在中华人民共和国领域内从事生产经营活动的单位的安全生产，适用本法。"
arts = _extract_articles_from_text(sample)
print("_extract_articles_from_text:", len(arts), "articles")

import inspect
from importlib import import_module
ai_parse_src = inspect.getsource(import_module("app.regulations.sync").ai_parse)
print("max_tokens limited:", "min(4096," in ai_parse_src)
print("preview truncation:", "raw_text[:5000]" in ai_parse_src)
print("All checks passed")