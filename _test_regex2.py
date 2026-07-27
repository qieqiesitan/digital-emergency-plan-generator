import sys, os, re, inspect
sys.path.insert(0, "/app")
from importlib import import_module
mod = import_module("app.regulations.sync")
src = inspect.getsource(mod._extract_articles_from_text)
print(src)