"""
Shared utilities for report generation routers.
ponytail: extract only the truly duplicated logic (summary JSON parsing),
not a full OOP hierarchy with one implementation.
"""
import re, json, logging

logger = logging.getLogger(__name__)


def parse_summary_from_last_chapter(chapters: list[dict]) -> dict | None:
    """Extract structured summary JSON from the last chapter's content.
    The LLM is prompted to output JSON at the end of the final chapter.
    Returns None if parsing fails (summary stays as-is)."""
    if not chapters:
        return None
    last_ch = chapters[-1]
    content = last_ch.get("content", "")
    if not content:
        return None
    # Find the last JSON object in the content
    try:
        # Try to find a JSON object near the end
        m = re.search(r"\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]+\}", content[::-1])
        if m:
            # Reverse back
            candidate = m.group()[::-1]
            struct = json.loads(candidate)
            return struct
    except (json.JSONDecodeError, Exception):
        pass
    # Fallback: try to find simpler JSON
    try:
        m = re.search(r"\{[^}]+\}\s*$", content)
        if m:
            return json.loads(m.group())
    except (json.JSONDecodeError, Exception):
        pass
    return None


def merge_summary_into_report(summary: dict, chapters: list[dict]) -> dict:
    """Merge parsed summary fields into the report's summary dict."""
    result = {"chapters": chapters}
    if summary:
        result.update(summary)
    return result
