"""Pytest bootstrap: make the backend package importable from any invocation directory.

Mirrors the sys.path handling in tests/test_web_search.py (inserting the backend
directory at sys.path[0]) without the hardcoded absolute path or os.chdir, so both
`cd backend && pytest tests/...` and root-level `pytest backend/tests/...` work.
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
