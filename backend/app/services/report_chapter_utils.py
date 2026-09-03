"""报告草稿章节（summary.chapters）读写工具。"""
from typing import Any


def get_chapters(summary: dict | None) -> list[dict]:
    if not summary or not isinstance(summary.get("chapters"), list):
        return []
    return summary["chapters"]


def upsert_chapter(chapters: list[dict], key: str, title: str, content: str) -> list[dict]:
    for ch in chapters:
        if ch.get("key") == key:
            ch["title"] = title
            ch["content"] = content
            return chapters
    chapters.append({"key": key, "title": title, "content": content})
    return chapters


def update_chapter_content(chapters: list[dict], key: str, content: str) -> list[dict]:
    for ch in chapters:
        if ch.get("key") == key:
            ch["content"] = content
            return chapters
    return chapters


def chapters_to_summary(chapters: list[dict]) -> dict[str, Any]:
    return {"chapters": chapters}
